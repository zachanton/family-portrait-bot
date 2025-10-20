# aiogram_bot_template/services/local_file_logger.py
import datetime as dt
import html
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

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
        dst_dir: The destination directory (e.g., '.../input').

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
    prompt_safe_for_html = html.escape(prompt)
    # For JavaScript, we need to escape backticks, backslashes, and use template literal-safe quotes.
    prompt_safe_for_js = prompt.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
    
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
.copy-btn {{ display: block; width: 100%; padding: 0.75rem; margin-top: 1rem; margin-bottom: 1.5rem; background-color: #4f46e5; color: white; border: none; border-radius: 0.5rem; font-size: 1rem; font-weight: 500; cursor: pointer; transition: background-color 0.2s; }}
.copy-btn:hover {{ background-color: #4338ca; }}
.copy-btn:active {{ background-color: #3730a3; }}
</style>
</head>
<body>
<h1>Prompt</h1>
<pre id="prompt-text">{prompt_safe_for_html}</pre>
<button class="copy-btn" onclick="copyPrompt()">Copy Prompt</button>

<h1>Parameters</h1>
<pre>{html.escape(params_json)}</pre>
<h1>Inputs</h1>
<div class="grid">{inputs_html}</div>
<h1>Outputs</h1>
<div class="grid">{outputs_html}</div>

<script>
function copyPrompt() {{
    const textToCopy = `{prompt_safe_for_js}`;
    navigator.clipboard.writeText(textToCopy).then(() => {{
        const btn = document.querySelector('.copy-btn');
        const originalText = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(() => {{
            btn.textContent = originalText;
        }}, 2000);
    }}, (err) => {{
        console.error('Failed to copy text: ', err);
    }});
}}
</script>
</body>
</html>"""


def _update_index_file(index_path: Path, title: str, new_line: str, link_target: str) -> None:
    """
    Creates or idempotently updates an index.html file.

    Args:
        index_path: The path to the index.html file.
        title: The title for the HTML document.
        new_line: The new <li>...</li> line to add.
        link_target: The href target to check for idempotency.
    """
    if not index_path.exists():
        _ensure_parent_and_write_text(
            index_path,
            f"<!doctype html>\n<html lang='en'><head><meta charset='utf-8'>"
            f"<title>{html.escape(title)}</title>"
            "<style>body{{font-family:system-ui,sans-serif;margin:2rem}}ul{{list-style:none;padding:0}}li{{margin-bottom:0.5rem;background-color:#fff;padding:0.75rem;border-radius:0.5rem;border:1px solid #e5e7eb}}a{{text-decoration:none;color:#1d4ed8;font-weight:500}}a:hover{{text-decoration:underline}}small{{color:#6b7280;margin:0 0.25rem}}</style>"
            f"</head><body>"
            f"<h1>{html.escape(title)}</h1><ul>\n{new_line}"
            "</ul></body></html>\n",
        )
        return

    with open(index_path, "r+", encoding="utf-8") as f:
        content = f.read()
        # Check if the link already exists to prevent duplicates
        if f'href="{html.escape(link_target)}"' in content:
            return

        pos = content.find("<ul>")
        if pos == -1:
            # Fallback if <ul> is somehow missing
            new_content = content.replace("</body>", f"<ul>\n{new_line}</ul></body>")
        else:
            insert_pos = pos + len("<ul>\n")
            new_content = content[:insert_pos] + new_line + content[insert_pos:]
        
        f.seek(0)
        f.write(new_content)
        f.truncate()


async def log_generation_to_disk(
    *,
    prompt: str,
    model_name: str,
    generation_type: str,
    user_id: Optional[int] = None,
    image_urls: Optional[List[str]] = None,
    params: Optional[Dict[str, Any]] = None,
    output_image_bytes: bytes,
    output_content_type: str,
    base_dir: str = "gen-logs",
) -> None:
    """
    Saves the inputs and outputs of an AI generation to a local directory
    with a hierarchical, self-contained HTML viewer.

    Structure:
    - base_dir/YYYY-MM-DD/index.html (links to users)
    - base_dir/YYYY-MM-DD/{user_id}/index.html (links to generations)
    - base_dir/YYYY-MM-DD/{user_id}/{gen_type}_{uuid}/ (generation assets)

    Args:
        prompt: The text prompt sent to the AI.
        model_name: The name of the model used for generation.
        generation_type: The type of generation (e.g., 'child_generation').
        user_id: The Telegram User ID of the requestor.
        image_urls: A list of public URLs for input images.
        params: A dictionary of other parameters sent to the AI.
        output_image_bytes: The generated image bytes.
        output_content_type: The MIME type of the generated image.
        base_dir: The root directory for storing logs.
    """
    try:
        timestamp = dt.datetime.utcnow()
        user_id_str = str(user_id) if user_id is not None else "unknown_user"
        request_id = uuid.uuid4().hex[:12]

        # 1. Define Paths
        root_dir = Path(base_dir)
        day_dir_name = timestamp.strftime("%Y-%m-%d")
        day_dir = root_dir / day_dir_name
        user_dir = day_dir / user_id_str
        run_dir_name = f"{generation_type}_{request_id}"
        run_dir = user_dir / run_dir_name
        
        # 2. Save Generation Artifacts
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

        # 3. Update Hierarchical Indexes
        time_str = timestamp.strftime("%H:%M:%S UTC")

        # Update User's index for the day
        user_index_path = user_dir / "index.html"
        user_index_title = f"Generations for User {user_id_str} on {day_dir_name}"
        user_index_link_target = f"{run_dir_name}/view.html"
        user_index_line = (
            f'<li><a href="{html.escape(user_index_link_target)}">{html.escape(run_dir_name)}</a> '
            f'[<small>{time_str}</small>] '
            f'[<small>{html.escape(model_name)}</small>] &mdash; '
            f"{html.escape(prompt[:120])}...</li>\n"
        )
        _update_index_file(user_index_path, user_index_title, user_index_line, user_index_link_target)

        # Update Day's index
        day_index_path = day_dir / "index.html"
        day_index_title = f"User Activity on {day_dir_name}"
        day_index_link_target = f"{user_id_str}/index.html"
        day_index_line = (
            f'<li><a href="{html.escape(day_index_link_target)}">User ID: {user_id_str}</a> '
            f'[<small>Last activity: {time_str}</small>]</li>\n'
        )
        _update_index_file(day_index_path, day_index_title, day_index_line, day_index_link_target)
        
        logger.info("Generation logged to disk", path=str(run_dir.resolve()))

    except Exception:
        logger.exception("Failed to log generation to disk.")