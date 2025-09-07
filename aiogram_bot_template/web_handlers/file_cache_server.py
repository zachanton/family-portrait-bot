import logging
from aiohttp import web
import base64

from typing import TYPE_CHECKING
import json

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


async def serve_cached_file(req: web.Request) -> web.Response:
    """
    Serve a file from the cache.

    Args:
        req: The incoming web request.

    Returns:
        The response object containing the file data.

    Raises:
        web.HTTPBadRequest: If the ID is missing or in an invalid format.
        web.HTTPNotFound: If the file is not found in the cache.
        web.HTTPInternalServerError: If the cached data is corrupted.
    """
    encoded_id = req.match_info.get("encoded_id")
    if not encoded_id:
        raise web.HTTPBadRequest(reason="ID is missing")

    try:
        file_unique_id = base64.urlsafe_b64decode(encoded_id.encode("ascii")).decode(
            "ascii",
        )
    except (ValueError, TypeError):
        logger.warning("Failed to decode base64 ID: %s", encoded_id)
        raise web.HTTPBadRequest(reason="Invalid ID format") from None

    # Get dp, and from it, the cache_pool.
    redis_cache: Redis = req.app["dp"]["cache_pool"]
    cached_json = await redis_cache.get(file_unique_id)

    if not cached_json:
        logger.warning("Requested file not in Redis cache: %s", file_unique_id)
        raise web.HTTPNotFound(reason="File not found in cache")

    try:
        payload_dict = json.loads(cached_json)
        content_type = payload_dict["content_type"]
        file_bytes = base64.b64decode(payload_dict["data"])
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.exception(
            "Could not decode JSON payload from Redis for key %s",
            file_unique_id,
        )
        raise web.HTTPInternalServerError(reason="Cache data corrupted") from e

    return web.Response(
        body=file_bytes,
        content_type=content_type or "application/octet-stream",
    )


routes = [
    web.get("/file_cache/{encoded_id}", serve_cached_file),
]
