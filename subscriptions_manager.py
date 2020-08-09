import logging
import sqlite3
from typing import List, Tuple, Union

import workers

logger = logging.getLogger(__name__)


def exec_select(
    query: str, parameters: Tuple[Union[str, int], ...] = ()
) -> List[Tuple]:
    assert query.startswith("SELECT")
    assert query.count("?") == len(parameters)
    results = []
    with sqlite3.connect("subscriptions.db") as connection:
        cursor = connection.cursor()
        cursor.execute(query, parameters)
        results = cursor.fetchall()
    return results


def exec_sql(query: str, parameters: Tuple[Union[str, int], ...] = ()) -> None:
    assert query.count("?") == len(parameters)
    # TODO proper mocking
    # print(f"SQL: {query} {parameters}")
    # return
    with sqlite3.connect("subscriptions.db") as connection:
        cursor = connection.cursor()
        cursor.execute(query, parameters)


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
            Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
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
        returns False if the user is already subscribed
    """
    if is_subscribed(chat_id, subreddit):
        return False

    exec_sql(
        "INSERT INTO subscriptions VALUES (?,?,?)", (chat_id, subreddit, monthly_rank),
    )
    workers.start_worker(chat_id, subreddit, monthly_rank)
    return True


def is_subscribed(chat_id: int, subreddit: str) -> bool:
    results = exec_select(
        "SELECT * FROM subscriptions WHERE chat_id=? AND subreddit=?",
        (chat_id, subreddit),
    )
    return bool(results)


def unsubscribe(chat_id: int, subreddit: str) -> bool:
    """
        returns False if there is no matching subscription
    """
    if not is_subscribed(chat_id, subreddit):
        return False
    exec_sql(
        "DELETE FROM subscriptions WHERE chat_id=? AND subreddit=?",
        (chat_id, subreddit),
    )
    workers.stop_worker(chat_id, subreddit)
    return True


def update_per_month(chat_id: int, subreddit: str, new_monthly_rank: int):
    exec_sql(
        "UPDATE subscriptions SET per_month=? " " WHERE chat_id=? AND subreddit=?",
        (new_monthly_rank, chat_id, subreddit),
    )
    workers.start_worker(chat_id, subreddit, new_monthly_rank)


def get_subscriptions() -> List[Tuple[int, str, int]]:
    return exec_select("SELECT chat_id, subreddit, per_month FROM subscriptions")  # type: ignore


def get_per_month(chat_id: int, subreddit: str) -> int:
    results = exec_select(
        "SELECT per_month FROM subscriptions WHERE chat_id=? AND subreddit=?",
        (chat_id, subreddit),
    )
    return results[0][0]


def all_subreddits() -> List[str]:
    results = exec_select("SELECT DISTINCT subreddit FROM subscriptions")
    return [sub for (sub,) in results]


def sub_followers(subreddit: str) -> List[Tuple[int, int]]:
    return exec_select(  # type: ignore
        "SELECT chat_id, per_month FROM subscriptions WHERE subreddit=?", (subreddit,),
    )


def user_subreddits(chat_id: int) -> List[str]:
    rows = exec_select(
        "SELECT subreddit FROM subscriptions WHERE chat_id=?", (chat_id,)
    )
    return [sub for (sub,) in rows]


def user_subscriptions(chat_id: int) -> List[Tuple[str, int]]:
    return exec_select(  # type: ignore
        "SELECT subreddit, per_month FROM subscriptions WHERE chat_id=?", (chat_id,),
    )


def already_sent(chat_id: int, post_id: str) -> bool:
    rows = exec_select(
        "SELECT * FROM messages WHERE chat_id=? AND post_id=?", (chat_id, post_id)
    )
    return bool(rows)


def mark_as_sent(chat_id: int, post_id: str):
    exec_sql("INSERT INTO messages(chat_id, post_id) VALUES (?,?)", (chat_id, post_id))


def already_sent_exception(chat_id: int, subreddit: str, reason: str):
    rows = exec_select(
        "SELECT * FROM exceptions WHERE chat_id=? AND subreddit=? AND reason=?",
        (chat_id, subreddit, reason),
    )
    return bool(rows)


def mark_exception_as_sent(chat_id: int, subreddit: str, reason: str):
    exec_sql("INSERT INTO exceptions VALUES (?,?,?)", (subreddit, reason, chat_id))


def delete_exception(subreddit: str):
    exec_sql("DELETE FROM exceptions WHERE subreddit=?", (subreddit,))


def get_old_subscribers(subreddit: str) -> List[int]:
    rows = exec_select(
        "SELECT DISTINCT chat_id FROM exceptions WHERE subreddit=?", (subreddit,)
    )
    return [chat_id for (chat_id,) in rows]


def unavailable_subreddits() -> List[str]:
    rows = exec_select("SELECT DISTINCT subreddit FROM exceptions")
    return [sub for (sub,) in rows]


def delete_user(chat_id):
    for sub in user_subreddits(chat_id):
        unsubscribe(chat_id, sub)
