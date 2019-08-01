import logging
import sqlite3
from typing import List

logger = logging.getLogger(__name__)

DB = sqlite3.connect("subscriptions.db", isolation_level=None)


def create_tables():
    c = DB.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS subscriptions (
            chat_id INTEGER NOT NULL,
            subreddit TEXT NOT NULL,
            threshold INTEGER NOT NULL,
            per_month INTEGER NOT NULL,
            PRIMARY KEY (chat_id, subreddit)
        );"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS messages (
            chat_id INTEGER NOT NULL,
            post_id TEXT NOT NULL,
            PRIMARY KEY (chat_id, post_id)
        );"""
    )


create_tables()


logger.info("Connected! (Hopefully)")


def subscribe(chat_id: int, subreddit: str, threshold: int, monthly_rank: int) -> bool:
    """
        return false if the user is already subscribed
    """
    c = DB.cursor()
    # try to update, if not found insert
    c.execute(
        "SELECT * FROM subscriptions WHERE chat_id=? AND subreddit=?",
        (chat_id, subreddit),
    )
    if c.fetchone():
        return False

    c.execute(
        "INSERT INTO subscriptions VALUES (?,?,?,?)",
        (chat_id, subreddit, threshold, monthly_rank),
    )
    return True


def unsubscribe(chat_id: int, subreddit: str):
    """
        returns False if there is no matching subscription
    """
    c = DB.cursor()
    c.execute(
        "DELETE FROM subscriptions WHERE chat_id=? AND subreddit=?",
        (chat_id, subreddit),
    )


def update_threshold(
    chat_id: int, subreddit: str, new_threshold: int, new_monthly_rank: int
):
    c = DB.cursor()
    c.execute(
        "UPDATE subscriptions SET threshold=?, per_month=? WHERE chat_id=? AND subreddit=?",
        (new_threshold, new_monthly_rank, chat_id, subreddit),
    )


def get_per_month(chat_id: int, subreddit: str) -> int:
    c = DB.cursor()
    c.execute(
        "SELECT per_month FROM subscriptions WHERE chat_id=? AND subreddit=?",
        (chat_id, subreddit),
    )
    return c.fetchone()[0]


def all_subreddits() -> List[str]:
    c = DB.cursor()
    c.execute("SELECT DISTINCT subreddit FROM subscriptions")
    return [sub for (sub,) in c.fetchall()]


def sub_followers(subreddit: str):
    c = DB.cursor()
    c.execute(
        "SELECT chat_id, threshold FROM subscriptions WHERE subreddit=?", (subreddit,)
    )
    for row in c.fetchall():
        yield row


def user_thresholds(chat_id: int):
    c = DB.cursor()
    c.execute(
        "SELECT subreddit, threshold FROM subscriptions WHERE chat_id=?", (chat_id,)
    )
    for row in c.fetchall():
        yield row


def user_subscriptions(chat_id: int):
    c = DB.cursor()
    c.execute(
        "SELECT subreddit, threshold, per_month FROM subscriptions WHERE chat_id=?",
        (chat_id,),
    )
    for row in c.fetchall():
        yield row


"""
def store_post(post_id, title, current_score, post_time, current_time, subreddit):
    row = {
        "post_id": post_id,
        "title": title,
        "score": current_score,
        "score_time": current_time,
        "post_time": post_time,
        "subreddit": subreddit,
    }
    DB['post_history'].insert(row)
    pass
"""


def already_sent(chat_id: int, post_id: str) -> bool:
    c = DB.cursor()
    c.execute(
        "SELECT * FROM messages WHERE chat_id=? AND post_id=?", (chat_id, post_id)
    )
    return bool(c.fetchone())


def mark_as_sent(chat_id: int, post_id: str):
    c = DB.cursor()
    c.execute("INSERT INTO messages VALUES (?,?)", (chat_id, post_id))


def commit():
    DB.commit()
