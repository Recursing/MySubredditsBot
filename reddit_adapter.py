import re
import httpx
import json
import urllib.parse
import asyncio
from typing import List, Dict
from datetime import datetime


def format_time_delta(delta_seconds: int) -> str:
    delta_seconds = int(delta_seconds)
    hours = delta_seconds // 3600
    minutes = (delta_seconds % 3600) // 60
    seconds = delta_seconds % 60
    if hours:
        return f"{hours}h {minutes}m"
    elif minutes:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


def markdown_to_html(source: str) -> str:
    replace_map = {"<": "&lt;", ">": "&gt;", "&": "&amp;"}
    for k, v in replace_map.items():
        source = source.replace(k, v)
    bold_md = r"\*\*(.*?)\*\*"
    bold_html = r"<b>\1</b>"
    link_md = r"\[(.*?)\]\((.*?)\)"
    link_html = r"<a href=\1>\2</a>"
    source = re.sub(bold_md, bold_html, source)
    source = re.sub(link_md, link_html, source)
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
        "{}+ Comments</a> - Posted {} ago\n\n{}"
    )
    if len(post["selftext"]) > 990:
        post["selftext"] = post["selftext"][:990] + "..."
    post["selftext"] = markdown_to_html(post["selftext"])
    return template.format(
        sub,
        urllib.parse.quote(post["url"], safe="/:?="),
        title,
        permalink,
        comment_number,
        time_ago,
        post["selftext"],
    )


class SubredditBanned(Exception):
    pass


class SubredditPrivate(Exception):
    pass


class SubredditEmpty(Exception):
    pass


class InvalidAnswerFromEndpoint(Exception):
    pass


async def get_posts_from_endpoint(endpoint: str, retry=True) -> List[Dict]:
    headers = {"user-agent": "my-subreddits-bot-0.1"}
    client = httpx.AsyncClient()
    try:
        r = await client.get(endpoint, headers=headers, timeout=60)
    except httpx.exceptions.ConnectTimeout:
        if retry:
            await asyncio.sleep(2 * 60)
            await get_posts_from_endpoint(endpoint, retry=False)
        else:
            return []
    try:
        r_json = dict(r.json())
    except json.decoder.JSONDecodeError:
        if retry:
            await asyncio.sleep(2 * 60)
            return await get_posts_from_endpoint(endpoint, retry=False)
        else:
            raise InvalidAnswerFromEndpoint(
                f"{endpoint} returned invalid json: {r.text}"
            )
    if "data" in r_json:
        posts = [p["data"] for p in r_json["data"]["children"] if p["kind"] == "t3"]
        if posts:
            return posts
        else:
            raise SubredditEmpty()
    elif "error" in r_json:
        if r_json["reason"] == "banned":
            raise SubredditBanned()
        if r_json["reason"] == "private":
            raise SubredditPrivate()
    raise Exception(f"{r_json}")


async def new_posts(subreddit: str, limit: int = 15) -> List[Dict]:
    endpoint = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}"
    return await get_posts_from_endpoint(endpoint)


async def top_day_posts(subreddit: str, limit: int = 15) -> List[Dict]:
    """
        Returns top posts of this day on the subreddit
        Returns empty list if subreddit doesn't exist
    """
    endpoint = f"https://www.reddit.com/r/{subreddit}/top.json?t=day&limit={limit}"
    return await get_posts_from_endpoint(endpoint)


async def get_threshold(subreddit: str, monthly_rank: int = 50) -> int:
    endpoint = (
        f"https://www.reddit.com/r/{subreddit}/top.json?t=month&limit={monthly_rank}"
    )
    posts = await get_posts_from_endpoint(endpoint)
    return posts[-1]["score"]


async def check_subreddit(subreddit: str):
    await new_posts(subreddit)


def valid_subreddit(text: str) -> bool:
    pattern = r"\A[A-Za-z0-9][A-Za-z0-9_]{2,20}\Z"
    return bool(re.match(pattern, text))
