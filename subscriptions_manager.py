import logging
import sqlite3
from datetime import datetime
from typing import Any, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


def exec_select(
    query: str, parameters: Tuple[Union[str, int], ...] = ()
) -> List[Tuple[Any, ...]]:
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
        """
        CREATE TABLE IF NOT EXISTS subscriptions(
            chat_id INTEGER NOT NULL,
            subreddit TEXT NOT NULL CHECK(subreddit LIKE "r/%" OR subreddit LIKE "u/%"),
            per_month INTEGER NOT NULL,
            "timestamp" DATETIME,
            PRIMARY KEY (chat_id, subreddit)
        );
        """
    )
    exec_sql(
        """
        CREATE TABLE IF NOT EXISTS exceptions (
            subreddit TEXT NOT NULL,
            reason TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            PRIMARY KEY (chat_id, subreddit, reason)
        );
        """
    )
    exec_sql(
        """
        CREATE TABLE IF NOT EXISTS messages (
            chat_id INTEGER NOT NULL,
            post_id TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            subreddit TEXT,
            PRIMARY KEY (chat_id, post_id)
        );
        """
    )
    exec_sql(
        """
        CREATE TRIGGER IF NOT EXISTS insert_Timestamp_Trigger
        AFTER INSERT ON subscriptions
        BEGIN
            UPDATE subscriptions SET timestamp = CURRENT_TIMESTAMP
            WHERE chat_id = NEW.chat_id AND subreddit = NEW.subreddit;
        END;
        """
    )
    exec_sql(
        """
        CREATE INDEX IF NOT EXISTS messages_timestamp_idx ON messages(timestamp);
        """
    )
    exec_sql(
        """
        CREATE INDEX IF NOT EXISTS messages_chat_id_post_id_idx ON messages(chat_id, post_id);
        """
    )
    exec_sql(
        """
        CREATE INDEX IF NOT EXISTS messages_chat_id_subreddit_timestamp_idx ON messages(chat_id, subreddit, timestamp);
        """
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
        "INSERT INTO subscriptions (chat_id, subreddit, per_month) VALUES (?,?,?)",
        (chat_id, subreddit, monthly_rank),
    )
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
    return True


def update_per_month(chat_id: int, subreddit: str, new_monthly_rank: int):
    exec_sql(
        "UPDATE subscriptions SET per_month=? " " WHERE chat_id=? AND subreddit=?",
        (new_monthly_rank, chat_id, subreddit),
    )


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
        "SELECT chat_id, per_month FROM subscriptions WHERE subreddit=?",
        (subreddit,),
    )


def user_subreddits(chat_id: int) -> List[str]:
    rows = exec_select(
        "SELECT subreddit FROM subscriptions WHERE chat_id=?", (chat_id,)
    )
    return [sub for (sub,) in rows]


def user_subscriptions(chat_id: int) -> List[Tuple[str, int]]:
    return exec_select(  # type: ignore
        "SELECT subreddit, per_month FROM subscriptions WHERE chat_id=?",
        (chat_id,),
    )


def already_sent(chat_id: int, post_id: str) -> bool:
    rows = exec_select(
        "SELECT * FROM messages WHERE chat_id=? AND post_id=?", (chat_id, post_id)
    )
    return bool(rows)


def mark_as_sent(chat_id: int, post_id: str, subreddit: str):
    exec_sql(
        "INSERT INTO messages(chat_id, post_id, subreddit) VALUES (?,?,?)",
        (chat_id, post_id, subreddit),
    )


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


def get_last_subscription_message(chat_id: int, subreddit: str) -> Optional[datetime]:
    rows = exec_select(
        "SELECT MAX(timestamp) from messages WHERE chat_id=? AND subreddit=?",
        (chat_id, subreddit),
    )
    for (timestamp,) in rows:
        try:
            return datetime.fromisoformat(timestamp)
        except TypeError:
            return None
    return None


def unavailable_subreddits() -> List[str]:
    rows = exec_select("SELECT DISTINCT subreddit FROM exceptions")
    return [sub for (sub,) in rows]


def delete_user(chat_id: int):
    for sub in user_subreddits(chat_id):
        unsubscribe(chat_id, sub)


def get_next_subscription_to_update() -> Tuple[str, int, int]:
    subreddit, chat_id, per_month, _priority = exec_select(
        """SELECT
  subscriptions.subreddit, subscriptions.chat_id, subscriptions.per_month,
  (
    (31.0 * 24.0 * 3600.0 / per_month) -
    (
        CAST(strftime('%s', CURRENT_TIMESTAMP) as integer) -
        COALESCE(
            CAST(strftime('%s', t.last_message_timestamp) as integer),
            0.0)
    )
  ) as priority
FROM subscriptions LEFT JOIN (
   SELECT chat_id, subreddit,
      COALESCE(max(timestamp), 0) as last_message_timestamp
    FROM messages
    GROUP BY chat_id, subreddit
    ORDER BY last_message_timestamp ASC
  ) t ON (
    t.chat_id = subscriptions.chat_id
    AND t.subreddit = subscriptions.subreddit
  )
ORDER BY priority ASC
LIMIT 1;
"""
    )[0]
    return subreddit, chat_id, per_month
