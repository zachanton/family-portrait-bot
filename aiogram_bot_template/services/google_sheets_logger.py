# aiogram_bot_template/services/google_sheets_logger.py
import asyncio
import json
import time
from datetime import datetime
from typing import Any, List, Tuple

import gspread_asyncio
import structlog
from google.oauth2.service_account import Credentials
from pydantic import BaseModel

from aiogram_bot_template.data.constants import GenerationType
from aiogram_bot_template.data.settings import settings
from aiogram_bot_template.services import image_cache
from aiogram_bot_template.services.image_generation_service import GenerationResult

logger = structlog.get_logger(__name__)

# Map generation types to sheet tab titles
SHEET_TITLE_MAP = {
    GenerationType.CHILD_GENERATION: "Child Generation",
    GenerationType.IMAGE_EDIT: "Image Edit",
    GenerationType.UPSCALE: "Upscale",
    GenerationType.GROUP_PHOTO: "Group Photo",
    GenerationType.GROUP_PHOTO_EDIT: "Group Photo Edit",
}

# ===== Image display settings (keep aspect ratio with IMAGE(...; 1)) =====
IMAGE_MODE = 1  # fit to cell, keep aspect ratio

# Make cells big so images in mode 1 render large
IMG_COL_WIDTH_PX = 320      # width for E, F, G, I (increase if you want bigger)
IMG_ROW_HEIGHT_PX = 320     # height for data rows (visual row 2+)

# 0-based indexes of the image columns: A=0, B=1, ...
IMAGE_COL_INDEXES = (4, 5, 6, 8)  # E, F, G, I
# ========================================================================


class GoogleSheetsLogger:
    """Async logger that writes generation data to Google Sheets."""

    def __init__(self):
        self._agcm = None
        if (
            settings.google
            and settings.google.sheet_id
            and settings.google.service_account_creds_json
        ):
            try:
                creds_json = settings.google.service_account_creds_json.get_secret_value()
                if not creds_json:
                    raise ValueError("Google service account credentials JSON is empty.")

                creds_info = json.loads(creds_json)
                # Use modern Sheets scope + Drive (needed by gspread). No legacy *feeds* scope.
                self._creds = Credentials.from_service_account_info(
                    info=creds_info,
                    scopes=[
                        "https://www.googleapis.com/auth/spreadsheets",
                        "https://www.googleapis.com/auth/drive",
                    ],
                )
                self._agcm = gspread_asyncio.AsyncioGspreadClientManager(lambda: self._creds)
                self.sheet_id = settings.google.sheet_id
                logger.info("Google Sheets Logger initialized.")
            except Exception:
                logger.exception("Failed to initialize Google Sheets Logger.")
                self._agcm = None
        else:
            logger.warning("Google Sheets logging disabled due to missing configuration.")

    async def _apply_dimension_sizes(
        self,
        spreadsheet,   # AsyncioGspreadSpreadsheet
        worksheet,     # AsyncioGspreadWorksheet
    ) -> None:
        """
        Force column widths (E,F,G,I) and row heights (row 2+) in pixels
        so IMAGE(...; 1) appears large while keeping aspect ratio.
        """
        try:
            sheet_gid = worksheet.id  # numeric gid of the tab
            requests: List[dict] = []

            # Set pixel width for image columns (E, F, G, I)
            for col in IMAGE_COL_INDEXES:
                requests.append({
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_gid,
                            "dimension": "COLUMNS",
                            "startIndex": col,
                            "endIndex": col + 1,
                        },
                        "properties": {"pixelSize": IMG_COL_WIDTH_PX},
                        "fields": "pixelSize",
                    }
                })

            # Set pixel height for many data rows (rows are 0-based; 1 -> visual row 2)
            requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_gid,
                        "dimension": "ROWS",
                        "startIndex": 1,
                        "endIndex": 5000,
                    },
                    "properties": {"pixelSize": IMG_ROW_HEIGHT_PX},
                    "fields": "pixelSize",
                }
            })

            # IMPORTANT: call batch_update on the Spreadsheet object, not on Worksheet
            resp = await spreadsheet.batch_update({"requests": requests})
            logger.info(
                "Applied column widths and row heights",
                gid=sheet_gid,
                col_width_px=IMG_COL_WIDTH_PX,
                row_height_px=IMG_ROW_HEIGHT_PX,
                reply_type=str(type(resp)),
            )
        except Exception:
            logger.exception("Failed to set column/row sizes for images.")

    async def _open_spreadsheet(self):
        """Authorize and open the Spreadsheet object."""
        agc = await self._agcm.authorize()
        spreadsheet = await agc.open_by_key(self.sheet_id)
        return spreadsheet

    # --- REFACTORED METHOD ---
    # Now accepts a list of headers to be more reusable
    async def _get_worksheet(
        self, sheet_title: str, headers: List[str]
    ) -> Tuple[Any, Any] | Tuple[None, None]:
        if not self._agcm:
            return None, None
        try:
            spreadsheet = await self._open_spreadsheet()
            try:
                worksheet = await spreadsheet.worksheet(sheet_title)
            except gspread_asyncio.gspread.exceptions.WorksheetNotFound:
                worksheet = await spreadsheet.add_worksheet(title=sheet_title, rows=100, cols=20)
                await worksheet.append_row(headers, value_input_option="USER_ENTERED")
            return spreadsheet, worksheet
        except Exception:
            logger.exception("Failed to access worksheet", sheet_title=sheet_title)
            return None, None

    # --- NEW METHOD: Log Vision Analysis ---
    async def log_vision_analysis(
        self, image_unique_id: str, model_name: str, result_data: dict[str, Any]
    ) -> None:
        if not self._agcm:
            return
        try:
            sheet_title = "Vision Analysis Log"
            headers = ["Timestamp", "Image", "Model", "Vision API Response JSON"]
            _, worksheet = await self._get_worksheet(sheet_title, headers)
            if not worksheet:
                return

            base_url = image_cache.get_cached_image_proxy_url(image_unique_id)
            image_formula = f'=IMAGE("{base_url}?v={int(time.time())}"; 1)'

            row_data = [
                datetime.now().isoformat(),
                image_formula,
                model_name,
                json.dumps(result_data, indent=2, ensure_ascii=False),
            ]
            await worksheet.append_row(row_data, value_input_option="USER_ENTERED")
        except Exception:
            logger.exception("Failed to log vision analysis to Google Sheets.")
    
    # --- NEW METHOD: Log Prompt Enhancement ---
    async def log_prompt_enhancement(
        self,
        user_content: List[dict],
        system_prompt: str,
        model_name: str,
        result_model: BaseModel,
    ) -> None:
        if not self._agcm:
            return
        try:
            sheet_title = "Prompt Enhancer Log"
            headers = ["Timestamp", "Image", "User Request", "System Prompt", "Model", "Enhancer API Response JSON"]
            _, worksheet = await self._get_worksheet(sheet_title, headers)
            if not worksheet:
                return

            image_formula = "-"
            user_request_text = "-"
            for part in user_content:
                if part.get("type") == "image_url":
                    url = part.get("image_url", {}).get("url", "")
                    if url:
                        image_formula = f'=IMAGE("{url}?v={int(time.time())}"; 1)'
                elif part.get("type") == "text":
                    user_request_text = part.get("text", "-")

            row_data = [
                datetime.now().isoformat(),
                image_formula,
                user_request_text,
                system_prompt,
                model_name,
                result_model.model_dump_json(indent=2),
            ]
            await worksheet.append_row(row_data, value_input_option="USER_ENTERED")
        except Exception:
            logger.exception("Failed to log prompt enhancement to Google Sheets.")

    async def log_generation(
        self,
        gen_data: dict[str, Any],
        result: GenerationResult,
        output_image_unique_id: str,
    ) -> None:
        if not self._agcm:
            return

        try:
            gen_type = GenerationType(gen_data.get("type"))
            sheet_title = SHEET_TITLE_MAP.get(gen_type)
            if not sheet_title:
                logger.warning("No sheet title mapping for generation type", type=str(gen_type))
                return

            # --- UPDATED CALL ---
            # Now we pass the correct headers for this specific sheet
            headers = [
                "Timestamp", "Generation Type", "Quality", "Trial Type",
                "Input Image 1", "Input Image 2", "Input Image 3",
                "API Request Payload", "Output Image", "Generation Time (ms)"
            ]
            spreadsheet, worksheet = await self._get_worksheet(sheet_title, headers)
            if not worksheet:
                return

            input_image_formulas: List[str] = []
            if source_images := gen_data.get("source_images"):
                for img in source_images:
                    base_url = image_cache.get_cached_image_proxy_url(img["file_unique_id"])
                    cache_busting_url = f"{base_url}?v={int(time.time())}"
                    input_image_formulas.append(f'=IMAGE("{cache_busting_url}"; {IMAGE_MODE})')
            input_image_formulas.extend(["-"] * (3 - len(input_image_formulas)))

            base_output_url = image_cache.get_cached_image_proxy_url(output_image_unique_id)
            cache_busting_output_url = f"{base_output_url}?v={int(time.time())}"
            output_image_formula = f'=IMAGE("{cache_busting_output_url}"; {IMAGE_MODE})'

            row_data = [
                datetime.now().isoformat(),
                gen_type.value,
                gen_data.get("quality_level", "N/A"),
                gen_data.get("trial_type", "-"),
                *input_image_formulas,
                json.dumps(result.request_payload, indent=2, ensure_ascii=False),
                output_image_formula,
                result.generation_time_ms,
            ]

            await worksheet.append_row(row_data, value_input_option="USER_ENTERED")
            logger.info("Logged generation row", sheet=sheet_title, gid=worksheet.id, image_mode=IMAGE_MODE)

            await self._apply_dimension_sizes(spreadsheet, worksheet)

        except Exception:
            logger.exception("Failed to log generation to Google Sheets.")