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


async def formatted_post(post: Dict[str, Any]) -> str:
    """
        Returns the message to send, with Telegram-style pesudo-HTML markup
    """
    screen_name = post["user"]["screen_name"]
    permalink = f"https://www.twitter.com/{screen_name}/status/{post['id']}"
    text = post.get("full_text") or post.get("text") or ""
    if post.get("retweeted_status"):
        op = post["retweeted_status"]
        op_name = op["user"]["screen_name"]
        permalink = f"https://www.twitter.com/{op_name}/status/{op['id']}"
        rt_text = op.get("full_text") or op.get("text") or ""
        text = f"<b>Retweet from {op_name}</b>: \n{rt_text}"
    text = re.sub(
        r"(^|[^@\w])@(\w{1,20})\b",
        '\\1<a href="http://twitter.com/\\2">@\\2</a>',
        text,
    )
    if post["in_reply_to_screen_name"]:
        try:
            original_post = await get_post(post["in_reply_to_status_id"])
            elapsed_time = (
                datetime.now().timestamp()
                - dateutil.parser.parse(original_post["created_at"]).timestamp()
            )
            original_text = original_post.get("full_text") or post.get("text")
            pretext = f'<b>Reply to: {original_post["user"]["name"]}</b> • {format_time_delta(elapsed_time)} ago: \n<i> {original_text} </i>\n\n\n'
        except KeyError as e:
            logging.error(f"Error forrmatting original from {post} {e!r}")
            pretext = f"<b>Reply: </b>"
        text = f"{pretext}{text}"
    if post.get("entities") and post["entities"].get("urls"):
        for url in post["entities"]["urls"]:
            text = text.replace(url["url"], url["expanded_url"])
    if post.get("extended_entities") and post["extended_entities"]:
        for media in post["extended_entities"]["media"]:
            text = text.replace(media["url"], media["expanded_url"])

    message = (
        f'<b>{post["user"]["name"]}</b> '
        f' • <a href="{permalink}">{format_time_delta(post["seconds_ago"])} ago</a>:\n\n{text}'
    )
    return message


async def get_post(post_id: str) -> Dict[str, Any]:
    endpoint = "https://api.twitter.com/1.1/statuses/show.json?id={post_id}&tweet_mode=extended"
    r = await CLIENT_SESSION.get(endpoint)
    post = r.json()
    r.close()
    return post


async def get_user_activity(user: str) -> List[Dict[str, Any]]:
    """
        Call the twitter API to get the last tweets, extended is required to get the full text
    """
    tweet_number = 100
    r = await CLIENT_SESSION.get(
        f"https://api.twitter.com/1.1/statuses/user_timeline.json"
        f"?screen_name={user}&count={tweet_number}&tweet_mode=extended",
    )
    posts = r.json()
    r.close()
    return posts


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
