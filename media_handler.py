from __future__ import annotations

import asyncio
import html
import logging
import re
from typing import TYPE_CHECKING, List, Literal, Optional
from urllib.parse import urlparse

import httpx
from aiogram import Bot, exceptions
from aiogram.types import InputMediaPhoto

if TYPE_CHECKING:
    from reddit_adapter import Gallery, Post

image_extensions = ["jpg", "png", "webp", "jpeg"]
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


async def GET(
    url: str, httpx_timeout: int = 60, total_timeout: int = 120
) -> httpx.Response:
    return await asyncio.wait_for(
        CLIENT_SESSION.get(url, timeout=httpx_timeout, follow_redirects=True),
        timeout=total_timeout,
    )


async def get_streamable_mp4_url(streamable_url: str) -> Optional[str]:
    url_pattern = re.compile(
        r'https://[a-z\-]+\.streamable\.com/video/mp4/.*?\.mp4\?Expires=\d+&Signature=.*?(?:&amp;|&)[^"]*',
        re.MULTILINE,
    )
    r = await GET(streamable_url)
    match = url_pattern.search(r.text)
    if match:
        return match.group().replace("&amp;", "&")

    logging.error(f"STREAMABLE URL NOT FOUND IN {streamable_url}")
    return None


async def get_gfycat_mp4_url(gfycat_url: str) -> Optional[str]:
    id_group = r"gfycat\.com\/(?:gifs\/)?(?:detail\/)?(?:amp\/)?(?:ru\/)?(?:fr\/)?(\w+)"
    gfyid = re.findall(id_group, gfycat_url)[0]
    r = await GET(f"https://api.gfycat.com/v1/gfycats/{gfyid}")
    try:
        r_json = r.json()
        assert isinstance(r_json, dict)
        urls: dict[str, str] = r_json["gfyItem"]
        return urls["mp4Url"]
    except Exception as e:
        logging.error(f"Invalid data from gfycat {gfycat_url} {e!r}")
        return None


video_scrapers = {
    "gfycat.com": get_gfycat_mp4_url,
    "/streamable.com": get_streamable_mp4_url,
}


def get_extension(url: str) -> str:
    path = urlparse(url).path
    if path.endswith("/"):
        return ""
    return path.split(".")[-1].lower() if "." in path else ""


def get_media_type(url: str) -> Literal["VID", "IMG", None]:
    extension = get_extension(url)
    if extension in image_extensions:
        return "IMG"
    if extension in animation_extensions:
        return "VID"
    if any(domain in url for domain in video_scrapers):
        return "VID"
    return None


async def fix_url(url: str) -> Optional[str]:
    maybe_url = url.replace("https:", "http:").replace("&amp;", "&") or None
    for domain, scraper in video_scrapers.items():
        if maybe_url and domain in maybe_url:
            return await scraper(maybe_url)
    return maybe_url


def is_gallery(post: Post) -> bool:
    return bool(post.get("is_gallery"))


def get_gallery_image_urls(gallery: Gallery) -> List[str]:
    gallery_data = gallery.get("gallery_data")
    if not gallery_data:
        return []
    image_ids = [item["media_id"] for item in gallery_data.get("items", [])]

    def get_url(media_id: str) -> str | None:
        media_info = (gallery.get("media_metadata") or {}).get(media_id)
        if not media_info:
            return None
        full_size = media_info.get("s")
        if (
            full_size
            and full_size["x"] <= 1200
            and full_size["y"] <= 1200
            and full_size.get("u")
        ):
            return full_size["u"]
        previews = media_info.get("p")
        if not previews:
            return None
        for preview in reversed(previews):
            if preview.get("u"):
                return preview["u"]
        return None

    image_urls = [get_url(media_id) for media_id in image_ids]
    return [html.unescape(u) for u in image_urls if u]


async def send_gallery(bot: Bot, chat_id: int, post: Post, caption: str) -> None:
    assert is_gallery(post)
    gallery: Gallery = post  # type:ignore
    image_urls = get_gallery_image_urls(gallery)
    if not image_urls:
        logging.error(f"Cannot get image urls from {post}")
        await bot.send_message(chat_id, caption, parse_mode="HTML")
        return
    if len(image_urls) == 1:
        await bot.send_photo(chat_id, image_urls[0], caption=caption, parse_mode="HTML")
        return
    if len(image_urls) > 10:
        image_urls = image_urls[:10]
    first_image_url, *image_urls = image_urls
    media_group = [InputMediaPhoto(first_image_url, caption=caption, parse_mode="HTML")]
    media_group.extend([InputMediaPhoto(url) for url in image_urls])

    try:
        await bot.send_media_group(chat_id=chat_id, media=media_group)
    except exceptions.BadRequest as e:
        logging.error(f"Error {e!r} sending gallery for {post}")
        await bot.send_message(chat_id, caption, parse_mode="HTML")


async def send_image(bot: Bot, chat_id: int, post: Post, caption: str) -> None:
    image_url = post["url"]
    preview_images = post.get("preview", {}).get("images")
    resolutions = preview_images and preview_images[0].get("resolutions")
    if resolutions:
        image_url = html.unescape(resolutions[-1]["url"])
    try:
        await bot.send_photo(
            chat_id=chat_id, photo=image_url, caption=caption, parse_mode="HTML"
        )
    except exceptions.BadRequest as e:
        logging.error(f"Error {e!r} sending photo for {post}")
        await bot.send_message(chat_id, caption, parse_mode="HTML")


async def send_video(bot: Bot, chat_id: int, post: Post, caption: str) -> None:
    maybe_url = await fix_url(post["url"])
    if maybe_url is None:
        await bot.send_message(chat_id, caption, parse_mode="HTML")
        return
    try:
        maybe_url = maybe_url.replace(".gifv", ".mp4")
        await bot.send_animation(
            chat_id,
            maybe_url,
            caption=caption,
            parse_mode="HTML",
        )
    except exceptions.BadRequest as e:
        logging.error(f"Error {e!r} sending video for {post}")
        await bot.send_message(chat_id, caption, parse_mode="HTML")


async def send_media(bot: Bot, chat_id: int, post: Post, caption: str) -> None:
    media_type = get_media_type(post["url"])
    assert media_type is not None
    if media_type == "IMG":
        await send_image(bot, chat_id, post, caption)
    elif media_type == "VID":
        await send_video(bot, chat_id, post, caption)


def contains_media(url: str) -> bool:
    media_extensions = image_extensions + animation_extensions
    known_extensions = media_extensions + document_extensions + ignore_extensions
    extension = get_extension(url)
    if 2 <= len(extension) <= 4 and extension not in known_extensions:
        logging.info(f"Unknown extension: {extension}, {url}")

    return get_media_type(url) in ["IMG", "VID"]
