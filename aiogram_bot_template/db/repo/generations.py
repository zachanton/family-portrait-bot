# aiogram_bot_template/db/repo/generations.py
from dataclasses import dataclass
from typing import Any

from aiogram_bot_template.db.db_api.storages import PostgresConnection


@dataclass
class GenerationRequestDraft:
    user_id: int
    status: str
    source_images: list[tuple[str, str, str]]


async def create_generation_request(db: PostgresConnection, draft: GenerationRequestDraft) -> int:
    """Creates a new generation request and its source images, returns the request ID."""
    async with db.transaction() as con:
        sql_insert_request = """
            INSERT INTO generation_requests (user_id, status)
            VALUES ($1, $2) RETURNING id;
        """
        request_id = await con.fetchval(
            sql_insert_request,
            draft.user_id,
            draft.status,
        )

        if draft.source_images:
            sql_insert_image = """
                INSERT INTO generation_source_images (request_id, file_unique_id, file_id, role)
                VALUES ($1, $2, $3, $4);
            """
            images_data = [
                (request_id, img_unique_id, img_id, role)
                for img_unique_id, img_id, role in draft.source_images
            ]
            await con.executemany(sql_insert_image, images_data)

    return request_id


async def update_generation_request_status(db: PostgresConnection, request_id: int, status: str) -> None:
    """Updates the status of a generation request."""
    sql = "UPDATE generation_requests SET status = $2, updated_at = NOW() WHERE id = $1;"
    await db.execute(sql, (request_id, status))


@dataclass
class GenerationLog:
    request_id: int
    type: str
    status: str
    quality_level: int | None = None
    trial_type: str | None = None
    seed: int | None = None
    style: str | None = None
    result_image_unique_id: str | None = None
    result_message_id: int | None = None
    result_file_id: str | None = None
    caption: str | None = None
    control_message_id: int | None = None
    error_message: str | None = None
    generation_time_ms: int | None = None
    api_request_payload: dict[str, Any] | None = None
    api_response_payload: dict[str, Any] | None = None
    enhanced_prompt: str | None = None


async def create_generation_log(db: PostgresConnection, log_data: GenerationLog) -> int:
    """Logs a single generation attempt and returns its ID."""
    sql = """
        INSERT INTO generations (
            request_id, type, status, quality_level, trial_type, seed, style,
            result_image_unique_id, result_message_id, result_file_id, caption,
            control_message_id, error_message, generation_time_ms,
            api_request_payload, api_response_payload, enhanced_prompt
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
        RETURNING id;
    """
    result = await db.fetchrow(
        sql,
        (
            log_data.request_id, log_data.type, log_data.status, log_data.quality_level,
            log_data.trial_type, log_data.seed, log_data.style, log_data.result_image_unique_id,
            log_data.result_message_id, log_data.result_file_id,
            log_data.caption, log_data.control_message_id,
            log_data.error_message, log_data.generation_time_ms,
            log_data.api_request_payload, log_data.api_response_payload,
            log_data.enhanced_prompt
        ),
    )
    return result.data["id"]

async def get_request_details_with_sources(
    db: PostgresConnection, request_id: int
) -> dict | None:
    """Fetches the main generation request and all its associated source images."""
    sql_request = "SELECT * FROM generation_requests WHERE id = $1"
    request_res = await db.fetchrow(sql_request, (request_id,))
    if not request_res.data:
        return None

    request_data = request_res.data

    sql_images = "SELECT file_unique_id, file_id, role FROM generation_source_images WHERE request_id = $1"
    images_res = await db.fetch(sql_images, (request_id,))

    request_data["source_images"] = images_res.data
    return request_data