import pytest

from .. import media_handler


@pytest.mark.asyncio
async def test_get_streamable_mp4_url():
    mp4_url = await media_handler.get_streamable_mp4_url(
        "https://streamable.com/2eyw5n"
    )
    assert mp4_url and mp4_url.split("?")[0].endswith(".mp4")
