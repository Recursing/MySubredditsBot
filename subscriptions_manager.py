import logging
import sqlite3
from typing import List, Tuple, Union

logger = logging.getLogger(__name__)

DB = sqlite3.connect("subscriptions.db", isolation_level=None)


def exec_sql(
    query: str, parameters: Tuple[Union[str, int], ...] = ()
) -> sqlite3.Cursor:
    cursor = DB.cursor()
    assert query.count("?") == len(parameters)
    cursor.execute(query, parameters)
    return cursor


def create_tables():
    exec_sql(
        """CREATE TABLE IF NOT EXISTS subscriptions (
            chat_id INTEGER NOT NULL,
            subreddit TEXT NOT NULL,
            per_month INTEGER NOT NULL,
            PRIMARY KEY (chat_id, subreddit)
        );"""
    )
    exec_sql(
        """CREATE TABLE IF NOT EXISTS messages (
            chat_id INTEGER NOT NULL,
            post_id TEXT NOT NULL,
            PRIMARY KEY (chat_id, post_id)
        );"""
    )
    exec_sql(
        """CREATE TABLE IF NOT EXISTS exceptions (
            subreddit TEXT NOT NULL,
            reason TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            PRIMARY KEY (chat_id, subreddit, reason)
        );"""
    )


create_tables()


logger.info("Connected! (Hopefully)")


def subscribe(chat_id: int, subreddit: str, monthly_rank: int) -> bool:
    """
        return false if the user is already subscribed
    """
    # try to subscribe, if not found insert
    if is_subscribed(chat_id, subreddit):
        return False

    exec_sql(
        "INSERT INTO subscriptions VALUES (?,?,?)", (chat_id, subreddit, monthly_rank),
    )
    return True


def is_subscribed(chat_id: int, subreddit: str) -> bool:
    # try to update, if not found insert
    cursor = exec_sql(
        "SELECT * FROM subscriptions WHERE chat_id=? AND subreddit=?",
        (chat_id, subreddit),
    )
    return bool(cursor.fetchone())


def unsubscribe(chat_id: int, subreddit: str) -> bool:
    """
        returns False if there is no matching subscription
    """
    cursor = exec_sql(
        "DELETE FROM subscriptions WHERE chat_id=? AND subreddit=?",
        (chat_id, subreddit),
    )
    return bool(cursor.rowcount)


def update_per_month(chat_id: int, subreddit: str, new_monthly_rank: int):
    exec_sql(
        "UPDATE subscriptions SET per_month=? " " WHERE chat_id=? AND subreddit=?",
        (new_monthly_rank, chat_id, subreddit),
    )


def get_subscriptions() -> List[Tuple[int, str, int]]:
    cursor = exec_sql("SELECT chat_id, subreddit, per_month FROM subscriptions")
    return list(cursor.fetchall())


def get_per_month(chat_id: int, subreddit: str) -> int:
    cursor = exec_sql(
        "SELECT per_month FROM subscriptions WHERE chat_id=? AND subreddit=?",
        (chat_id, subreddit),
    )
    return cursor.fetchone()[0]


def all_subreddits() -> List[str]:
    cursor = exec_sql("SELECT DISTINCT subreddit FROM subscriptions")
    return [sub for (sub,) in cursor.fetchall()]


def sub_followers(subreddit: str) -> List[Tuple[int, int]]:
    cursor = exec_sql(
        "SELECT chat_id, per_month FROM subscriptions WHERE subreddit=?", (subreddit,),
    )
    return list(cursor.fetchall())


def user_subreddits(chat_id: int) -> List[str]:
    cursor = exec_sql("SELECT subreddit FROM subscriptions WHERE chat_id=?", (chat_id,))
    return [sub for (sub,) in cursor.fetchall()]


def user_subscriptions(chat_id: int) -> List[Tuple[str, int]]:
    cursor = exec_sql(
        "SELECT subreddit, per_month FROM subscriptions WHERE chat_id=?", (chat_id,),
    )
    return list(cursor.fetchall())


def already_sent(chat_id: int, post_id: str) -> bool:
    cursor = exec_sql(
        "SELECT * FROM messages WHERE chat_id=? AND post_id=?", (chat_id, post_id)
    )
    return bool(cursor.fetchone())


def mark_as_sent(chat_id: int, post_id: str):
    exec_sql("INSERT INTO messages VALUES (?,?)", (chat_id, post_id))


def commit():
    DB.commit()


def already_sent_exception(chat_id: int, subreddit: str, reason: str):
    cursor = exec_sql(
        "SELECT * FROM exceptions WHERE chat_id=? AND subreddit=? AND reason=?",
        (chat_id, subreddit, reason),
    )
    return bool(cursor.fetchone())


def mark_exception_as_sent(chat_id: int, subreddit: str, reason: str):
    exec_sql("INSERT INTO exceptions VALUES (?,?,?)", (subreddit, reason, chat_id))


def delete_exception(subreddit: str):
    exec_sql("DELETE FROM exceptions WHERE subreddit=?", (subreddit,))


def get_old_subscribers(subreddit: str) -> List[int]:
    cursor = exec_sql(
        "SELECT DISTINCT chat_id FROM exceptions WHERE subreddit=?", (subreddit,)
    )
    return [chat_id for (chat_id,) in cursor.fetchall()]


def unavailable_subreddits() -> List[str]:
    cursor = exec_sql("SELECT DISTINCT subreddit FROM exceptions")
    return [sub for (sub,) in cursor.fetchall()]
