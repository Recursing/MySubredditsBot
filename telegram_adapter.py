from __future__ import annotations

import asyncio
import logging
import time
import traceback
from functools import wraps
from typing import Awaitable, Callable

from aiogram import Bot, Dispatcher, exceptions
from aiogram.contrib.fsm_storage.memory import MemoryStorage

import credentials
import media_handler
import reddit_adapter
import subscriptions_manager

bot = Bot(credentials.BOT_API_KEY)
dispatcher = Dispatcher(bot, storage=MemoryStorage())


class mockBot:
    def __getattribute__(self, attr):
        print(f"Called bot.{attr}")

        async def mock_fun(*args, **kwargs):
            print(f"With: {args} {kwargs}")

        return mock_fun


# TODO proper mocking for tests
# bot = mockBot()


def format_traceback(e: Exception) -> str:
    tb = traceback.format_tb(e.__traceback__)
    line_sep = "==============================\n"
    return f"{e!r}:\n{line_sep.join(tb)}"


async def send_to_admin(message: str):
    try:
        await bot.send_message(chat_id=credentials.ADMIN_ID, text=message[:2000])
    except Exception as e2:
        logging.error("*******Exception sending message to admin!!")
        logging.error(f"{e2!r}")


async def send_exception(e: Exception, message: str):
    formatted_traceback = format_traceback(e)
    logging.error(f"Logging exception: {message} {formatted_traceback}")
    logging.error(message, exc_info=True)
    logging.error(formatted_traceback)
    await send_to_admin(formatted_traceback)
    await send_to_admin(message)


def catch_telegram_exceptions(
    func: Callable[..., Awaitable[bool]]
) -> Callable[..., Awaitable[bool]]:
    @wraps(func)
    async def wrap(*args, **kwargs) -> bool:
        try:
            return await func(*args, **kwargs)
        except (exceptions.Unauthorized, exceptions.ChatNotFound) as e:
            chat_id = kwargs.get("chat_id") or args[0]
            unsub_reasons = [
                "chat not found",
                "bot was blocked by the user",
                "user is deactivated",
                "chat not found",
                "bot was kicked",
                "bot is not a member",
                "need administrator rights",
            ]
            if any(reason in str(e).lower() for reason in unsub_reasons):
                logging.warning(f"Unsubscribing user {chat_id} for {e!r}")
                subscriptions_manager.delete_user(chat_id)
            else:
                await send_exception(e, f"Failed to send {args} {kwargs}")
        except exceptions.InlineKeyboardExpected as e:
            if "reply_markup" in kwargs:
                del kwargs["reply_markup"]
                await send_message(*args, **kwargs)
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
            logging.error(f"{e!r} RetryAfter error, sleeping")
            time.sleep(time_to_sleep)
        except exceptions.NetworkError as e:
            logging.error(f"{e!r} network error, sleeping")
            time.sleep(60)
        except (
            exceptions.NotFound,
            exceptions.RestartingTelegram,
            exceptions.TelegramAPIError,
        ) as e:
            await send_exception(e, f"TelegramApiError {args} {kwargs}")
            logging.error(f"{e!r} Telegram error, sleeping")
            await asyncio.sleep(60)  # Telegram maybe down, sleep a while
        return False

    return wrap


@catch_telegram_exceptions
async def send_message(*args, **kwargs) -> bool:
    await bot.send_message(*args, **kwargs)
    return True


@catch_telegram_exceptions
async def send_media(chat_id: int, url: str, caption: str) -> bool:
    # parse_mode is always HTML
    await media_handler.send_media(bot, chat_id, url, caption)
    return True


async def edit_message(text: str, chat_id: int, message_id: int, reply_markup):
    try:
        await bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
        )
    except exceptions.MessageNotModified:
        pass
    except Exception as e:
        logging.error(f"Exception editing message: {e!r}")


async def reply(message, *args, **kwargs):
    kwargs["reply_to_message_id"] = message.message_id
    await send_message(message.chat.id, *args, **kwargs)


async def send_post(
    chat_id: int, content: reddit_adapter.Post | reddit_adapter.Comment, subreddit: str
):
    if subscriptions_manager.already_sent(chat_id, content["id"]):
        return
    # TODO: handle images and gifs
    try:
        is_post = content["kind"] == "t3"
        if is_post:
            formatted_post = reddit_adapter.formatted_post(content)
        else:
            formatted_post = reddit_adapter.formatted_comment(content)
        sent = False
        if is_post and await media_handler.contains_media(content["url"]):
            sent = await send_media(chat_id, content["url"], formatted_post)
        else:
            sent = await send_message(chat_id, formatted_post, parse_mode="HTML")
        if sent:
            subscriptions_manager.mark_as_sent(chat_id, content["id"], subreddit)
    except Exception as e:
        logging.error(f"{e!r} while sending content, sleeping")
        await send_exception(e, f"Uncaught sending {str(content)} to {chat_id}")
        # If I'm doing something wrong or telegram is down, at least wait a bit
        await asyncio.sleep(60 * 2)
