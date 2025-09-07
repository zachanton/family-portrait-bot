import base64
import json
import mimetypes
from redis.asyncio import Redis
from aiogram import Bot
from aiogram.types import PhotoSize
import structlog
from aiogram_bot_template.data.settings import settings

logger = structlog.get_logger(__name__)


def get_cached_image_proxy_url(unique_id: str) -> str:
    encoded_id = base64.urlsafe_b64encode(unique_id.encode("ascii")).decode("ascii")
    return f"{str(settings.proxy.base_url).strip('/')}/file_cache/{encoded_id}"


async def cache_image_bytes(
    unique_id: str,
    image_bytes: bytes,
    content_type: str,
    redis: Redis,
) -> None:
    """Caches image bytes in Redis."""
    payload_dict = {
        "content_type": content_type,
        "data": base64.b64encode(image_bytes).decode("ascii"),
    }
    payload_to_cache = json.dumps(payload_dict)
    await redis.set(unique_id, payload_to_cache, ex=86400)  # Cache for 24 hours
    logger.debug("Image cached in Redis", file_unique_id=unique_id)


async def get_cached_image_bytes(
    unique_id: str,
    redis: Redis,
) -> tuple[bytes, str] | tuple[None, None]:
    """Retrieves image bytes and content type from Redis cache."""
    cached_json = await redis.get(unique_id)
    if not cached_json:
        logger.warning("Requested file not in Redis cache", file_unique_id=unique_id)
        return None, None
    try:
        payload_dict = json.loads(cached_json)
        content_type = payload_dict["content_type"]
        file_bytes = base64.b64decode(payload_dict["data"])
        return file_bytes, content_type
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.exception("Could not decode payload from Redis", file_unique_id=unique_id)
        return None, None


async def download_and_cache_photo(
    photo: PhotoSize,
    bot: Bot,
    redis: Redis,
) -> str | None:
    """
    Downloads a photo from Telegram, caches it in Redis, and returns a public URL.

    Returns:
        A public proxy URL to the cached image, or None if an error occurs.
    """
    try:
        file_info = await bot.get_file(photo.file_id)
        if not file_info.file_path:
            logger.warning("File path is missing", file_id=photo.file_id)
            return None

        file_io = await bot.download_file(file_info.file_path)
        file_bytes = file_io.read()

        content_type, _ = mimetypes.guess_type(file_info.file_path)
        if not content_type:
            content_type = "application/octet-stream"

        await cache_image_bytes(photo.file_unique_id, file_bytes, content_type, redis)

        return get_cached_image_proxy_url(photo.file_unique_id)

    except Exception:
        logger.exception("Failed to download or cache photo", file_id=photo.file_id)
        return None
