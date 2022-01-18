from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Dict, cast

import pytest
from aiogram import Bot

if TYPE_CHECKING:
    from reddit_adapter import Gallery, Post

from .. import media_handler


@pytest.mark.asyncio
async def test_get_streamable_mp4_url():
    urls = ["https://streamable.com/2eyw5n", "http://streamable.com/9o626v"]

    mp4_urls = await asyncio.gather(*map(media_handler.get_streamable_mp4_url, urls))
    for url in mp4_urls:
        assert url and url.split("?")[0].endswith(".mp4")


def test_gallery():
    gallery_post: Post = {  # type: ignore
        "kind": "t3",
        "subreddit": "comics",
        "is_gallery": True,
        "title": "Genie",
        "media_metadata": {
            "x8or3pvjiua81": {
                "status": "valid",
                "e": "Image",
                "m": "image/jpg",
                "p": [
                    {
                        "y": 108,
                        "x": 108,
                        "u": "https://preview.redd.it/x8or3pvjiua81.jpg?width=108&crop=smart&auto=webp&s=5e5945b3beaedef70bb9af57c297abe8b95529ba",
                    },
                    {
                        "y": 216,
                        "x": 216,
                        "u": "https://preview.redd.it/x8or3pvjiua81.jpg?width=216&crop=smart&auto=webp&s=395a964856a37954b90379b2f84498bf7f36ebf3",
                    },
                    {
                        "y": 320,
                        "x": 320,
                        "u": "https://preview.redd.it/x8or3pvjiua81.jpg?width=320&crop=smart&auto=webp&s=6efb6422b05c024f7aa3f27326ca140a708605da",
                    },
                    {
                        "y": 640,
                        "x": 640,
                        "u": "https://preview.redd.it/x8or3pvjiua81.jpg?width=640&crop=smart&auto=webp&s=730025cfa3c9b7a895d775691dc29eb20fc55451",
                    },
                ],
                "s": {
                    "y": 800,
                    "x": 800,
                    "u": "https://preview.redd.it/x8or3pvjiua81.jpg?width=800&format=pjpg&auto=webp&s=69de14211f60f9570a8ffa2c2183ba224344f6ad",
                },
                "id": "x8or3pvjiua81",
            },
            "mwqoyovjiua81": {
                "status": "valid",
                "e": "Image",
                "m": "image/jpg",
                "p": [
                    {
                        "y": 108,
                        "x": 108,
                        "u": "https://preview.redd.it/mwqoyovjiua81.jpg?width=108&crop=smart&auto=webp&s=aaae14749947465441cf76c68707a4ab76e68b13",
                    },
                    {
                        "y": 216,
                        "x": 216,
                        "u": "https://preview.redd.it/mwqoyovjiua81.jpg?width=216&crop=smart&auto=webp&s=e4a0aba82447127b0f835407334c691c68032452",
                    },
                    {
                        "y": 320,
                        "x": 320,
                        "u": "https://preview.redd.it/mwqoyovjiua81.jpg?width=320&crop=smart&auto=webp&s=a738dea7687e0f9587d8b87509a2b3b9c73b0baf",
                    },
                    {
                        "y": 640,
                        "x": 640,
                        "u": "https://preview.redd.it/mwqoyovjiua81.jpg?width=640&crop=smart&auto=webp&s=961796b8c69823864843b5564af0e5b584eb0ecd",
                    },
                ],
                "s": {
                    "y": 800,
                    "x": 800,
                    "u": "https://preview.redd.it/mwqoyovjiua81.jpg?width=800&format=pjpg&auto=webp&s=b829a1d3ccf6ed30437d691390973140e0cdf55d",
                },
                "id": "mwqoyovjiua81",
            },
            "2b5c8rvjiua81": {
                "status": "valid",
                "e": "Image",
                "m": "image/jpg",
                "p": [
                    {
                        "y": 108,
                        "x": 108,
                        "u": "https://preview.redd.it/2b5c8rvjiua81.jpg?width=108&crop=smart&auto=webp&s=e01301baf2851068081701e56cf7dd7ea82cc0e7",
                    },
                    {
                        "y": 216,
                        "x": 216,
                        "u": "https://preview.redd.it/2b5c8rvjiua81.jpg?width=216&crop=smart&auto=webp&s=002579b9550f37567ff8503ca0d92b0ffe5a7358",
                    },
                    {
                        "y": 320,
                        "x": 320,
                        "u": "https://preview.redd.it/2b5c8rvjiua81.jpg?width=320&crop=smart&auto=webp&s=2e5f5142c366d8ad53f166da8eab4f6612e139e9",
                    },
                    {
                        "y": 640,
                        "x": 640,
                        "u": "https://preview.redd.it/2b5c8rvjiua81.jpg?width=640&crop=smart&auto=webp&s=4eed4d1647aaf9f958e0250f56a0cae6561ed2ab",
                    },
                ],
                "s": {
                    "y": 800,
                    "x": 800,
                    "u": "https://preview.redd.it/2b5c8rvjiua81.jpg?width=800&format=pjpg&auto=webp&s=f5d7332c4c8a1a0fcc436bf977c37c0555a53c07",
                },
                "id": "2b5c8rvjiua81",
            },
            "mv3giovjiua81": {
                "status": "valid",
                "e": "Image",
                "m": "image/jpg",
                "p": [
                    {
                        "y": 108,
                        "x": 108,
                        "u": "https://preview.redd.it/mv3giovjiua81.jpg?width=108&crop=smart&auto=webp&s=a898e660ad24b80f524486be2ca2506ec2e6796a",
                    },
                    {
                        "y": 216,
                        "x": 216,
                        "u": "https://preview.redd.it/mv3giovjiua81.jpg?width=216&crop=smart&auto=webp&s=279de5ec1617c97900b8adc855ff03bffcf4bf2b",
                    },
                    {
                        "y": 320,
                        "x": 320,
                        "u": "https://preview.redd.it/mv3giovjiua81.jpg?width=320&crop=smart&auto=webp&s=250b3aba0cc1f691fa8acf093839618735851795",
                    },
                    {
                        "y": 640,
                        "x": 640,
                        "u": "https://preview.redd.it/mv3giovjiua81.jpg?width=640&crop=smart&auto=webp&s=8bcbb161f36d2cdae9c1d65d208993607d1243a9",
                    },
                ],
                "s": {
                    "y": 800,
                    "x": 800,
                    "u": "https://preview.redd.it/mv3giovjiua81.jpg?width=800&format=pjpg&auto=webp&s=991cf2b6e1400404eacc9c01a2a6f075d172ca10",
                },
                "id": "mv3giovjiua81",
            },
            "y80e83wjiua81": {
                "status": "valid",
                "e": "Image",
                "m": "image/jpg",
                "p": [
                    {
                        "y": 108,
                        "x": 108,
                        "u": "https://preview.redd.it/y80e83wjiua81.jpg?width=108&crop=smart&auto=webp&s=d65a9697e86f5947c8fa50dfba362cd84010d59c",
                    },
                    {
                        "y": 216,
                        "x": 216,
                        "u": "https://preview.redd.it/y80e83wjiua81.jpg?width=216&crop=smart&auto=webp&s=e72ad0b1dd46afc2b800d68b37b9a3759d88ed3f",
                    },
                    {
                        "y": 320,
                        "x": 320,
                        "u": "https://preview.redd.it/y80e83wjiua81.jpg?width=320&crop=smart&auto=webp&s=860ff92ad5e99d7ea73db8811b87bd9fa323710f",
                    },
                    {
                        "y": 640,
                        "x": 640,
                        "u": "https://preview.redd.it/y80e83wjiua81.jpg?width=640&crop=smart&auto=webp&s=f9877b53db9dc64a8b6b3c7e725483d7282d07c6",
                    },
                    {
                        "y": 960,
                        "x": 960,
                        "u": "https://preview.redd.it/y80e83wjiua81.jpg?width=960&crop=smart&auto=webp&s=8bee0d5745d4fa78c6fa3ca45bc0ba2cf314c81c",
                    },
                    {
                        "y": 1080,
                        "x": 1080,
                        "u": "https://preview.redd.it/y80e83wjiua81.jpg?width=1080&crop=smart&auto=webp&s=73d0cf1e99f1d96ce3ad5fe6449e8a309ca2dae7",
                    },
                ],
                "s": {
                    "y": 1440,
                    "x": 1440,
                    "u": "https://preview.redd.it/y80e83wjiua81.jpg?width=1440&format=pjpg&auto=webp&s=77447641333d258ba92cf493a42da72b885f3d90",
                },
                "id": "y80e83wjiua81",
            },
        },
        "permalink": "/r/comics/comments/s0hxfc/genie/",
        "gallery_data": {
            "items": [
                {"media_id": "mv3giovjiua81", "id": 101071881},
                {"media_id": "mwqoyovjiua81", "id": 101071882},
                {"media_id": "x8or3pvjiua81", "id": 101071883},
                {"media_id": "2b5c8rvjiua81", "id": 101071884},
                {"media_id": "y80e83wjiua81", "id": 101071885},
            ]
        },
    }

    assert media_handler.is_gallery(gallery_post)
    gallery: Gallery = gallery_post  # type: ignore
    assert media_handler.get_gallery_image_urls(gallery) == [
        "https://preview.redd.it/mv3giovjiua81.jpg?width=800&format=pjpg&auto=webp&s=991cf2b6e1400404eacc9c01a2a6f075d172ca10",
        "https://preview.redd.it/mwqoyovjiua81.jpg?width=800&format=pjpg&auto=webp&s=b829a1d3ccf6ed30437d691390973140e0cdf55d",
        "https://preview.redd.it/x8or3pvjiua81.jpg?width=800&format=pjpg&auto=webp&s=69de14211f60f9570a8ffa2c2183ba224344f6ad",
        "https://preview.redd.it/2b5c8rvjiua81.jpg?width=800&format=pjpg&auto=webp&s=f5d7332c4c8a1a0fcc436bf977c37c0555a53c07",
        "https://preview.redd.it/y80e83wjiua81.jpg?width=1080&crop=smart&auto=webp&s=73d0cf1e99f1d96ce3ad5fe6449e8a309ca2dae7",
    ]


@pytest.mark.asyncio
async def test_large_image():
    post: Post = {  # type: ignore
        "kind": "t3",
        "subreddit": "piano",
        "selftext": "",
        "title": "Finally got this Kawai GL30!!",
        "preview": {
            "images": [
                {
                    "source": {
                        "url": "https://preview.redd.it/6780jwapt9b81.jpg?auto=webp&amp;s=713360c9874e3e4c89c1d0f9f0c00bfee366aecc",
                        "width": 6936,
                        "height": 9248,
                    },
                    "resolutions": [
                        {
                            "url": "https://preview.redd.it/6780jwapt9b81.jpg?width=108&amp;crop=smart&amp;auto=webp&amp;s=fad3a88652e1183693f72980710c13dc18771b6e",
                            "width": 108,
                            "height": 144,
                        },
                        {
                            "url": "https://preview.redd.it/6780jwapt9b81.jpg?width=216&amp;crop=smart&amp;auto=webp&amp;s=57e8132ae3d023889a5ef68b3eff66723a0e09c2",
                            "width": 216,
                            "height": 288,
                        },
                        {
                            "url": "https://preview.redd.it/6780jwapt9b81.jpg?width=320&amp;crop=smart&amp;auto=webp&amp;s=622587929f21160caf5a9b3d607fb74db413ffbf",
                            "width": 320,
                            "height": 426,
                        },
                        {
                            "url": "https://preview.redd.it/6780jwapt9b81.jpg?width=640&amp;crop=smart&amp;auto=webp&amp;s=b4b418231c1fb83db85e812863cff64454ef9409",
                            "width": 640,
                            "height": 853,
                        },
                        {
                            "url": "https://preview.redd.it/6780jwapt9b81.jpg?width=960&amp;crop=smart&amp;auto=webp&amp;s=5fdfa114c9d894aeaa431ef4c0c291db88a31199",
                            "width": 960,
                            "height": 1280,
                        },
                        {
                            "url": "https://preview.redd.it/6780jwapt9b81.jpg?width=1080&amp;crop=smart&amp;auto=webp&amp;s=9e249e8ecb9039eb9f6671150413d8f0c02340e8",
                            "width": 1080,
                            "height": 1440,
                        },
                    ],
                    "variants": {},
                    "id": "1t8rNRotK1FUtxNmAGpN4Mxb5x9r57AkIN8oNoU2y4w",
                }
            ],
            "enabled": True,
        },
        "id": "s287ia",
        "permalink": "/r/piano/comments/s287ia/finally_got_this_kawai_gl30/",
        "url": "https://i.redd.it/6780jwapt9b81.jpg",
        "is_video": False,
    }
    assert media_handler.contains_media(post["url"])

    class MockBot:
        call_args: Dict[str, Any] = {}

        async def send_photo(self, **kwargs: Dict[str, Any]):
            self.call_args = kwargs

    mockBot = MockBot()
    await media_handler.send_media(cast(Bot, mockBot), 123, post, "Caption")
    assert mockBot.call_args == {
        "chat_id": 123,
        "photo": "https://preview.redd.it/6780jwapt9b81.jpg?width=1080&crop=smart&auto=webp&s=9e249e8ecb9039eb9f6671150413d8f0c02340e8",
        "caption": "Caption",
        "parse_mode": "HTML",
    }
