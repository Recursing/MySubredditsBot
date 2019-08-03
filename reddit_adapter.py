import re
import httpx
import json
import urllib.parse
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
        "{}+ Comments</a> - Posted {} ago"
    )
    return template.format(
        sub,
        urllib.parse.quote(post["url"], safe="/:?="),
        title,
        permalink,
        comment_number,
        time_ago,
    )


class SubredditBanned(Exception):
    pass


class SubredditEmpty(Exception):
    pass


class InvalidAnswerFromEndpoint(Exception):
    pass


async def get_posts_from_endpoint(endpoint: str) -> List[Dict]:
    client = httpx.AsyncClient()
    r = await client.get(endpoint)
    try:
        r_json = r.json()
    except json.decoder.JSONDecodeError:
        raise InvalidAnswerFromEndpoint(f"{endpoint} return invalid json:\n{r.text}")
    if "data" in r_json:
        posts = [p["data"] for p in r_json["data"]["children"] if p["kind"] == "t3"]
        if posts:
            return posts
        else:
            raise SubredditEmpty()
    elif "error" in r_json:
        if r_json["reason"] == "banned":
            raise SubredditBanned()
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


async def check_exists(subreddit: str):
    if not valid_subreddit(subreddit):
        return False
    await new_posts(subreddit)
    return True


def valid_subreddit(text: str):
    pattern = r"\A[A-Za-z0-9][A-Za-z0-9_]{2,20}\Z"
    return bool(re.match(pattern, text))
