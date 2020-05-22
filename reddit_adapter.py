import asyncio
import re
import urllib.parse
from datetime import datetime
from time import time
from typing import Dict, List, Tuple, Union

import httpx

from bot import log_exception


def format_time_delta(delta_seconds: int) -> str:
    delta_seconds = int(delta_seconds)
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
    bold_md = r"\*\*(.*?)\*\*"
    bold_html = r"<b>\1</b>"
    link_md = r"\[(.*?)]\((.*?)\)"
    link_html = r'<a href="\2">\1</a>'
    source = re.sub(link_md, link_html, source)
    source = re.sub(bold_md, bold_html, source)
    return source


def formatted_post(post: Dict) -> str:
    """
       TODO: maybe show score and threshold, and subreddit in bold
    """
    sub = post["subreddit"]

    title = post["title"].replace("<", "&lt;").replace(">", "&gt;")
    permalink = post["permalink"]
    time_ago = format_time_delta(datetime.now().timestamp() - post["created_utc"])
    comment_number = post["num_comments"]
    if post["over_18"]:
        title += " - NSFW"

    template = (
        '{}: <a href="{}">{}</a> - <a href="https://www.reddit.com{}">'
        "{}+ Comments</a> - +{} in {}\n\n{}"
    )
    if len(post["selftext"]) > 1100:
        post["selftext"] = post["selftext"][:1000] + "..."

    post["selftext"] = markdown_to_html(post["selftext"])
    if len(post["selftext"]) > 2000:
        post["selftext"] = post["selftext"][:1900] + "..."
    return template.format(
        sub,
        urllib.parse.quote(post["url"], safe="/:?=&#"),
        title,
        permalink,
        comment_number,
        post["score"],
        time_ago,
        post["selftext"],
    )


class SubredditBanned(Exception):
    pass


class SubredditPrivate(Exception):
    pass


class InvalidAnswerFromEndpoint(Exception):
    pass


Post = Dict[str, Union[int, str]]
CLIENT_SESSION = httpx.AsyncClient()
TIMED_CACHE: Dict[str, Tuple[float, List[Post]]] = {}


async def get_posts_from_endpoint(endpoint: str, retry=True) -> List[Post]:
    if endpoint in TIMED_CACHE and TIMED_CACHE[endpoint][0] > time() - 600:
        return TIMED_CACHE[endpoint][1]
    headers = {"user-agent": "my-subreddits-bot-0.1"}
    r_json = None
    try:
        response = await CLIENT_SESSION.get(endpoint, headers=headers, timeout=60)
        r_json = response.json()
    except Exception as e:
        log_exception(e, f"Exception getting endpoint {endpoint} {r_json} {e!r}")
        if retry:
            print("sleeping 60 seconds before retrying contacting reddit")
            await asyncio.sleep(60)
            return await get_posts_from_endpoint(endpoint, retry=False)
        raise InvalidAnswerFromEndpoint(f"{endpoint} returned invalid json")
    if not isinstance(r_json, dict):
        if retry:
            print("sleeping 60 seconds before retrying contacting reddit")
            await asyncio.sleep(60)
            return await get_posts_from_endpoint(endpoint, retry=False)
        raise InvalidAnswerFromEndpoint(f"{endpoint} returned invalid json")
    if "data" in r_json:
        posts = [p["data"] for p in r_json["data"]["children"] if p["kind"] == "t3"]
        TIMED_CACHE[endpoint] = (time(), posts)
        if len(TIMED_CACHE) > 100000:
            TIMED_CACHE.clear()
            TIMED_CACHE[endpoint] = (time(), posts)
        return posts
    if "error" in r_json and "reason" in r_json:
        if r_json["reason"] == "banned" or r_json["reason"] == "quarantined":
            raise SubredditBanned()
        if r_json["reason"] == "private":
            raise SubredditPrivate()
    raise Exception(f"{r_json}")


async def new_posts(subreddit: str, limit: int = 30) -> List[Dict]:
    endpoint = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}"
    return await get_posts_from_endpoint(endpoint)


async def get_posts(subreddit: str, per_month: int) -> List[Dict]:
    base = "https://www.reddit.com/r/"
    if per_month < 99:
        limit = per_month
        time_period = "month"
    elif per_month // 4 < 99:
        limit = per_month // 4
        time_period = "week"
    elif per_month // 31 < 99:
        limit = per_month // 31
        time_period = "day"
    else:
        limit = min(per_month // (31 * 24), 99)
        time_period = "hour"
    endpoint = f"{base}{subreddit}/top.json?t={time_period}&limit={limit}"
    return (await get_posts_from_endpoint(endpoint))[:limit]


async def check_subreddit(subreddit: str):
    await new_posts(subreddit)


def valid_subreddit(text: str) -> bool:
    pattern = r"\A[A-Za-z0-9][A-Za-z0-9_]{2,20}\Z"
    return bool(re.match(pattern, text))
