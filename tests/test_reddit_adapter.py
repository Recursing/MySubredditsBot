from typing import Any
import pytest
from .. import reddit_adapter


def test_format_time_delta():
    assert reddit_adapter.format_time_delta(3.5) == "3s"
    assert reddit_adapter.format_time_delta(35) == "35s"
    assert reddit_adapter.format_time_delta(12345) == "3h 25m"
    assert reddit_adapter.format_time_delta(123456) == "1d 10h"
    assert reddit_adapter.format_time_delta(0) == "0s"
    with pytest.raises(AssertionError):
        assert reddit_adapter.format_time_delta(-3.5)


def test_markdown_to_html():
    md = "Here is a [link](https://google.com/linky/)"
    assert (
        reddit_adapter.markdown_to_html(md)
        == 'Here is a <a href="https://google.com/linky/">link</a>'
    )


@pytest.fixture
def patch_datetime_now(monkeypatch: pytest.MonkeyPatch):
    class mynow:
        @staticmethod
        def timestamp():
            return 1642364229.123

    class mydatetime:
        @staticmethod
        def now():
            return mynow

    monkeypatch.setattr(reddit_adapter, "datetime", mydatetime)


def test_formatted_comment(patch_datetime_now: Any):
    comment: reddit_adapter.Comment = {  # type: ignore
        "subreddit_id": "t5_30m6u",
        "approved_at_utc": None,
        "author_is_blocked": False,
        "comment_type": None,
        "link_title": "What are some good SSC-adjacent groups that have meetups IRL? I just moved to Kansas City and am looking to meet folks",
        "mod_reason_by": None,
        "banned_by": None,
        "ups": 1,
        "num_reports": None,
        "author_flair_type": "text",
        "total_awards_received": 0,
        "subreddit": "slatestarcodex",
        "link_author": "ElbieLG",
        "likes": None,
        "replies": "",
        "user_reports": [],
        "saved": False,
        "id": "hscdq7x",
        "banned_at_utc": None,
        "mod_reason_title": None,
        "gilded": 0,
        "archived": False,
        "collapsed_reason_code": None,
        "no_follow": True,
        "author": "ScottAlexander",
        "num_comments": 9,
        "can_mod_post": False,
        "send_replies": True,
        "parent_id": "t3_s1vbb0",
        "score": 1,
        "author_fullname": "t2_1pyka",
        "over_18": False,
        "report_reasons": None,
        "removal_reason": None,
        "approved_by": None,
        "controversiality": 0,
        "body": "I don't know if [Kansas City Rationalists](https://www.meetup.com/Kansas-City-Rationalists/) still exists, but you might want to get in touch with them and check.",
        "edited": False,
        "top_awarded_type": None,
        "downs": 0,
        "author_flair_css_class": None,
        "is_submitter": False,
        "collapsed": False,
        "author_flair_richtext": [],
        "author_patreon_flair": False,
        "body_html": '&lt;div class="md"&gt;&lt;p&gt;I don&amp;#39;t know if &lt;a href="https://www.meetup.com/Kansas-City-Rationalists/"&gt;Kansas City Rationalists&lt;/a&gt; still exists, but you might want to get in touch with them and check.&lt;/p&gt;\n&lt;/div&gt;',
        "gildings": {},
        "collapsed_reason": None,
        "distinguished": None,
        "associated_award": None,
        "stickied": False,
        "author_premium": False,
        "can_gild": True,
        "link_id": "t3_s1vbb0",
        "unrepliable_reason": None,
        "author_flair_text_color": None,
        "score_hidden": False,
        "permalink": "/r/slatestarcodex/comments/s1vbb0/what_are_some_good_sscadjacent_groups_that_have/hscdq7x/",
        "subreddit_type": "public",
        "link_permalink": "https://www.reddit.com/r/slatestarcodex/comments/s1vbb0/what_are_some_good_sscadjacent_groups_that_have/",
        "name": "t1_hscdq7x",
        "author_flair_template_id": None,
        "subreddit_name_prefixed": "r/slatestarcodex",
        "author_flair_text": None,
        "treatment_tags": [],
        "created": 1641992976.0,
        "created_utc": 1641992976.0,
        "awarders": [],
        "all_awardings": [],
        "locked": False,
        "author_flair_background_color": None,
        "collapsed_because_crowd_control": None,
        "mod_reports": [],
        "quarantine": False,
        "mod_note": None,
        "link_url": "https://www.reddit.com/r/slatestarcodex/comments/s1vbb0/what_are_some_good_sscadjacent_groups_that_have/",
        "kind": "t1",
    }
    assert (
        reddit_adapter.formatted_comment(comment) == ""
        "ScottAlexander on: "
        '<a href="https://www.reddit.com/r/slatestarcodex/comments/s1vbb0/what_are_some_good_sscadjacent_groups_that_have/">'
        "What are some good SSC-adjacent groups that have meetups IRL? I just moved to Kansas City and am looking to meet folks</a>"
        '\n\nI don\'t know if <a href="https://www.meetup.com/Kansas-City-Rationalists/">Kansas City Rationalists</a> still exists,'
        " but you might want to get in touch with them and check.\n\n"
        '<a href="https://old.reddit.com/r/slatestarcodex/comments/s1vbb0/what_are_some_good_sscadjacent_groups_that_have/hscdq7x/?context=4">'
        "Context</a> - +1 in 4d 7h"
    )
