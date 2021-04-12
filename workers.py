import asyncio
import logging
import random
import time
from datetime import datetime
from typing import Dict, Tuple, Optional

import reddit_adapter
import subscriptions_manager
import telegram_adapter


async def send_subscription_update(subreddit: str, chat_id: int, per_month: int):
    # Send top unsent post from subreddit to chat_id
    # per_month is used only to choose where to look for posts (see get_posts)
    try:
        post_iterator = await reddit_adapter.get_posts(subreddit, per_month)
        if per_month > 1000:
            post_iterator += await reddit_adapter.new_posts(subreddit)
        for post in post_iterator:
            if subscriptions_manager.already_sent(chat_id, post["id"]):
                continue
            if post["created_utc"] < time.time() - 86400 * 40:
                continue
            await telegram_adapter.send_post(chat_id, post, subreddit)
            break
        else:
            logging.info(f"No post to send from {subreddit} to {chat_id}, {per_month=}")
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
        time.sleep(60 * 2)


async def make_worker(
    chat_id: int, subreddit: str, per_month: int, last_message: Optional[datetime]
):
    period = 3600 * 24 * 31 / per_month

    # Randomize the period a few seconds to prevent workers to sync up
    period += random.random() * 10 - 5
    # Before the first run sleep randomly a bit to offset the worker
    if not last_message:
        init_sleep = random.random() * period / 2
    else:
        already_elapsed = (datetime.utcnow() - last_message).total_seconds()
        init_sleep = max(random.random() * 30, period - already_elapsed)
    t0 = time.monotonic()
    print(f"{chat_id}, {subreddit}, {per_month}, {period=}, {init_sleep=:.2f}")
    await asyncio.sleep(init_sleep)
    elapsed = time.monotonic() - t0
    print(
        f"{chat_id}, {subreddit} starting to send, slept {elapsed=:.2f} vs {init_sleep=:.2f}"
    )
    while True:
        t0 = time.monotonic()
        await send_subscription_update(subreddit, chat_id, per_month)
        elapsed = time.monotonic() - t0
        await asyncio.sleep(period - elapsed)
        elapsed = time.monotonic() - t0
        logging.info(
            f"{elapsed=:.2f}s vs {period=:.2f} for woker {chat_id} {subreddit} {per_month}"
        )


workers: Dict[Tuple[int, str], asyncio.Task] = {}


def stop_worker(chat_id, subreddit):
    try:
        print(f"stopping {chat_id} {subreddit}")
        workers[(chat_id, subreddit)].cancel()
        del workers[(chat_id, subreddit)]
    except Exception as e:
        logging.error(f"Cannot stop worker ({chat_id}, {subreddit}), {e!r}")
        asyncio.create_task(
            telegram_adapter.send_exception(
                e, f"Cannot stop worker ({chat_id}, {subreddit})"
            )
        )


def start_worker(chat_id, subreddit, per_month):
    if (chat_id, subreddit) in workers:
        stop_worker(chat_id, subreddit)
    last_message = subscriptions_manager.get_last_subscription_message(
        chat_id, subreddit
    )
    workers[(chat_id, subreddit)] = asyncio.create_task(
        make_worker(chat_id, subreddit, per_month, last_message)
    )


def start_workers():
    logging.info(f"{datetime.now()} Starting workers...")
    subscriptions = subscriptions_manager.get_subscriptions()
    while len(subscriptions) == 0:
        print("Waiting for subscriptions...")
        subscriptions = subscriptions_manager.get_subscriptions()
        time.sleep(10)
    random.shuffle(subscriptions)
    for chat_id, subreddit, per_month in subscriptions:
        last_message = subscriptions_manager.get_last_subscription_message(
            chat_id, subreddit
        )
        print("Making worker: ", chat_id, subreddit, per_month, last_message)
        workers[(chat_id, subreddit)] = asyncio.create_task(
            make_worker(chat_id, subreddit, per_month, last_message)
        )


async def check_exceptions(refresh_period=24 * 60 * 60):
    """
        Check whether private or banned subs are now available
    """
    while True:
        unavailable_subs = subscriptions_manager.unavailable_subreddits()
        for sub in unavailable_subs:
            try:
                try:
                    await reddit_adapter.new_posts(sub)
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


async def on_startup(_dispatcher):
    start_workers()
    asyncio.create_task(check_exceptions())
