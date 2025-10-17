# aiogram_bot_template/services/pipelines/image_edit_pipeline/image_edit.py
import io
from PIL import Image
from aiogram.utils.i18n import gettext as _
import asyncpg
import structlog

from aiogram_bot_template.db.db_api.storages import PostgresConnection
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.services import image_cache
from ..base import BasePipeline, PipelineOutput
from .edit_default import PROMPT_IMAGE_EDIT_DEFAULT
from .reframe import PROMPT_IMAGE_REFRAME  # <-- NEW IMPORT
from aiogram_bot_template.keyboards.inline.aspect_ratio import SUPPORTED_ASPECT_RATIOS # <-- NEW IMPORT

def _find_closest_aspect_ratio(width: int, height: int) -> str:
    """
    Finds the closest supported aspect ratio string to the given dimensions.

    Args:
        width: The width of the source image.
        height: The height of the source image.

    Returns:
        The closest matching aspect ratio string (e.g., "9:16").
    """
    if height == 0:
        return "1:1"  # Fallback for invalid dimensions

    target_ratio = width / height
    best_match = "1:1"
    min_diff = float('inf')

    for ratio_str in SUPPORTED_ASPECT_RATIOS:
        try:
            w_str, h_str = ratio_str.split(':')
            supported_ratio = int(w_str) / int(h_str)
            diff = abs(target_ratio - supported_ratio)

            if diff < min_diff:
                min_diff = diff
                best_match = ratio_str
        except (ValueError, ZeroDivisionError):
            continue

    return best_match


class ImageEditPipeline(BasePipeline):
    """
    Pipeline for editing an existing generated image based on a user's text prompt
    or for reframing it to a new aspect ratio.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def prepare_data(self) -> PipelineOutput:
        """
        Prepares data for the image edit/reframe generation. It now handles two
        distinct flows based on the 'is_reframe' flag in the FSM data.
        """
        is_reframe_task = self.gen_data.get("is_reframe", False)
        
        if is_reframe_task:
            await self.update_status_func(_("Preparing your image for reframing..."))
        else:
            await self.update_status_func(_("Preparing your image for editing..."))

        source_generation_id = self.gen_data.get("source_generation_id")
        if not source_generation_id:
            raise ValueError("Missing source generation ID for editing/reframing.")

        db = PostgresConnection(self.db_pool, self.log)
        sql = "SELECT result_image_unique_id FROM generations WHERE id = $1"
        result = await db.fetchrow(sql, (source_generation_id,))

        if not result or not result.data or not result.data.get("result_image_unique_id"):
            raise ValueError(f"Could not find source image for generation_id={source_generation_id}")

        source_image_unique_id = result.data["result_image_unique_id"]
        source_image_url = image_cache.get_cached_image_proxy_url(source_image_unique_id)
        
        final_prompt: str
        aspect_ratio: str

        if is_reframe_task:
            # --- REFRAME FLOW ---
            chosen_ratio = self.gen_data.get("chosen_aspect_ratio")
            if not chosen_ratio:
                raise ValueError("Missing chosen aspect ratio for reframing task.")
            
            final_prompt = PROMPT_IMAGE_REFRAME.replace("{{ASPECT_RATIO}}", chosen_ratio)
            aspect_ratio = chosen_ratio
            self.log.info("Preparing reframe task.", target_ratio=aspect_ratio)

        else:
            # --- TEXT EDIT FLOW ---
            user_prompt = self.gen_data.get("user_prompt")
            if not user_prompt:
                raise ValueError("Missing user prompt for editing task.")

            final_prompt = PROMPT_IMAGE_EDIT_DEFAULT.replace("{{USER_PROMPT}}", user_prompt)
            
            # Fetch image bytes to determine its dimensions for the closest ratio
            image_bytes, content_type = await image_cache.get_cached_image_bytes(source_image_unique_id, self.cache_pool)
            if not image_bytes:
                raise ValueError(f"Could not retrieve image bytes from cache for unique_id={source_image_unique_id}")

            try:
                img = Image.open(io.BytesIO(image_bytes))
                width, height = img.size
                aspect_ratio = _find_closest_aspect_ratio(width, height)
                self.log.info(
                    "Determined closest aspect ratio for edit",
                    source_dims=f"{width}x{height}",
                    calculated_ratio=aspect_ratio
                )
            except Exception:
                self.log.exception("Failed to read image dimensions, falling back to 9:16.")
                aspect_ratio = "9:16"

        quality_level = self.gen_data.get("quality_level", 2)
        tier_config = settings.image_edit.tiers.get(quality_level)
        if not tier_config:
            raise ValueError(f"Tier configuration for image_edit level {quality_level} not found.")

        request_payload = {
            "model": tier_config.model,
            "image_urls": [source_image_url],
            "generation_type": GenerationType.IMAGE_EDIT.value,
            "prompt": final_prompt,
            "temperature": 0.5,
            "aspect_ratio": aspect_ratio,
        }

        metadata = {
            "processed_uids": [source_image_unique_id],
        }

        return PipelineOutput(request_payload=request_payload, caption=None, metadata=metadata)
