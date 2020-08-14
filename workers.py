import asyncio
import logging
import random
import time
from datetime import datetime
from typing import Dict, Tuple

import subscriptions_manager
import telegram_adapter
import twitter_adapter


async def send_subscription_update(subreddit: str, chat_id: int, per_month: int):
    # Send top unsent post from subreddit to chat_id
    # per_month is used only to choose where to look for posts (see get_posts)
    period = 3600 * 24 * 31 / per_month
    try:
        post_iterator = await twitter_adapter.new_posts(subreddit)
        for post in post_iterator:
            if subscriptions_manager.already_sent(chat_id, post["id"]):
                continue
            if post["seconds_ago"] > period * 30:
                continue
            await telegram_adapter.send_post(chat_id, post)
            break
        else:
            logging.info(f"No post to send from {subreddit} to {chat_id}, {per_month=}")
    except Exception as e:
        logging.error(f"{e!r} while sending sub updates, sleeping")
        await telegram_adapter.send_exception(
            e, f"send_subscription_update({subreddit}, {chat_id}, {per_month})"
        )
        time.sleep(60 * 2)


async def make_worker(chat_id: int, subreddit: str, per_month: int):
    period = 3600 * 24 * 31 / per_month

    # Randomize the period a few seconds to prevent workers to sync up
    period += random.random() * 10 - 5
    # Before the first run sleep randomly a bit to offset the worker
    init_sleep = random.random() * period / 10
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
    workers[(chat_id, subreddit)] = asyncio.create_task(
        make_worker(chat_id, subreddit, per_month)
    )


def start_workers():
    logging.info(f"{datetime.now()} Starting workers...")
    subscriptions = subscriptions_manager.get_subscriptions()
    if len(subscriptions) == 0:
        print("Warning: no subscriptions...")
        subscriptions = subscriptions_manager.get_subscriptions()
        time.sleep(10)
    random.shuffle(subscriptions)
    for chat_id, subreddit, per_month in subscriptions:
        workers[(chat_id, subreddit)] = asyncio.create_task(
            make_worker(chat_id, subreddit, per_month)
        )


async def on_startup(_dispatcher):
    start_workers()
