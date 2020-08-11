"""
Handle communication with the twitter API
"""
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import dateutil.parser
from authlib.integrations.httpx_client import AsyncOAuth1Client

import credentials

CLIENT_SESSION = AsyncOAuth1Client(
    credentials.API_KEY,
    credentials.API_SECRET,
    credentials.ACCESS_TOKEN,
    credentials.ACCESS_TOKEN_SECRET,
)


def format_time_delta(delta_seconds: float) -> str:
    """
        Returns a human readable string from a time difference given in seconds
        >>> format_time_delta(4758)
        ... '1h 19m 18s'
    """
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


def formatted_post(post: Dict[str, Any]) -> str:
    """
        Returns the message to send, with Telegram-style pesudo-HTML markup
    """
    screen_name = post["user"]["screen_name"]
    permalink = f"https://www.twitter.com/{screen_name}/status/{post['id']}"
    if hasattr(post, "retweeted_status"):
        post["full_text"] = post["retweeted_status"]["full_text"]
    text = re.sub(
        r"(^|[^@\w])@(\w{1,20})\b",
        '\\1<a href="http://twitter.com/\\2">@\\2</a>',
        post["full_text"],
    )
    if post["in_reply_to_screen_name"]:
        text = "Reply: " + text
    if hasattr(post, "entities") and post["entities"].get("urls"):
        for url in post["entities"]["urls"]:
            text = text.replace(url["url"], url["expanded_url"])
    if hasattr(post, "extended_entities") and post["extended_entities"]:
        for media in post["extended_entities"]["media"]:
            text = text.replace(media["url"], "")
            text = f'<a href="{media["expanded_url"]}">{media["type"]}</a>\n' + text

    message = (
        f'<b>{post["user"]["name"]}</b> • <a href="https://twitter.com/{screen_name}">@{screen_name}</a>'
        f' • <a href="{permalink}">{format_time_delta(post["seconds_ago"])} ago</a>:\n\n{text}'
    )
    return message


async def get_user_activity(user: str) -> List[Dict[str, Any]]:
    """
        Call the twitter API to get the last tweets, extended is required to get the full text
    """
    tweet_number = 100
    r = await CLIENT_SESSION.get(
        f"https://api.twitter.com/1.1/statuses/user_timeline.json"
        f"?screen_name={user}&count={tweet_number}&tweet_mode=extended",
    )
    return r.json()


async def new_posts(user: str) -> List[Dict[str, Any]]:
    """
        Get most recent tweets of user
        Returns a list of dictionaries with the tweet attributes,
        see https://developer.twitter.com/en/docs/tweets/data-dictionary/overview/tweet-object
        it adds a score attribute (favorites + retweets: int) and an has_media attribute (bool)
    """

    # call the API asynchronously
    user_act = await get_user_activity(user)

    # I think it might have happened a couple of times
    # if it doesn't happen again I'm planning to remove this
    if not isinstance(user_act, list):
        logger = logging.getLogger(__name__)
        logger.error("USER ACTIVITY IS NOT A LIST")
        logger.error(user_act)
        return []

    for post in user_act:
        post["score"] = post["favorite_count"] + post["retweet_count"]
        post["has_media"] = post.get("extended_entities", {}).get("media")
        created_datetime = dateutil.parser.parse(post["created_at"])
        elapsed_time = datetime.now().timestamp() - created_datetime.timestamp()
        post["seconds_ago"] = elapsed_time

    user_act.sort(key=lambda p: p["score"], reverse=True)

    return user_act


async def get_posts_error(user: str) -> Optional[str]:
    try:
        posts = await new_posts(user)
        if posts:
            return None
        else:
            return "No posts"
    except Exception as e:
        return f"Got Exception {e!r}"
