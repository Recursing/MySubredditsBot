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


def test_gallery_with_missing_image():
    # Apparently this can happen :shrugs
    gallery_post: Post = {  # type: ignore
        "kind": "t3",
        "subreddit": "phclassifieds",
        "selftext": "",
        "is_gallery": True,
        "title": "Male cats for adoption! Location: Dasma, Cavite",
        "media_metadata": {
            "u3dxaipziic81": {
                "status": "valid",
                "e": "Image",
                "m": "image/jpg",
                "p": [
                    {
                        "y": 1440,
                        "x": 1080,
                        "u": "https://preview.redd.it/u3dxaipziic81.jpg?width=1080&amp;crop=smart&amp;auto=webp&amp;s=187b759018e50c9ca6019891e816654cbfa30e3c",
                    },
                ],
                "s": {
                    "y": 4624,
                    "x": 3468,
                    "u": "https://preview.redd.it/u3dxaipziic81.jpg?width=3468&amp;format=pjpg&amp;auto=webp&amp;s=40193d5df8e08882b95fed9943873ba6cd0c01fe",
                },
                "id": "u3dxaipziic81",
            },
            "315vp420jic81": {
                "status": "valid",
                "e": "Image",
                "m": "image/jpg",
                "p": [
                    {
                        "y": 810,
                        "x": 1080,
                        "u": "https://preview.redd.it/315vp420jic81.jpg?width=1080&amp;crop=smart&amp;auto=webp&amp;s=42ed0cde863455f8752ebc61277bfd7529bf116d",
                    },
                ],
                "s": {
                    "y": 3468,
                    "x": 4624,
                    "u": "https://preview.redd.it/315vp420jic81.jpg?width=4624&amp;format=pjpg&amp;auto=webp&amp;s=faab29e0c2fd5f58b099edc36d7a74c912a01fc4",
                },
                "id": "315vp420jic81",
            },
            "cx9099hziic81": {"status": "failed"},
        },
        "gallery_data": {
            "items": [
                {"media_id": "cx9099hziic81", "id": 103482769},
                {"media_id": "u3dxaipziic81", "id": 103482770},
                {"media_id": "315vp420jic81", "id": 103482771},
            ]
        },
        "url": "https://www.reddit.com/gallery/s784v9",
    }

    assert media_handler.is_gallery(gallery_post)
    gallery: Gallery = gallery_post  # type: ignore
    assert media_handler.get_gallery_image_urls(gallery) == [
        "https://preview.redd.it/u3dxaipziic81.jpg?width=1080&crop=smart&auto=webp&s=187b759018e50c9ca6019891e816654cbfa30e3c",
        "https://preview.redd.it/315vp420jic81.jpg?width=1080&crop=smart&auto=webp&s=42ed0cde863455f8752ebc61277bfd7529bf116d",
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
