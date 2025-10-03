# file: aiogram_bot_template/services/observability/local_file_logger.py
import os
import uuid
import json
import html
import datetime as dt
from pathlib import Path
from typing import List, Optional, Dict, Any

import structlog
from aiogram_bot_template.services.utils import http_client

logger = structlog.get_logger(__name__)


def _ensure_parent_and_write_bytes(path: Path, data: bytes) -> None:
    """Safely writes bytes to a file, creating parent directories if needed."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
    except OSError:
        logger.exception("Failed to write bytes to file", path=str(path))


def _ensure_parent_and_write_text(path: Path, text: str) -> None:
    """Safely writes text to a file, creating parent directories if needed."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        logger.exception("Failed to write text to file", path=str(path))


def _ext_from_content_type(ct: Optional[str]) -> str:
    """Determines a file extension from a MIME type string."""
    if not ct:
        return "bin"
    ct = ct.lower().split(";")[0].strip()
    return {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/webp": "webp",
        "image/gif": "gif",
        "image/bmp": "bmp",
        "image/tiff": "tiff",
    }.get(ct, "bin")


async def _download_inputs_for_archive(urls: List[str], dst_dir: Path) -> List[str]:
    """
    Downloads input images from their URLs for archival.

    Args:
        urls: A list of public URLs to the input images.
        dst_dir: The destination directory (e.g., 'gen-logs/.../input').

    Returns:
        A list of the relative file paths saved.
    """
    if not urls:
        return []
    session = await http_client.session()
    saved: List[str] = []
    for i, url in enumerate(urls):
        try:
            async with session.get(url, timeout=60) as resp:
                resp.raise_for_status()
                data = await resp.read()
                ext = _ext_from_content_type(resp.headers.get("Content-Type"))
                name = f"input_{i:02d}.{ext}"
                out_path = dst_dir / name
                _ensure_parent_and_write_bytes(out_path, data)
                saved.append(name)
        except Exception:
            logger.warning("Failed to download input image for logging", url=url)
    return saved


def _make_request_html(
    prompt: str,
    params: Dict[str, Any],
    input_files: List[str],
    output_files: List[str],
) -> str:
    """Creates a self-contained HTML page to view a single generation log."""
    prompt_safe = html.escape(prompt)
    params_json = json.dumps(params or {}, ensure_ascii=False, indent=2)
    inputs_html = (
        "".join(
            f'<div class="card"><img src="input/{html.escape(p)}" loading="lazy"><small>input/{html.escape(p)}</small></div>'
            for p in input_files
        )
        or "<p><i>No input images</i></p>"
    )
    outputs_html = "".join(
        f'<div class="card"><img src="output/{html.escape(p)}" loading="lazy"><small>output/{html.escape(p)}</small></div>'
        for p in output_files
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Image Generation Log</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 2rem; background-color: #f9fafb; color: #111827; }}
h1 {{ font-size: 1.25rem; font-weight: 600; margin-bottom: 0.75rem; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.5rem; }}
pre {{ white-space: pre-wrap; word-wrap: break-word; background-color: #f3f4f6; padding: 1rem; border-radius: 0.5rem; font-size: 0.875rem; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(256px, 1fr)); gap: 1rem; }}
.card {{ background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 0.75rem; padding: 0.75rem; box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); }}
img {{ width: 100%; height: auto; border-radius: 0.5rem; margin-bottom: 0.5rem; }}
small {{ color: #6b7280; font-size: 0.75rem; }}
</style>
</head>
<body>
<h1>Prompt</h1>
<pre>{prompt_safe}</pre>
<h1>Parameters</h1>
<pre>{html.escape(params_json)}</pre>
<h1>Inputs</h1>
<div class="grid">{inputs_html}</div>
<h1>Outputs</h1>
<div class="grid">{outputs_html}</div>
</body>
</html>"""


def _append_to_root_index(
    root_dir: Path,
    request_id: str,
    prompt: str,
    model: str,
    timestamp: dt.datetime,
    user_id: Optional[int],
) -> None:
    """Appends a link to the main index.html for easy navigation."""
    index_path = root_dir / "index.html"
    day_folder = timestamp.strftime("%Y-%m-%d")
    link = f"{day_folder}/{request_id}/view.html"
    time_str = timestamp.strftime("%H:%M:%S UTC")
    
    user_html = f'[<small>User: {user_id}</small>]' if user_id else ''

    line = (
        f'<li><a href="{html.escape(link)}">{html.escape(request_id)}</a> '
        f'[<small>{time_str}</small>] {user_html} '
        f'[<small>{html.escape(model)}</small>] &mdash; '
        f"{html.escape(prompt[:120])}...</li>\n"
    )

    if not index_path.exists():
        _ensure_parent_and_write_text(
            index_path,
            "<!doctype html>\n<html><head><meta charset='utf-8'>"
            "<title>Image Generation Logs</title>"
            "<style>body{font-family:system-ui,sans-serif;margin:2rem}ul{list-style:none;padding:0}li{margin-bottom:0.5rem;}a{text-decoration:none;color:#1d4ed8}a:hover{text-decoration:underline}small{color:#6b7280;margin:0 0.25rem}</style>"
            "</head><body>"
            "<h1>Image Generation Logs</h1><ul>\n"
            f"{line}"
            "</ul></body></html>\n",
        )
        return

    with open(index_path, "r+", encoding="utf-8") as f:
        content = f.read()
        pos = content.find("<ul>")
        if pos == -1:
            # Fallback if <ul> is somehow missing
            new_content = content.replace("</body>", f"<ul>\n{line}</ul></body>")
        else:
            # Insert the new line right after the <ul> tag
            insert_pos = pos + len("<ul>\n")
            new_content = content[:insert_pos] + line + content[insert_pos:]
        
        f.seek(0)
        f.write(new_content)
        f.truncate()


async def log_generation_to_disk(
    *,
    prompt: str,
    model_name: str,
    user_id: Optional[int] = None,
    image_urls: Optional[List[str]] = None,
    params: Optional[Dict[str, Any]] = None,
    output_image_bytes: bytes,
    output_content_type: str,
    base_dir: str = "gen-logs",
) -> None:
    """
    Saves the inputs and outputs of an AI generation to a local directory
    with a self-contained HTML viewer.

    Args:
        prompt: The text prompt sent to the AI.
        model_name: The name of the model used for generation.
        user_id: The Telegram User ID of the requestor.
        image_urls: A list of public URLs for input images.
        params: A dictionary of other parameters sent to the AI.
        output_image_bytes: The generated image bytes.
        output_content_type: The MIME type of the generated image.
        base_dir: The root directory for storing logs.
    """
    try:
        timestamp = dt.datetime.utcnow()
        root = Path(base_dir)
        request_id = uuid.uuid4().hex[:12]
        day_folder = timestamp.strftime("%Y-%m-%d")
        run_dir = root / day_folder / request_id
        input_dir = run_dir / "input"
        output_dir = run_dir / "output"

        input_rel_files: List[str] = []
        if image_urls:
            input_rel_files = await _download_inputs_for_archive(image_urls, input_dir)

        _ensure_parent_and_write_text(run_dir / "prompt.txt", prompt)
        _ensure_parent_and_write_text(
            run_dir / "params.json", json.dumps(params or {}, ensure_ascii=False, indent=2)
        )

        out_ext = _ext_from_content_type(output_content_type)
        out_name = f"output_00.{out_ext}"
        _ensure_parent_and_write_bytes(output_dir / out_name, output_image_bytes)

        html_doc = _make_request_html(prompt, params or {}, input_rel_files, [out_name])
        _ensure_parent_and_write_text(run_dir / "view.html", html_doc)

        _append_to_root_index(root, request_id, prompt, model_name, timestamp, user_id)
        
        logger.info("Generation logged to disk", path=str(run_dir.resolve()))

    except Exception:
        logger.exception("Failed to log generation to disk.")
