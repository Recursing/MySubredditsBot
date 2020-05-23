import asyncio
import re
from urllib.parse import urlparse

from aiogram import Bot, exceptions

import httpx

image_extensions = ["jpg", "png", "webp"]
animation_extensions = ["gif", "gifv", "mp4", "mpeg"]
document_extensions = ["pdf", "txt", "md"]
ignore_extensions = [
    "vim",
    "html",
    "htm",
    "php",
    "cms",
    "en",
    "amp",
    "aspx",
    "cfm",
    "org",
    "js",
]

CLIENT_SESSION = httpx.AsyncClient()


async def get_streamable_mp4_url(streamable_url: str) -> str:
    url_pattern = r"https://[a-z\-]+\.streamable\.com/video/mp4/.*?\.mp4\?token=.*?(?:&amp;|&)expires=\d+"
    r = await asyncio.wait_for(
        CLIENT_SESSION.get(streamable_url, timeout=60), timeout=100
    )
    match = re.search(url_pattern, r.text, re.MULTILINE)
    if match:
        return match.group().replace("&amp;", "&")
    raise Exception(f"STREAMABLE URL NOT FOUND IN {streamable_url}")


async def get_gfycat_mp4_url(gfycat_url: str) -> str:
    id_group = r"gfycat\.com\/(?:gifs\/)?(?:detail\/)?(?:amp\/)?(?:ru\/)?(?:fr\/)?(\w+)"
    gfyid = re.findall(id_group, gfycat_url)[0]
    r = await asyncio.wait_for(
        CLIENT_SESSION.get(f"https://api.gfycat.com/v1/gfycats/{gfyid}", timeout=60),
        timeout=100,
    )
    r_json = r.json()
    assert isinstance(r_json, dict)
    if "gfyItem" not in r_json:
        raise Exception(f"Invalid data from gfy {r.json()}")
    urls = r_json["gfyItem"]
    return urls["mp4Url"]


async def get_reddit_mp4_url(reddit_url: str) -> str:
    reddit_qualities = [
        "DASH_600_K",
        "DASH_1_2_M",
        "DASH_2_4_M",
        "DASH_4_8_M",
        "DASH_480",
        "DASH_360",
        "DASH_720",
        "DASH_240",
        "DASH_9_6_M",
        "DASH_1080",
    ]
    url = reddit_url.rstrip("/")
    mpd = url + "/DASHPlaylist.mpd"
    # TODO get video size
    r = await asyncio.wait_for(CLIENT_SESSION.get(mpd, timeout=60), timeout=100)
    quality = next((q for q in reddit_qualities if q in r.text), "DASH_480")
    return f"{url}/{quality}?source=fallback"


video_scrapers = {
    "gfycat.com": get_gfycat_mp4_url,
    "v.redd.it": get_reddit_mp4_url,
    "/streamable.com": get_streamable_mp4_url,
}


def get_extension(url: str) -> str:
    path = urlparse(url).path
    if path.endswith("/"):
        return ""
    return path.split(".")[-1].lower() if "." in path else ""


def get_media_type(url: str) -> str:
    extension = get_extension(url)
    if extension in image_extensions:
        return "IMG"
    if extension in animation_extensions:
        return "VID"
    if any(domain in url for domain in video_scrapers):
        return "VID"
    return ""


async def send_media(bot: Bot, chat_id: int, url: str, caption: str, parse_mode: str):
    assert await contains_media(url)
    media_type = get_media_type(url)

    url = url.replace("https:", "http:").replace("&amp;", "&")
    for domain, scraper in video_scrapers.items():
        if domain in url:
            url = await scraper(url)

    if url is None:
        await bot.send_message(chat_id, caption, parse_mode=parse_mode)
    elif media_type == "IMG":
        try:
            await bot.send_photo(chat_id, url, caption=caption, parse_mode=parse_mode)
        except (
            exceptions.PhotoDimensions,
            exceptions.WrongFileIdentifier,
            exceptions.InvalidHTTPUrlContent,
            exceptions.BadRequest,
        ) as e:
            print(f"Error sending photo from {url} {e!r}")
            await bot.send_message(chat_id, caption, parse_mode=parse_mode)
    elif media_type == "VID":
        try:
            await bot.send_animation(
                chat_id,
                url.replace(".gifv", ".mp4"),
                caption=caption,
                parse_mode=parse_mode,
            )
        except (
            exceptions.WrongFileIdentifier,
            exceptions.InvalidHTTPUrlContent,
            exceptions.BadRequest,
        ) as e:
            print(f"Error sending video from {url} {e!r}")
            await bot.send_message(chat_id, caption, parse_mode=parse_mode)


async def contains_media(url: str) -> bool:
    media_extensions = image_extensions + animation_extensions
    known_extensions = media_extensions + document_extensions + ignore_extensions
    extension = get_extension(url)
    if 2 <= len(extension) <= 4 and extension not in known_extensions:
        print("Unknown extension:", extension, url)

    return get_media_type(url) in ["IMG", "VID"]
