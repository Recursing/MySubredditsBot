import asyncio
import logging
import time
import traceback
import tracemalloc
from datetime import datetime
from random import shuffle
from typing import Callable, List, Optional

from aiogram import Bot, Dispatcher, exceptions, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters import Command
from aiogram.dispatcher.filters.state import State, StatesGroup

import credentials
import media_handler
import reddit_adapter
import subscriptions_manager

tracemalloc.start()


# :(((
BANNED = {
    783219617,
    686522367,
    457538401,
    765120636,
    782767735,
    1003294400,
    -395678896,
    347883772,
    25897720,
    691437317,
    833945522,
    -1001229267832,
}

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


def delete_user(chat_id):
    logger.warning(f"Unsubscribing user {chat_id}")
    for sub in subscriptions_manager.user_subreddits(chat_id):
        subscriptions_manager.unsubscribe(chat_id, sub)


async def reply_wrapper(message, *args, **kwargs):
    kwargs["reply_to_message_id"] = message.message_id
    await send_message_wrapper(message.chat.id, *args, **kwargs)


def catch_telegram_exceptions(func: Callable) -> Callable:
    async def wrap(*args, **kwargs) -> bool:
        try:
            await func(*args, **kwargs)
            return True
        except (exceptions.Unauthorized, exceptions.ChatNotFound) as e:
            chat_id = kwargs.get("chat_id") or args[0]
            unsub_reasons = [
                "chat not found",
                "bot was blocked by the user",
                "user is deactivated",
                "chat not found",
                "bot was kicked",
            ]
            if any(reason in str(e).lower() for reason in unsub_reasons):
                delete_user(chat_id)
            else:
                await log_exception(e, f"Failed to send {args} {kwargs}")
        except exceptions.InlineKeyboardExpected as e:
            if "reply_markup" in kwargs:
                del kwargs["reply_markup"]
                await send_message_wrapper(*args, **kwargs)
            else:
                raise e
        except exceptions.MigrateToChat as e:
            new_chat_id = e.migrate_to_chat_id
            old_chat_id = kwargs.get("chat_id") or args[0]
            for sub, pm in subscriptions_manager.user_subscriptions(old_chat_id):
                subscriptions_manager.subscribe(new_chat_id, sub, pm)
                subscriptions_manager.unsubscribe(old_chat_id, sub)
        except exceptions.RetryAfter as e:
            time_to_sleep = e.timeout + 1
            await asyncio.sleep(time_to_sleep)
        except exceptions.NetworkError:
            await asyncio.sleep(60)
        except (
            exceptions.NotFound,
            exceptions.RestartingTelegram,
            exceptions.TelegramAPIError,
        ) as e:
            await log_exception(e, f"TelegramApiError {args} {kwargs}")
            # await asyncio.sleep(60 * 30)  # Telegram down, sleep a while
        return False

    return wrap


@catch_telegram_exceptions
async def send_message_wrapper(*args, **kwargs):
    await bot.send_message(*args, **kwargs)


@catch_telegram_exceptions
async def send_media_wrapper(chat_id: int, url: str, caption: str, parse_mode: str):
    await media_handler.send_media(bot, chat_id, url, caption, parse_mode)


class StateMachine(StatesGroup):
    asked_remove = State()
    asked_add = State()
    asked_more = State()
    asked_less = State()


@dp.channel_post_handler(Command(["cancel"]), state="*")
@dp.message_handler(state="*", commands=["cancel"])
async def cancel_handler(message: types.Message, state, raw_state=None):
    """
    Allow user to cancel any action
    """
    # Cancel state and inform user about it
    await state.finish()
    # And remove keyboard (just in case)
    await reply_wrapper(message, "Canceled.", reply_markup=types.ReplyKeyboardRemove())


@dp.callback_query_handler(lambda cb: cb.data.startswith("cancel"), state="*")
async def inline_cancel_handler(query: types.CallbackQuery, state):
    message = query.message
    await state.finish()
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    await send_message_wrapper(
        message.chat.id, "Canceled.", reply_markup=types.ReplyKeyboardRemove()
    )


async def get_posts_error(sub: str, monthly_rank: int) -> Optional[str]:
    if not reddit_adapter.valid_subreddit(sub):
        return f"{sub} is not a valid subreddit name"
    try:
        posts = await reddit_adapter.get_posts(sub, monthly_rank)
        if posts:
            return None
        return f"r/{sub} does not exist or is empty or something"
    except reddit_adapter.SubredditBanned:
        return f"r/{sub} has been banned"
    except reddit_adapter.SubredditPrivate:
        return f"r/{sub} is private"


async def add_subscription(chat_id: int, sub: str) -> bool:
    monthly_rank = 31
    error = await get_posts_error(sub, monthly_rank)
    if error:
        await send_message_wrapper(chat_id, error)
    if not subscriptions_manager.subscribe(chat_id, sub, monthly_rank):
        await send_message_wrapper(chat_id, f"You are already subscribed to {sub}")
        return False
    return True


async def add_subscriptions(chat_id: int, subs: List[str]):
    if len(subs) > 5:
        await send_message_wrapper(
            chat_id, "Can't subscribe to more than 5 subreddits per message"
        )
        return
    for sub in subs:
        if subscriptions_manager.is_subscribed(chat_id, sub):
            await send_message_wrapper(chat_id, f"You are already subscribed to {sub}")
            return
        err = await get_posts_error(sub, 31)
        if err:
            await send_message_wrapper(chat_id, err)
            return

    for sub in subs:
        await add_subscription(chat_id, sub)
    await send_message_wrapper(chat_id, f"You have subscribed to {', '.join(subs)}")
    await list_subscriptions(chat_id)
    for sub in subs:
        await send_subscription_updates(sub, chat_id, 31)


@dp.channel_post_handler(state=StateMachine.asked_add)
@dp.message_handler(state=StateMachine.asked_add)
async def add_reply_handler(message: types.Message, state):
    if not message.text or message.text is None:
        return
    subs = message.text.lower().replace(",", " ").replace("+", " ").split()
    await add_subscriptions(message.chat.id, subs)
    await state.finish()


@dp.channel_post_handler(Command(["add"]))
@dp.message_handler(commands=["add"])
async def handle_add(message: types.Message):
    """
        Subscribe to new space/comma separated subreddits
    """
    chat_id = message["chat"]["id"]
    if chat_id in BANNED:
        return
    text = message["text"].lower().strip()

    if len(text.split()) > 1:
        await add_subscriptions(
            chat_id, text.replace(",", " ").replace("+", " ").split()[1:]
        )
    else:
        await StateMachine.asked_add.set()
        inline_keyboard = types.InlineKeyboardMarkup()
        inline_keyboard.add(
            types.InlineKeyboardButton("cancel", callback_data="cancel")
        )
        await reply_wrapper(
            message,
            "What would you like to subscribe to?",
            reply_markup=inline_keyboard,
        )


async def remove_subscriptions(chat_id: int, subs: List[str]):
    for sub in subs:
        if not subscriptions_manager.is_subscribed(chat_id, sub):
            await send_message_wrapper(chat_id, f"Error: not subscribed to {sub}")
            return

    for sub in subs:
        subscriptions_manager.unsubscribe(chat_id, sub)
    await send_message_wrapper(chat_id, f"You have unsubscribed from {', '.join(subs)}")
    await list_subscriptions(chat_id)


@dp.callback_query_handler(lambda cb: cb.data.startswith("remove|"), state="*")
async def remove_callback_handler(query: types.CallbackQuery, state):
    if not query.data or query.data is None:
        return
    _remove, *subs = query.data.split("|")
    message = query.message
    await state.finish()
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    await remove_subscriptions(message.chat.id, subs)
    await query.answer()


@dp.channel_post_handler(state=StateMachine.asked_remove)
@dp.message_handler(state=StateMachine.asked_remove)
async def remove_reply_handler(message: types.Message, state):
    await remove_subscriptions(message.chat.id, message["text"].lower().split())
    await state.finish()


def sub_list_keyboard(chat_id: int, command):
    subreddits = subscriptions_manager.user_subreddits(chat_id)
    subreddits.sort(reverse=True)
    if not subreddits:
        return types.ReplyKeyboardRemove()

    if len(subreddits) >= 19:
        # TODO paginate
        reply_markup = types.ReplyKeyboardMarkup(
            resize_keyboard=True, selective=True, one_time_keyboard=True
        )
        for row in chunks(subreddits):
            reply_markup.add(*row)
        reply_markup.add("/cancel")
        return reply_markup

    inline_markup = types.InlineKeyboardMarkup()
    for row in chunks(subreddits):
        button_row = [
            types.InlineKeyboardButton(s, callback_data=f"{command}|{s}") for s in row
        ]
        inline_markup.row(*button_row)
    inline_markup.add(types.InlineKeyboardButton("cancel", callback_data="cancel"))
    return inline_markup


@dp.channel_post_handler(Command(["remove"]))
@dp.message_handler(commands=["remove"])
async def handle_remove(message: types.Message):
    """
        Unsubscribe from a subreddit
    """
    chat_id = message["chat"]["id"]
    text = message["text"].strip().lower()
    if len(text.split()) > 1:
        await remove_subscriptions(chat_id, text.split()[1:])
    else:
        subreddits = subscriptions_manager.user_subreddits(chat_id)
        subreddits.sort()
        if not subreddits:
            await reply_wrapper(
                message,
                "You are not subscribed to any subreddit, press /add to subscribe",
            )
        else:
            await StateMachine.asked_remove.set()
            markup = sub_list_keyboard(chat_id, "remove")
            await reply_wrapper(
                message,
                "Which subreddit would you like to unsubscribe from?",
                reply_markup=markup,
            )


@dp.callback_query_handler(lambda cb: cb.data.startswith("change_th|"))
async def inline_change_handler(query: types.CallbackQuery):
    if not query.data or query.data is None:
        return
    _less, subreddit = query.data.split("|")
    await change_threshold(
        query.message.chat.id, subreddit, factor=1, original_message=query.message
    )
    await query.answer()  # send answer to close the rounding circle


async def change_threshold(
    chat_id: int, subreddit: str, factor: float, original_message=None
):
    if not subscriptions_manager.is_subscribed(chat_id, subreddit):
        await send_message_wrapper(
            chat_id, f"You are not subscribed to {subreddit}, press /add to subscribe"
        )
        return

    current_monthly = subscriptions_manager.get_per_month(chat_id, subreddit)
    new_monthly = round(current_monthly * factor)
    if new_monthly == current_monthly and factor != 1:
        if factor > 1:
            new_monthly = current_monthly + 1
        else:
            new_monthly = current_monthly - 1
    if new_monthly > 1500:
        new_monthly = 1500
    if new_monthly < 1:
        await send_message_wrapper(chat_id=chat_id, text="Press /remove to unsubscribe")
        return
    err = await get_posts_error(subreddit, new_monthly)
    if err:
        await send_message_wrapper(chat_id=chat_id, text=err)
        return
    subscriptions_manager.update_per_month(chat_id, subreddit, new_monthly)
    message_text = (
        f"You will receive about {format_period(new_monthly)} " f"from {subreddit}"
    )
    inline_keyboard = types.InlineKeyboardMarkup()
    inline_keyboard.row(
        types.InlineKeyboardButton("Less", callback_data=f"less|{subreddit}"),
        types.InlineKeyboardButton("More", callback_data=f"more|{subreddit}"),
    )
    inline_keyboard.add(types.InlineKeyboardButton("cancel", callback_data="cancel"))
    if original_message is None:
        await send_message_wrapper(chat_id, message_text, reply_markup=inline_keyboard)
    else:
        await bot.edit_message_text(
            text=message_text,
            chat_id=original_message.chat.id,
            message_id=original_message.message_id,
            reply_markup=inline_keyboard,
        )


@dp.callback_query_handler(lambda cb: cb.data.startswith("less|"))
async def inline_less_handler(query: types.CallbackQuery):
    if not query.data or query.data is None:
        return
    _less, subreddit = query.data.split("|")
    await change_threshold(
        query.message.chat.id, subreddit, factor=1 / 1.5, original_message=query.message
    )
    await query.answer()  # send answer to close the rounding circle


@dp.callback_query_handler(lambda cb: cb.data.startswith("more|"))
async def inline_more_handler(query: types.CallbackQuery):
    await query.answer()  # send answer to close the rounding circle
    if not query.data or query.data is None:
        return
    _more, subreddit = query.data.split("|")
    await change_threshold(
        query.message.chat.id, subreddit, factor=1.5, original_message=query.message
    )


@dp.channel_post_handler(state=StateMachine.asked_less)
@dp.message_handler(state=StateMachine.asked_less)
async def asked_less_handler(message: types.Message, state):
    await change_threshold(message.chat.id, message["text"].lower(), factor=1 / 1.5)
    await state.finish()


@dp.channel_post_handler(state=StateMachine.asked_more)
@dp.message_handler(state=StateMachine.asked_more)
async def asked_more_handler(message: types.Message, state):
    await change_threshold(message.chat.id, message["text"].lower(), factor=1.5)
    await state.finish()


async def handle_change_threshold(message: types.Message, factor: float):
    """
        factor: new_monthly / current_monthly
    """
    chat_id = message["chat"]["id"]
    text = message["text"].strip().lower()
    if len(text.split()) > 1:
        await change_threshold(chat_id, text.split(None, 1)[1], factor=factor)
    else:
        subreddits = subscriptions_manager.user_subreddits(chat_id)
        subreddits.sort()
        if not subreddits:
            await reply_wrapper(
                message,
                "You are not subscribed to any subreddit, press /add to subscribe",
            )
        else:
            if factor >= 1:
                await StateMachine.asked_more.set()
                markup = sub_list_keyboard(chat_id, "more")
            else:
                await StateMachine.asked_less.set()
                markup = sub_list_keyboard(chat_id, "less")

            question_template = "From which subreddit would you like to get {} updates?"
            question = question_template.format("more" if factor > 1 else "fewer")

            await reply_wrapper(message, question, reply_markup=markup)


@dp.channel_post_handler(Command(["moar", "more", "mo4r"]))
@dp.message_handler(commands=["moar", "more", "mo4r"])
async def handle_mo4r(message: types.Message):
    """
        Receive more updates from subreddit
    """
    await handle_change_threshold(message, 1.5)


def format_period(per_month):
    if per_month > 31:
        return f"{per_month // 31} messages per day"
    if per_month == 31:
        return "one message every day"
    return f"one message every {31 / per_month:.1f} days"


@dp.channel_post_handler(Command(["less", "fewer"]))
@dp.message_handler(commands=["less", "fewer"])
async def handle_less(message: types.Message):
    """
        Receive fewer updates from subreddit
    """
    await handle_change_threshold(message, 1 / 1.5)


async def list_subscriptions(chat_id: int):
    subscriptions = list(subscriptions_manager.user_subscriptions(chat_id))
    if subscriptions:
        text_list = "\n\n".join(
            (
                f"[{sub}](https://www.reddit.com/r/{sub}), "
                f"about {format_period(per_month)}"
            )
            for sub, per_month in subscriptions
        )
        markup = sub_list_keyboard(chat_id, "change_th")
        await send_message_wrapper(
            chat_id,
            f"You are currently subscribed to:\n\n{text_list}",
            parse_mode="Markdown",
            reply_markup=markup,
            disable_web_page_preview=True,
        )
    else:
        await send_message_wrapper(
            chat_id, "You are not subscribed to any subreddit, press /add to subscribe"
        )


@dp.channel_post_handler(Command(["list"]))
@dp.message_handler(commands=["list"])
async def handle_list(message: dict):
    """
        List subreddits you're subscribed to
    """
    await list_subscriptions(message["chat"]["id"])


async def send_post(chat_id: int, post):
    if subscriptions_manager.already_sent(chat_id, post["id"]):
        return
    # TODO: handle images and gifs
    print(f"sending posts {post['id']} to {chat_id}")
    try:
        formatted_post = reddit_adapter.formatted_post(post)
        sent = False
        if await media_handler.contains_media(post["url"]):
            sent = await send_media_wrapper(
                chat_id, post["url"], formatted_post, parse_mode="HTML"
            )
        else:
            sent = await send_message_wrapper(
                chat_id, formatted_post, parse_mode="HTML"
            )
        if sent:
            subscriptions_manager.mark_as_sent(chat_id, post["id"])
    except Exception as e:
        await log_exception(e, f"Failed to send {formatted_post} to {chat_id}")
        # If I'm doing something wrong or telegram is down, at least wait a bit
        await asyncio.sleep(60 * 2)


async def send_subscription_updates(subreddit: str, chat_id: int, per_month: int):
    # Don't send more than 4 messages in a row to the same chat_id, to avoid flooding
    try:
        post_iterator = await reddit_adapter.get_posts(subreddit, per_month)
        if per_month > 2000:
            post_iterator += await reddit_adapter.new_posts(subreddit)
        # Don't send more than 4 messages "at once", to prevent flooding
        sent_posts = 0
        for post in post_iterator:
            if post["created_utc"] < 1590051621:
                continue
            if subscriptions_manager.already_sent(chat_id, post["id"]):
                continue
            sent_posts += 1
            if sent_posts > 4:
                break
            await send_post(chat_id, post)
    except reddit_adapter.SubredditBanned:
        if not subscriptions_manager.already_sent_exception(
            chat_id, subreddit, "banned"
        ):
            await send_message_wrapper(chat_id, f"r/{subreddit} has been banned")
            subscriptions_manager.mark_exception_as_sent(chat_id, subreddit, "banned")
        subscriptions_manager.unsubscribe(chat_id, subreddit)
    except reddit_adapter.SubredditPrivate:
        if not subscriptions_manager.already_sent_exception(
            chat_id, subreddit, "private"
        ):
            await send_message_wrapper(chat_id, f"r/{subreddit} has been made private")
            subscriptions_manager.mark_exception_as_sent(chat_id, subreddit, "private")
        subscriptions_manager.unsubscribe(chat_id, subreddit)
    except Exception as e:
        await log_exception(
            e, f"send_subscription_updates({subreddit}, {chat_id}, {per_month})"
        )
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


@dp.channel_post_handler(Command(["start", "help"]))
@dp.message_handler(commands=["start", "help"])
async def help_message(message: dict):
    """
        Send help message
    """
    commands = {
        "/help": help_message,
        "/add": handle_add,
        "/remove": handle_remove,
        "/more": handle_mo4r,
        "/less": handle_less,
        "/list": handle_list,
    }

    command_docs = "".join(f"{key}: {f.__doc__}" for key, f in commands.items())

    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True, selective=True, one_time_keyboard=True
    )
    command_list = list(commands.keys())
    for row in chunks(command_list):
        markup.add(*row)

    await send_message_wrapper(
        message["chat"]["id"],
        f"Try the following commands: \n    {command_docs}",
        reply_markup=markup,
    )


async def send_updates(refresh_period=15 * 60):
    print(datetime.now(), "sending updates...")
    subscriptions = subscriptions_manager.get_subscriptions()
    shuffle(subscriptions)
    print(subscriptions)
    sleep_time = refresh_period / len(subscriptions)
    print("sleep time:", sleep_time)
    if len(subscriptions) == 0:
        await asyncio.sleep(10)
    last_time = time.time()
    tasks = []
    batch_size = 10
    for chat_id, subreddit, per_month in subscriptions:
        tasks.append(send_subscription_updates(subreddit, chat_id, per_month))
        if len(tasks) >= batch_size:
            assert len(tasks) == batch_size
            tasks.append(asyncio.sleep(sleep_time * batch_size))
            await asyncio.wait(tasks)
            tasks = []
            print(
                f"Managing {len(subscriptions)}: sleeping for "
                f"{sleep_time * batch_size:.2f} slept for {time.time() - last_time:.2f}"
            )
            last_time = time.time()
    await asyncio.gather(*tasks)
    print(datetime.now(), "Sent updates")


async def check_exceptions(refresh_period=24 * 60 * 60):
    """
        Check whether private or banned subs are now available
    """
    unavailable_subs = subscriptions_manager.unavailable_subreddits()
    try:
        for sub in unavailable_subs:
            try:
                await reddit_adapter.new_posts(sub)
            except (reddit_adapter.SubredditPrivate, reddit_adapter.SubredditBanned):
                continue
            old_subscribers = subscriptions_manager.get_old_subscribers(sub)
            for chat_id in old_subscribers:
                await add_subscription(chat_id, sub)
                await send_message_wrapper(chat_id, f"{sub} is now available again")
            subscriptions_manager.delete_exception(sub)
    except Exception as e:
        await log_exception(e, f"Exception while checking unavailability of {sub}")
    await asyncio.sleep(refresh_period)


async def loop_forever(fun):
    while True:
        try:
            await fun()
        except Exception:
            print("!!! Exception in loop_forever!")


async def on_startup(_dispatcher):
    asyncio.create_task(loop_forever(send_updates))
    asyncio.create_task(loop_forever(check_exceptions))


def format_traceback(e: Exception) -> str:
    tb = traceback.format_tb(e.__traceback__)
    line_sep = "==============================\n"
    return f"{e!r}:\n{line_sep.join(tb)}"


async def log_exception(e: Exception, message: str):
    formatted_traceback = format_traceback(e)
    print("Logging exception:", message, formatted_traceback)
    logger.error(message, exc_info=True)
    logger.error(formatted_traceback)
    try:
        await bot.send_message(
            chat_id=credentials.ADMIN_ID, text=formatted_traceback[:2000]
        )
        await bot.send_message(chat_id=credentials.ADMIN_ID, text=message)
    except Exception as e2:
        print("*******Exception sending exception!!")
        print(f"{e2!r}")


if __name__ == "__main__":
    # TODO use async with job queue
    executor.start_polling(dp, on_startup=on_startup)
