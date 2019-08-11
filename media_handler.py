from aiogram import Bot, exceptions
from bot import log_exception
import re
import httpx

image_extensions = ["jpg", "png"]
animation_extensions = ["gif", "gifv", "mp4"]
document_extensions = ["pdf"]
ignore_extensions = ["vim", "html", "php"]


async def get_streamable_mp4_url(streamable_url: str) -> str:
    url_pattern = r"https://[a-z\-]+\.streamable\.com/video/mp4/.*?\.mp4\?token=.*?&amp;expires=\d+"
    client = httpx.AsyncClient()
    r = await client.get(streamable_url, timeout=60)
    match = re.search(url_pattern, r.text, re.MULTILINE)
    if match:
        return match.group()
    raise Exception(f"STREAMABLE URL NOT FOUND IN {streamable_url}")


async def get_gfycat_mp4_url(gfycat_url: str) -> str:
    id_group = r"gfycat\.com\/(?:detail\/)?(\w+)"
    gfyid = re.findall(id_group, gfycat_url)[0]
    client = httpx.AsyncClient()
    r = await client.get(f"https://api.gfycat.com/v1/gfycats/{gfyid}", timeout=60)
    urls = r.json()["gfyItem"]
    return urls["mp4Url"]


async def get_reddit_mp4_url(reddit_url: str) -> str:
    reddit_qualities = [
        "DASH_720",
        "DASH_480",
        "DASH_360",
        "DASH_1080",
        "DASH_600_K",
        "DASH_1_2_M",
        "DASH_9_6_M",
        "DASH_4_8_M",
        "DASH_2_4_M",
        "DASH_240",
    ]
    url = reddit_url.rstrip("/")
    mpd = url + "/DASHPlaylist.mpd"
    client = httpx.AsyncClient()
    r = await client.get(mpd, timeout=60)
    quality = next((q for q in reddit_qualities if q in r.text), "DASH_480")
    return f"{url}/{quality}?source=fallback"


video_scrapers = {
    "gfycat.com": get_gfycat_mp4_url,
    "v.redd.it": get_reddit_mp4_url,
    "streamable.com": get_streamable_mp4_url,
}


def get_media_type(url: str) -> str:
    extension = url.split(".")[-1].split("?")[0]
    if extension in image_extensions:
        return "IMG"
    if extension in animation_extensions:
        return "VID"
    if any(domain in url for domain in video_scrapers):
        return "VID"
    return ""


async def send_media(bot: Bot, chat_id: int, url: str, caption: str, parse_mode: str):
    assert contains_media(url)
    media_type = get_media_type(url)

    url = url.replace("https:", "http:")
    for domain, scraper in video_scrapers.items():
        if domain in url:
            url = await scraper(url)

    if media_type == "IMG":
        try:
            await bot.send_photo(chat_id, url, caption=caption, parse_mode=parse_mode)
        except (
            exceptions.PhotoDimensions,
            exceptions.WrongFileIdentifier,
            exceptions.InvalidHTTPUrlContent,
        ):
            print("Error sending photo from", url)
            await bot.send_message(chat_id, caption, parse_mode=parse_mode)
    elif media_type == "VID":
        try:
            await bot.send_animation(
                chat_id,
                url.replace(".gifv", ".mp4"),
                caption=caption,
                parse_mode=parse_mode,
            )
        except (exceptions.WrongFileIdentifier, exceptions.InvalidHTTPUrlContent):
            print("Error sending video from", url)
            await bot.send_message(chat_id, caption, parse_mode=parse_mode)


async def contains_media(url: str) -> bool:
    media_extensions = image_extensions + animation_extensions
    known_extensions = media_extensions + document_extensions + ignore_extensions
    extension = url.split(".")[-1].split("?")[0]
    if 2 <= len(extension) <= 4 and extension not in known_extensions:
        await log_exception(Exception("Unknown extension"), url)

    return get_media_type(url) in ["IMG", "VID"]
