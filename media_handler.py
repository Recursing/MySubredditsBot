from aiogram import Bot, exceptions
from bot import log_exception
import re
import httpx

image_extensions = ["jpg", "png"]
animation_extensions = ["gif", "gifv", "mp4"]
document_extensions = ["pdf"]
ignore_extensions = ["vim", "html"]
gfycat_domain = "gfycat.com"
vreddit_domain = "v.redd.it"

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


def get_media_type(url: str) -> str:
    extension = url.split(".")[-1].split("?")[0]
    if extension in image_extensions:
        return "IMG"
    if extension in animation_extensions:
        return "VID"
    if gfycat_domain in url or vreddit_domain in url:
        return "VID"
    return ""


async def send_media(bot: Bot, chat_id: int, url: str, caption: str, parse_mode: str):
    assert await contains_media(url)
    media_type = get_media_type(url)

    url = url.replace("https:", "http:")
    if gfycat_domain in url:
        url = await get_gfycat_mp4_url(url)
    elif vreddit_domain in url:
        url = await get_reddit_mp4_url(url)

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


async def get_gfycat_mp4_url(gfycat_url: str) -> str:
    id_group = r"gfycat\.com\/(?:detail\/)?(\w+)"
    gfyid = re.findall(id_group, gfycat_url)[0]
    client = httpx.AsyncClient()
    r = await client.get(f"https://api.gfycat.com/v1/gfycats/{gfyid}", timeout=60)
    urls = r.json()["gfyItem"]
    return urls["mp4Url"]


async def get_reddit_mp4_url(reddit_url: str) -> str:
    url = reddit_url.rstrip("/")
    mpd = url + "/DASHPlaylist.mpd"
    client = httpx.AsyncClient()
    r = await client.get(mpd, timeout=60)
    quality = next((q for q in reddit_qualities if q in r.text), "DASH_480")
    return f"{url}/{quality}?source=fallback"


async def contains_media(url: str) -> bool:
    media_extensions = image_extensions + animation_extensions
    known_extensions = media_extensions + document_extensions + ignore_extensions
    extension = url.split(".")[-1].split("?")[0]
    if 2 <= len(extension) <= 4 and extension not in known_extensions:
        await log_exception(Exception("Unknown extension"), url)

    return get_media_type(url) in ["IMG", "VID"]
