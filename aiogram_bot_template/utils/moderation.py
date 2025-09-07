# aiogram_bot_template/utils/moderation.py
import logging
from openai import AsyncOpenAI

openai_client = AsyncOpenAI()
logger = logging.getLogger(__name__)


async def _moderation_flagged(inputs: list[dict]) -> bool:
    """
    Returns True if the OpenAI moderation endpoint flags the content.

    Returns:
        bool: True if content is flagged as unsafe, otherwise False.
    """
    try:
        resp = await openai_client.moderations.create(
            model="text-moderation-latest", input=inputs, timeout=15
        )

        result = resp.results[0]
        flagged = bool(result.flagged)

        if flagged:
            logger.warning(
                "🚨 Moderation flagged content",
                scores=result.category_scores.dict(),
                categories=result.categories.dict(),
            )

        return flagged  # noqa: TRY300

    except Exception:
        logger.exception("OpenAI moderation call failed")
        # В случае ошибки API, для безопасности считаем контент небезопасным.
        return True


async def is_safe_prompt(prompt: str) -> bool:
    """
    Returns True if the text prompt is considered safe by the moderation API.

    Returns:
        bool: True if prompt is safe, False otherwise.
    """
    # OpenAI API ожидает строку или массив строк, а не сложную структуру.
    # Для простого текста достаточно передать саму строку.
    return not await _moderation_flagged([prompt])


async def is_nsfw_image(image_url: str, *, prompt: str | None = None) -> bool:
    """
    Returns True if the image (and optionally text) violates NSFW rules.
    This function is not currently used but is ready for future implementation.

    Returns:
        bool: True if NSFW is detected, otherwise False.
    """
    inputs = [image_url]
    if prompt:
        inputs.append(prompt)

    return await _moderation_flagged(inputs)
