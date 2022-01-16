from __future__ import annotations

import asyncio
import itertools
import logging
import re
import urllib.parse
from datetime import datetime
from typing import Any, Coroutine, List, Literal, Optional, Set, TypedDict

import httpx


class Post(TypedDict):
    kind: Literal["t3"]
    created_utc: int
    id: str
    num_comments: int
    over_18: bool
    permalink: str
    score: int
    selftext: str
    subreddit: str
    title: str
    url: str


class Comment(TypedDict):
    kind: Literal["t1"]
    author: str
    body: str
    created_utc: int
    id: str
    link_title: str
    link_url: str
    num_comments: str
    over_18: bool
    permalink: str
    score: int


def format_time_delta(delta_seconds: float) -> str:
    delta_seconds = int(delta_seconds)
    assert delta_seconds >= 0
    days = delta_seconds // (86400)
    hours = (delta_seconds % 86400) // 3600
    minutes = (delta_seconds % 3600) // 60
    seconds = delta_seconds % 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def markdown_to_html(source: str) -> str:
    source = source.replace("&amp;#x200B;", "").replace("&amp;nbsp;", " ")
    source = source.replace("<", "&lt;").replace(">", "&gt;")
    bold_md = r"\*\*(.*?)\*\*"
    bold_html = r"<b>\1</b>"
    link_md = r"\[([^\]\[]*?)]\((\w[^\s\"]*?)\\?\"?#?\)"
    link_html = r'<a href="\2">\1</a>'
    source = re.sub(link_md, link_html, source)
    source = re.sub(bold_md, bold_html, source)
    return source


def formatted_post(post: Post) -> str:
    """
    TODO: maybe show score and threshold, and subreddit in bold
    """

    title = post["title"].replace("<", "&lt;").replace(">", "&gt;")
    if post["over_18"]:
        title += " - NSFW"

    time_ago = format_time_delta(datetime.now().timestamp() - post["created_utc"])

    if len(post["selftext"]) > 2100:
        post["selftext"] = post["selftext"][:2000] + "..."

    post["selftext"] = markdown_to_html(post["selftext"])
    if len(post["selftext"]) > 3100:
        post["selftext"] = post["selftext"][:3000] + "..."

    template = (
        '{}: <a href="{}">{}</a> - <a href="https://old.reddit.com{}">'
        "{}+ Comments</a> - +{} in {}\n\n{}"
    )
    return template.format(
        post["subreddit"],
        urllib.parse.quote(post["url"], safe="/:?=&#"),
        title,
        post["permalink"],
        post["num_comments"],
        post["score"],
        time_ago,
        post["selftext"],
    )


def formatted_comment(comment: Comment) -> str:

    time_ago = format_time_delta(datetime.now().timestamp() - comment["created_utc"])

    if len(comment["body"]) > 2100:
        comment["body"] = comment["body"][:2000] + "..."

    template = (
        '{} on: <a href="{}">{}</a>'
        "\n\n{}\n\n"
        '<a href="https://old.reddit.com{}?context=4">Context</a> - +{} in {}'
    )

    return template.format(
        comment["author"],
        urllib.parse.quote(comment["link_url"], safe="/:?=&#"),
        comment["link_title"],
        markdown_to_html(comment["body"]),
        comment["permalink"],
        comment["score"],
        time_ago,
    )


class SubredditBanned(Exception):
    pass


class SubredditPrivate(Exception):
    pass


class InvalidAnswerFromEndpoint(Exception):
    pass


CLIENT_SESSION = httpx.AsyncClient()


async def get_posts_from_endpoint(
    endpoint: str, retry: bool = True
) -> List[Post | Comment]:
    headers = {"user-agent": "my-subreddits-bot-0.1"}
    r_json = None
    response = None
    try:
        response = await CLIENT_SESSION.get(endpoint, headers=headers, timeout=60)
        r_json = response.json()
        if not isinstance(r_json, dict):
            raise InvalidAnswerFromEndpoint()
    except Exception as e:
        if retry:
            logging.info(f"{e!r} sleeping 60 seconds before retrying contacting reddit")
            await asyncio.sleep(60)
            return await get_posts_from_endpoint(endpoint, retry=False)
        raise InvalidAnswerFromEndpoint(f"{endpoint} returned invalid json {response}")
    if "data" in r_json:
        children: Any = r_json["data"]["children"]
        for child in children:
            child["data"]["kind"] = child["kind"]
        return [c["data"] for c in children if c["kind"] in ("t1", "t3")]
    if "error" in r_json and "reason" in r_json:
        if r_json["reason"] == "banned" or r_json["reason"] == "quarantined":
            raise SubredditBanned()
        if r_json["reason"] == "private":
            raise SubredditPrivate()
    raise Exception(f"{r_json} on {endpoint}")


BASE_URL = "https://www.reddit.com"


def is_subreddit(subscription: str) -> bool:
    if subscription[:2] not in ("u/", "r/"):
        raise ValueError(f"Invalid subscription {subscription}")
    return subscription.startswith("r/")


async def hot_posts(subscription: str, limit: int = 30) -> List[Post | Comment]:
    endpoint = f"{BASE_URL}/{subscription}/hot.json?limit={limit}"
    return await get_posts_from_endpoint(endpoint)


async def new_posts(subscription: str, limit: int = 30) -> List[Post | Comment]:
    endpoint = f"{BASE_URL}/{subscription}/new.json?limit={limit}"
    return await get_posts_from_endpoint(endpoint)


async def get_top_posts(
    subscription: str, time_period: str, limit: int
) -> List[Post | Comment]:
    if is_subreddit(subscription):
        endpoint = f"{BASE_URL}/{subscription}/top.json?t={time_period}&limit={limit}"
    else:
        subscription = subscription.replace("u/", "user/")
        endpoint = (
            f"{BASE_URL}/{subscription}.json?sort=top&t={time_period}&limit={limit}"
        )
    return await get_posts_from_endpoint(endpoint)


async def get_posts(subscription: str, per_month: int) -> List[Post | Comment]:
    tasks: List[Coroutine[Any, Any, List[Post | Comment]]] = []
    if per_month < 99:
        tasks.append(get_top_posts(subscription, "month", per_month))
    if per_month // 4 < 99:
        limit = per_month // 4
        tasks.append(get_top_posts(subscription, "week", limit))
    if per_month // 31 < 99:
        limit = per_month // 31
        tasks.append(get_top_posts(subscription, "day", limit))
    if is_subreddit(subscription):
        tasks.append(hot_posts(subscription, min(per_month // 10, 99)))

    posts: List[Post | Comment] = list(
        itertools.chain.from_iterable(await asyncio.gather(*tasks))
    )

    def get_score(post: Post | Comment):
        return post["score"]

    posts.sort(key=get_score, reverse=True)

    seen_ids: Set[str] = set()
    unique_posts: List[Post | Comment] = []
    for post in posts:
        if post["id"] in seen_ids:
            continue
        seen_ids.add(post["id"])
        unique_posts.append(post)
    return unique_posts


# from https://github.com/reddit-archive/reddit/blob/753b17407e9a9dca09558526805922de24133d53/r2/r2/lib/validator/validator.py#L1570-L1571
user_rx = re.compile(r"\Au/[\w-]{3,20}\Z", re.UNICODE)
# from https://github.com/reddit-archive/reddit/blob/753b17407e9a9dca09558526805922de24133d53/r2/r2/models/subreddit.py#L114
subreddit_rx = re.compile(r"\Ar/[A-Za-z0-9][A-Za-z0-9_]{2,20}\Z")


def valid_subscription(text: str) -> bool:
    return bool(subreddit_rx.fullmatch(text) or user_rx.fullmatch(text))


async def get_posts_error(sub: str, monthly_rank: int) -> Optional[str]:
    if not valid_subscription(sub):
        return f"{sub} is not a valid subreddit or user name"
    try:
        posts = await get_posts(sub, monthly_rank)
        if posts and sum(post["over_18"] for post in posts) / len(posts) >= 0.8:
            return f"{sub} seems to be a porn subreddit, if that's not the case contact @recursing"
        if not posts:
            return f"{sub} does not exist or is empty or something"
    except SubredditBanned:
        return f"{sub} has been banned"
    except SubredditPrivate:
        return f"{sub} is private"
