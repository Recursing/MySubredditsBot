import asyncio
import logging
import re
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional, Union

import httpx


def format_time_delta(delta_seconds: float) -> str:
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
    source = source.replace("<", "&lt;").replace(">", "&gt;")
    bold_md = r"\*\*(.*?)\*\*"
    bold_html = r"<b>\1</b>"
    link_md = r"\[([^\]\[]*?)]\((\w[^\s\"]*?)\\?\"?#?\)"
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
        '{}: <a href="{}">{}</a> - <a href="https://old.reddit.com{}">'
        "{}+ Comments</a> - +{} in {}\n\n{}"
    )
    if len(post["selftext"]) > 2100:
        post["selftext"] = post["selftext"][:2000] + "..."

    post["selftext"] = markdown_to_html(post["selftext"])
    if len(post["selftext"]) > 3100:
        post["selftext"] = post["selftext"][:3000] + "..."
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


async def get_posts_from_endpoint(endpoint: str, retry=True) -> List[Post]:
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
        posts = [p["data"] for p in r_json["data"]["children"] if p["kind"] == "t3"]
        return posts
    if "error" in r_json and "reason" in r_json:
        if r_json["reason"] == "banned" or r_json["reason"] == "quarantined":
            raise SubredditBanned()
        if r_json["reason"] == "private":
            raise SubredditPrivate()
    raise Exception(f"{r_json}")


async def hot_posts(subreddit: str, limit: int = 30) -> List[Dict]:
    endpoint = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    return await get_posts_from_endpoint(endpoint)


async def new_posts(subreddit: str, limit: int = 30) -> List[Dict]:
    endpoint = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}"
    return await get_posts_from_endpoint(endpoint)


async def get_top_posts(subreddit: str, time_period: str, limit: int) -> List[Dict]:
    endpoint = (
        f"https://www.reddit.com/r/{subreddit}/top.json?t={time_period}&limit={limit}"
    )
    return await get_posts_from_endpoint(endpoint)


async def get_posts(subreddit: str, per_month: int) -> List[Dict]:
    posts: List[Dict] = []
    if per_month < 99:
        posts.extend(await get_top_posts(subreddit, "month", per_month))
    if per_month // 4 < 99:
        limit = per_month // 4
        posts.extend(await get_top_posts(subreddit, "week", limit))
    if per_month // 31 < 99:
        limit = per_month // 31
        posts.extend(await get_top_posts(subreddit, "day", limit))

    posts.extend(await hot_posts(subreddit, min(per_month // 10, 99)))

    def get_score(post):
        return post["score"]

    posts.sort(key=get_score, reverse=True)

    seen_ids = set()
    unique_posts = []
    for post in posts:
        if post["id"] in seen_ids:
            continue
        seen_ids.add(post["id"])
        unique_posts.append(post)
    return unique_posts


def valid_subreddit(text: str) -> bool:
    pattern = r"\A[A-Za-z0-9][A-Za-z0-9_]{2,20}\Z"
    return bool(re.match(pattern, text))


async def get_posts_error(sub: str, monthly_rank: int) -> Optional[str]:
    if not valid_subreddit(sub):
        return f"{sub} is not a valid subreddit name"
    try:
        posts = await get_posts(sub, monthly_rank)
        if posts and sum(post["over_18"] for post in posts) / len(posts) >= 0.8:
            return f"r/{sub} seems to be a porn subreddit, if that's not the case contact @recursing"
        if posts:
            return None
        return f"r/{sub} does not exist or is empty or something"
    except SubredditBanned:
        return f"r/{sub} has been banned"
    except SubredditPrivate:
        return f"r/{sub} is private"
