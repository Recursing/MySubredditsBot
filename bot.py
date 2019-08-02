import traceback
from aiogram import Bot, Dispatcher, executor
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
dp = Dispatcher(bot)


async def add_subscriptions(chat_id: int, subs: List[str]):
    for sub in subs:
        if not reddit_adapter.valid_subreddit(sub):
            await bot.send_message(
                chat_id, "{} is not a valid subreddit name".format(sub)
            )
        elif await reddit_adapter.check_exists(sub):
            monthly_rank = 31
            threshold = await reddit_adapter.get_threshold(sub, monthly_rank)
            if not subscriptions_manager.subscribe(
                chat_id, sub, threshold, monthly_rank
            ):
                await bot.send_message(
                    chat_id, "You are already subscribed to {}".format(sub)
                )
        else:
            await bot.send_message(chat_id, "Cannot find {} subreddit".format(sub))
    await list_subscriptions(chat_id)
    for sub, _th, _pm in subscriptions_manager.user_subscriptions(chat_id):
        await send_subreddit_updates(sub)


@dp.message_handler(commands=["add"])
async def handle_add(message: dict):
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

        async def add_reply_handler(message):
            subs = message["text"].lower().replace(",", " ").replace("+", " ").split()
            await add_subscriptions(chat_id, subs)

        """bot.ask(
            chat_id,
            "What would you like to subscribe to?",
            reply_handler=add_reply_handler,
        )"""


async def remove_subscriptions(chat_id: int, subs: List[str]):
    for sub in subs:
        if not subscriptions_manager.unsubscribe(chat_id, sub):
            await bot.send_message(chat_id, "You are not subscribed to {}".format(sub))
    await list_subscriptions(chat_id)


@dp.message_handler(commands=["remove"])
async def handle_remove(message: dict):
    """
        Unsubscribe from a subreddit
    """
    chat_id = message["chat"]["id"]
    text = message["text"].strip().lower()
    if len(text.split()) > 1:
        await remove_subscriptions(chat_id, text.split()[1:])
    else:

        async def remove_reply_handler(message):
            await remove_subscriptions(chat_id, message["text"].lower().split())

        user_thresholds = subscriptions_manager.user_thresholds(chat_id)
        subreddits = [subreddit for subreddit, threshold in user_thresholds]
        subreddits.sort()
        if not subreddits:
            await bot.send_message(
                chat_id,
                "You are not subscribed to any subreddit, press /add to subscribe",
            )
        """else:
            bot.ask(
                chat_id,
                "Which subreddit would you like to unsubscribe from?",
                reply_handler=remove_reply_handler,
                possible_replies=subreddits,
            )"""


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
    template = "You will now receive on average about {} messages per day from {}"
    await bot.send_message(
        chat_id, template.format(round(new_monthly / 32, 2), subreddit)
    )


async def handle_change_threshold(message: dict, factor: float):
    """
        factor: new_monthly / current_monthly
    """
    chat_id = message["chat"]["id"]
    text = message["text"].strip().lower()
    if len(text.split()) > 1:
        await change_threshold(chat_id, text.split(None, 1)[1], factor=factor)
    else:

        async def change_threshold_handler(message):
            await change_threshold(chat_id, message["text"].lower(), factor=factor)

        user_thresholds = subscriptions_manager.user_thresholds(chat_id)
        subreddits = [subreddit for subreddit, threshold in user_thresholds]
        subreddits.sort()
        if not subreddits:
            await bot.send_message(
                chat_id,
                "You are not subscribed to any subreddit, press /add to subscribe",
            )
        """else:
            question_template = (
                "From which subreddit would you like to recieve {} updates?"
            )
            question = question_template.format("more" if factor > 1 else "less")
            bot.ask(
                chat_id,
                question,
                reply_handler=change_threshold_handler,
                possible_replies=subreddits,
            )"""


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
        text_list = "\n".join(
            [
                "{}, about {:.2f} per day".format(sub, per_month / 31)
                for sub, th, per_month in subscriptions
            ]
        )
        await bot.send_message(
            chat_id, "You are curently subscribed to:\n{}".format(text_list)
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
        post_iterator = await reddit_adapter.top_day_posts(subreddit)
        if any(threshold <= 50 for chat_id, threshold in subscriptions):
            post_iterator += await reddit_adapter.new_posts(subreddit)
        for post in post_iterator:
            # cur_timestamp = datetime.now().timestamp()
            # subscriptions_manager.store_post(post.id, post.title, post.score,
            #                                 post.created_utc, cur_timestamp, subreddit)
            for chat_id, threshold in subscriptions:
                if post["score"] > threshold:
                    await send_post(chat_id, post)

    except Exception as e:
        await log_exception(e, f"send_subreddit_updates({subreddit})")
        time.sleep(60 * 2)


@dp.message_handler(commands=["start", "help"])
async def help_message(message: dict):
    """
        Send help message
    """
    command_docs = "".join(
        "/{}: {}".format(key, f.__doc__)
        for key, f in {
            "help": help_message,
            "add": handle_add,
            "remove": handle_remove,
            "mo4r": handle_mo4r,
            "list": handle_list,
        }.items()
    )
    await bot.send_message(
        message["chat"]["id"],
        "Try the following commands: \n    {}".format(command_docs),
    )


async def main_loop():
    while True:
        subreddits = subscriptions_manager.all_subreddits()
        if len(subreddits) == 0:
            await asyncio.sleep(10)
        for subreddit in subreddits:
            sleep_time = 60 * 15 / len(subreddits)
            print(f"Tracking {len(subreddits)} sleeping for {sleep_time}")
            await asyncio.sleep(sleep_time)
            try:
                print(f"Sending updates for subreddit {subreddit}")
                await send_subreddit_updates(subreddit)
            except Exception as e:
                await log_exception(e, f"Exception while sending {subreddit}")

    logger.info("Sent updates to everybody")


async def on_startup(dp):
    asyncio.create_task(main_loop())


def format_traceback(e: Exception):
    tb = traceback.format_tb(e.__traceback__)
    line_sep = "==============================\n"
    return f"{e!r}:\n{line_sep.join(tb)}"


async def log_exception(e: Exception, message: str):
    formatted_traceback = format_traceback(e)
    logger.error(message, exc_info=True)
    logger.error(formatted_traceback)
    await bot.send_message(80906134, message)
    await bot.send_message(80906134, formatted_traceback)


if __name__ == "__main__":
    # TODO use async with job queue
    executor.start_polling(dp, on_startup=on_startup)
