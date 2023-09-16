import asyncio
import logging
import time
from typing import Any

import reddit_adapter
import subscriptions_manager
import telegram_adapter


async def send_subscription_update(subreddit: str, chat_id: int, per_month: int):
    # Send top unsent post from subreddit to chat_id
    # per_month is used only to choose where to look for posts (see get_posts)
    try:
        posts = reddit_adapter.get_posts(subreddit, per_month)
        if per_month > 200:
            posts += reddit_adapter.new_posts(subreddit)
        for post in posts:
            if subscriptions_manager.already_sent(chat_id, post["id"]):
                continue
            if post["created_utc"] < time.time() - 86400 * 90:
                continue
            await telegram_adapter.send_post(chat_id, post, subreddit)
            break
        else:
            logging.info(
                f"No post to send from {subreddit} to {chat_id}, {per_month=}. Halving per_month"
            )
            subscriptions_manager.update_per_month(
                chat_id, subreddit, max(per_month // 2, 1)
            )
            subscriptions_manager.mark_as_sent(
                chat_id, f"no_message_found_at_{time.time()}", subreddit
            )
    except reddit_adapter.SubredditBanned:
        if not subscriptions_manager.already_sent_exception(
            chat_id, subreddit, "banned"
        ):
            await telegram_adapter.send_message(
                chat_id, f"r/{subreddit} has been banned"
            )
            subscriptions_manager.mark_exception_as_sent(chat_id, subreddit, "banned")
        subscriptions_manager.unsubscribe(chat_id, subreddit)
    except reddit_adapter.SubredditPrivate:
        if not subscriptions_manager.already_sent_exception(
            chat_id, subreddit, "private"
        ):
            await telegram_adapter.send_message(
                chat_id, f"r/{subreddit} has been made private"
            )
            subscriptions_manager.mark_exception_as_sent(chat_id, subreddit, "private")
        subscriptions_manager.unsubscribe(chat_id, subreddit)
    except Exception as e:
        logging.error(f"{e!r} while sending sub updates, sleeping")
        await telegram_adapter.send_exception(
            e, f"send_subscription_update({subreddit}, {chat_id}, {per_month})"
        )
        time.sleep(30)


async def check_exceptions(refresh_period: int = 48 * 60 * 60):
    """
    Check whether private or banned subs are now available
    """
    await asyncio.sleep(refresh_period)
    while True:
        unavailable_subs = subscriptions_manager.unavailable_subreddits()
        for sub in unavailable_subs:
            try:
                try:
                    reddit_adapter.new_posts(sub)
                except (
                    reddit_adapter.SubredditPrivate,
                    reddit_adapter.SubredditBanned,
                ):
                    continue
                old_subscribers = subscriptions_manager.get_old_subscribers(sub)
                for chat_id in old_subscribers:
                    subscriptions_manager.subscribe(chat_id, sub, 31)
                    await telegram_adapter.send_message(
                        chat_id, f"{sub} is now available again"
                    )
                subscriptions_manager.delete_exception(sub)
            except Exception as e:
                await telegram_adapter.send_exception(
                    e, f"Exception while checking unavailability of {sub}"
                )
        await asyncio.sleep(refresh_period)

async def send_updates():
    while True:
        (
            subreddit,
            chat_id,
            per_month,
            time_left
        ) = subscriptions_manager.get_next_subscription_to_update()
        logging.info(f"Sending {subreddit=} to {chat_id=} {per_month=} {time_left=}")
        await asyncio.sleep(max(0.01, time_left))
        logging.info(f"Sending {subreddit=} to {chat_id=} {per_month=}")
        await send_subscription_update(subreddit, chat_id, per_month)

tasks = []
async def on_startup(_dispatcher: Any):
    tasks.append(asyncio.create_task(check_exceptions()))
    tasks.append(asyncio.create_task(send_updates()))
