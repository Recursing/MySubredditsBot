import traceback
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
import subscriptions_manager
import reddit_adapter
import logging
import time
import asyncio
import credentials
from typing import List

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="infolog.log",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


bot = Bot(credentials.BOT_API_KEY)  # commands=list(commands.keys()))
# bot.start_handling(perm_handle)
dp = Dispatcher(bot, storage=MemoryStorage())


class StateMachine(StatesGroup):
    asked_remove = State()
    asked_add = State()
    asked_more = State()
    asked_less = State()


@dp.message_handler(state="*", commands=["cancel"])
@dp.message_handler(lambda message: message.text.lower() == "cancel", state="*")
async def cancel_handler(message: types.Message, state, raw_state=None):
    """
    Allow user to cancel any action
    """
    # Cancel state and inform user about it
    await state.finish()
    # And remove keyboard (just in case)
    await message.reply("Canceled.", reply_markup=types.ReplyKeyboardRemove())


async def add_subscription(chat_id: int, sub: str) -> bool:
    if not reddit_adapter.valid_subreddit(sub):
        await bot.send_message(chat_id, "{} is not a valid subreddit name".format(sub))
        return False
    try:
        await reddit_adapter.check_subreddit(sub)
    except reddit_adapter.SubredditEmpty:
        await bot.send_message(chat_id, f"r/{sub} does not exist or is empty")
        return False
    except reddit_adapter.SubredditBanned:
        await bot.send_message(chat_id, f"r/{sub} has been banned")
        return False
    except reddit_adapter.SubredditPrivate:
        await bot.send_message(chat_id, f"r/{sub} is private")
        return False
    monthly_rank = 31
    threshold = await reddit_adapter.get_threshold(sub, monthly_rank)
    if not subscriptions_manager.subscribe(chat_id, sub, threshold, monthly_rank):
        await bot.send_message(chat_id, f"You are already subscribed to {sub}")
        return False
    return True


async def add_subscriptions(chat_id: int, subs: List[str]):
    new_subs = []
    for sub in subs:
        if await add_subscription(chat_id, sub):
            new_subs.append(sub)
    if new_subs:
        await list_subscriptions(chat_id)
        for sub in new_subs:
            await send_subreddit_updates(sub)


@dp.message_handler(state=StateMachine.asked_add)
async def add_reply_handler(message: types.message, state):
    subs = message.text.lower().replace(",", " ").replace("+", " ").split()
    await add_subscriptions(message.chat.id, subs)
    await state.finish()


@dp.message_handler(commands=["add"])
async def handle_add(message: types.message):
    """
        Subscribe to new space/comma separated subreddits
    """
    chat_id = message["chat"]["id"]
    text = message["text"].lower().strip()

    if len(text.split()) > 1:
        await add_subscriptions(
            chat_id, text.replace(",", " ").replace("+", " ").split()[1:]
        )
    else:
        await StateMachine.asked_add.set()
        markup = types.ReplyKeyboardMarkup(
            resize_keyboard=True, selective=True, one_time_keyboard=True
        )
        markup.add("/cancel")
        await message.reply("What would you like to subscribe to?", markup)


async def remove_subscriptions(chat_id: int, subs: List[str]):
    for sub in subs:
        if not subscriptions_manager.unsubscribe(chat_id, sub):
            await bot.send_message(chat_id, "You are not subscribed to {}".format(sub))
    await list_subscriptions(chat_id)


@dp.message_handler(state=StateMachine.asked_remove)
async def remove_reply_handler(message: types.message, state):
    await remove_subscriptions(message.chat.id, message["text"].lower().split())
    await state.finish()


@dp.message_handler(commands=["remove"])
async def handle_remove(message: types.message):
    """
        Unsubscribe from a subreddit
    """
    chat_id = message["chat"]["id"]
    text = message["text"].strip().lower()
    if len(text.split()) > 1:
        await remove_subscriptions(chat_id, text.split()[1:])
    else:
        user_thresholds = subscriptions_manager.user_thresholds(chat_id)
        subreddits = [subreddit for subreddit, threshold in user_thresholds]
        subreddits.sort()
        if not subreddits:
            await message.reply(
                "You are not subscribed to any subreddit, press /add to subscribe"
            )
        else:
            await StateMachine.asked_remove.set()
            markup = types.ReplyKeyboardMarkup(
                resize_keyboard=True, selective=True, one_time_keyboard=True
            )
            for row in chunks(subreddits):
                markup.add(*row)
            markup.add("/cancel")
            await message.reply(
                "Which subreddit would you like to unsubscribe from?",
                reply_markup=markup,
            )


async def change_threshold(chat_id: int, subreddit: str, factor: float):
    try:
        current_monthly = subscriptions_manager.get_per_month(chat_id, subreddit)
    except Exception as e:
        await log_exception(e, f"Getting monthly threshold for {chat_id}, {subreddit}")
        await bot.send_message(
            chat_id,
            "You are not subscribed to {}, press /add to subscribe".format(subreddit),
        )
        return
    new_monthly = round(current_monthly * factor)
    if new_monthly == current_monthly:
        if factor > 1:
            new_monthly = current_monthly + 1
        else:
            new_monthly = current_monthly - 1
    if new_monthly > 300:
        new_monthly = 300
    if new_monthly < 1:
        await bot.send_message(chat_id=chat_id, text="Press /remove to unsubscribe")
        return
    new_threshold = await reddit_adapter.get_threshold(subreddit, new_monthly)
    subscriptions_manager.update_threshold(
        chat_id, subreddit, new_threshold, new_monthly
    )
    message_text = (
        f"You will now receive on average about {new_monthly / 31:.2f} "
        f"messages per day from {subreddit}, "
        f"minimum score: {new_threshold}"
    )
    await bot.send_message(chat_id, message_text)


@dp.message_handler(state=StateMachine.asked_less)
async def asked_less_handler(message: types.message, state):
    await change_threshold(message.chat.id, message["text"].lower(), factor=1 / 1.5)
    await state.finish()


@dp.message_handler(state=StateMachine.asked_more)
async def asked_more_handler(message: types.message, state):
    await change_threshold(message.chat.id, message["text"].lower(), factor=1.5)
    await state.finish()


async def handle_change_threshold(message: types.message, factor: float):
    """
        factor: new_monthly / current_monthly
    """
    chat_id = message["chat"]["id"]
    text = message["text"].strip().lower()
    if len(text.split()) > 1:
        await change_threshold(chat_id, text.split(None, 1)[1], factor=factor)
    else:
        user_thresholds = subscriptions_manager.user_thresholds(chat_id)
        subreddits = [subreddit for subreddit, threshold in user_thresholds]
        subreddits.sort()
        if not subreddits:
            await message.reply(
                "You are not subscribed to any subreddit, press /add to subscribe"
            )
        else:
            if factor > 1:
                await StateMachine.asked_more.set()
            else:
                await StateMachine.asked_less.set()
            markup = types.ReplyKeyboardMarkup(
                resize_keyboard=True, selective=True, one_time_keyboard=True
            )
            for row in chunks(subreddits):
                markup.add(*row)
            markup.add("/cancel")

            question_template = (
                "From which subreddit would you like to recieve {} updates?"
            )
            question = question_template.format("more" if factor > 1 else "less")

            await bot.send_message(chat_id, question, reply_markup=markup)


@dp.message_handler(commands=["moar", "more", "mo4r"])
async def handle_mo4r(message: dict):
    """
        Receive more updates from subreddit
    """
    await handle_change_threshold(message, 1.5)


@dp.message_handler(commands=["less", "fewer"])
async def handle_less(message: dict):
    """
        Receive fewer updates from subreddit
    """
    await handle_change_threshold(message, 1 / 1.5)


async def list_subscriptions(chat_id: int):
    subscriptions = list(subscriptions_manager.user_subscriptions(chat_id))
    if subscriptions:

        def format_period(per_month):
            if per_month > 31:
                return f"{per_month/31:.2f} per day"
            elif per_month == 31:
                return f"one every day"
            return f"one every {31/per_month:.2f} days"

        text_list = "\n\n".join(
            f"*{sub}*, about {format_period(per_month)}, > {th} upvotes"
            for sub, th, per_month in subscriptions
        )
        await bot.send_message(
            chat_id,
            "You are curently subscribed to:\n{}".format(text_list),
            parse_mode="Markdown",
            reply_markup=types.ReplyKeyboardRemove(),
        )
    else:
        await bot.send_message(
            chat_id, "You are not subscribed to any subreddit, press /add to subscribe"
        )


@dp.message_handler(commands=["list"])
async def handle_list(message: dict):
    """
        List subreddits you're subscribed to
    """
    await list_subscriptions(message["chat"]["id"])


async def send_post(chat_id: int, post):
    if not subscriptions_manager.already_sent(chat_id, post["id"]):
        formatted_post = reddit_adapter.formatted_post(post)
        try:
            await bot.send_message(chat_id, formatted_post, parse_mode="HTML")
            subscriptions_manager.mark_as_sent(chat_id, post["id"])
        except Exception as e:
            await log_exception(e, f"Failed to send {formatted_post} to {chat_id}")
            unsub_reasons = [
                "chat not found",
                "bot was blocked by the user",
                "user is deactivated",
                "chat not found",
                "bot was kicked",
            ]
            if any(reason in str(e) for reason in unsub_reasons):
                logger.warning("Unsubscribing user {}".format(chat_id))
                for sub, th, pm in subscriptions_manager.user_subscriptions(chat_id):
                    subscriptions_manager.unsubscribe(chat_id, sub)
            elif (
                hasattr(e, "json")
                and "group chat was upgraded to a supergroup chat"
                in getattr(e, "json")["description"]
            ):
                logger.warning("Resubscribing group {}".format(chat_id))
                for sub, th, pm in subscriptions_manager.user_subscriptions(chat_id):
                    subscriptions_manager.subscribe(
                        getattr(e, "json")["parameters"]["migrate_to_chat_id"],
                        sub,
                        th,
                        pm,
                    )
                    subscriptions_manager.unsubscribe(chat_id, sub)
            else:
                time.sleep(60 * 2)


async def send_subreddit_updates(subreddit: str):
    subscriptions = list(subscriptions_manager.sub_followers(subreddit))
    try:
        try:
            post_iterator = await reddit_adapter.top_day_posts(subreddit)
        except reddit_adapter.SubredditEmpty:  # No posts today
            post_iterator = []
        if any(threshold <= 50 for chat_id, threshold, _pm in subscriptions):
            post_iterator += await reddit_adapter.new_posts(subreddit)
        for post in post_iterator:
            # cur_timestamp = datetime.now().timestamp()
            # subscriptions_manager.store_post(post.id, post.title, post.score,
            #                                 post.created_utc, cur_timestamp, subreddit)
            for chat_id, threshold, _pm in subscriptions:
                if post["score"] > threshold:
                    await send_post(chat_id, post)
    except reddit_adapter.SubredditBanned:
        for chat_id, _threshold, _pm in subscriptions + [(credentials.ADMIN_ID, 0)]:
            if not subscriptions_manager.already_sent_exception(
                chat_id, subreddit, "banned"
            ):
                await bot.send_message(chat_id, f"r/{subreddit} has been banned")
                subscriptions_manager.mark_exception_as_sent(
                    chat_id, subreddit, "banned"
                )
            subscriptions_manager.unsubscribe(chat_id, subreddit)
    except reddit_adapter.SubredditPrivate:
        for chat_id, _threshold, _pm in subscriptions + [(credentials.ADMIN_ID, 0, 0)]:
            if not subscriptions_manager.already_sent_exception(
                chat_id, subreddit, "private"
            ):
                await bot.send_message(chat_id, f"r/{subreddit} has been made private")
                subscriptions_manager.mark_exception_as_sent(
                    chat_id, subreddit, "private"
                )
            subscriptions_manager.unsubscribe(chat_id, subreddit)

    except Exception as e:
        await log_exception(e, f"send_subreddit_updates({subreddit})")
        time.sleep(60 * 2)


def chunks(sequence, chunk_size=2):
    """
        [1,2,3,4,5], 2 --> [[1,2],[3,4],[5]]
    """
    lsequence = list(sequence)
    while lsequence:
        size = min(len(lsequence), chunk_size)
        yield lsequence[:size]
        lsequence = lsequence[size:]


@dp.message_handler(commands=["start", "help"])
async def help_message(message: dict):
    """
        Send help message
    """
    commands = {
        "/help": help_message,
        "/add": handle_add,
        "/remove": handle_remove,
        "/mo4r": handle_mo4r,
        "/list": handle_list,
    }

    command_docs = "".join(
        "{}: {}".format(key, f.__doc__) for key, f in commands.items()
    )

    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True, selective=True, one_time_keyboard=True
    )
    command_list = list(commands.keys())
    for row in chunks(command_list):
        markup.add(*row)

    await bot.send_message(
        message["chat"]["id"],
        "Try the following commands: \n    {}".format(command_docs),
        reply_markup=markup,
    )


async def send_updates(refresh_period=15 * 60):
    subreddits = subscriptions_manager.all_subreddits()
    if len(subreddits) == 0:
        await asyncio.sleep(10)
    for subreddit in subreddits:
        sleep_time = refresh_period / len(subreddits)
        print(f"Tracking {len(subreddits)} sleeping for {sleep_time}")
        await asyncio.sleep(sleep_time)
        try:
            print(f"Sending updates for subreddit {subreddit}")
            await send_subreddit_updates(subreddit)
        except Exception as e:
            await log_exception(e, f"Exception while sending {subreddit}")

    logger.info("Sent updates")


async def check_exceptions(refresh_period=24 * 60 * 60):
    """
        Check whether private or banned subs are now available
    """
    unavailable_subs = subscriptions_manager.unavailable_subreddits()
    try:
        for sub in unavailable_subs:
            try:
                reddit_adapter.new_posts(sub)
            except (reddit_adapter.SubredditPrivate, reddit_adapter.SubredditBanned):
                continue
            old_subscribers = subscriptions_manager.get_old_subscribers(sub)
            for chat_id in old_subscribers:
                await add_subscription(chat_id, sub)
                await bot.send_message(chat_id, f"{sub} is now available again")
    except Exception as e:
        await log_exception(e, f"Exception while checking unavailability of {sub}")
    await asyncio.sleep(refresh_period)


async def update_thresholds(refresh_period=36 * 60 * 60):
    """
        Update all upvote thresholds based on monthly number
    """
    subreddits = subscriptions_manager.all_subreddits()
    if len(subreddits) == 0:
        await asyncio.sleep(refresh_period)
    for subreddit in subreddits:
        for chat_id, old_threshold, per_month in subscriptions_manager.sub_followers(
            subreddit
        ):
            new_threshold = await reddit_adapter.get_threshold(subreddit, per_month)
            if new_threshold != old_threshold:
                subscriptions_manager.update_threshold(
                    chat_id, subreddit, new_threshold, per_month
                )
            await asyncio.sleep(2)
    await asyncio.sleep(refresh_period)


async def loop_forever(fun):
    while True:
        await fun()


async def on_startup(dp):
    asyncio.create_task(loop_forever(send_updates))
    asyncio.create_task(loop_forever(check_exceptions))
    asyncio.create_task(loop_forever(update_thresholds))


def format_traceback(e: Exception):
    tb = traceback.format_tb(e.__traceback__)
    line_sep = "==============================\n"
    return f"{e!r}:\n{line_sep.join(tb)}"


async def log_exception(e: Exception, message: str):
    formatted_traceback = format_traceback(e)
    logger.error(message, exc_info=True)
    logger.error(formatted_traceback)
    await bot.send_message(credentials.ADMIN_ID, message)
    await bot.send_message(credentials.ADMIN_ID, formatted_traceback)


if __name__ == "__main__":
    # TODO use async with job queue
    executor.start_polling(dp, on_startup=on_startup)
