"""Meeting history helpers and history viewer generation."""

from __future__ import annotations

import html
import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import MEETING_OUTPUT_DIR

logger = logging.getLogger(__name__)


def get_meeting_summaries() -> list[dict[str, Any]]:
    """Return meeting PDF files sorted newest first."""
    summaries: list[dict[str, Any]] = []
    directory = Path(MEETING_OUTPUT_DIR)
    if not directory.exists():
        return summaries

    for path in directory.glob("*.pdf"):
        try:
            filename = path.name
            date_obj = datetime.fromtimestamp(path.stat().st_mtime)
            if "Meeting_Summary_" in filename or "Meeting_Transcript_" in filename:
                timestamp = filename.replace("Meeting_Summary_", "").replace("Meeting_Transcript_", "")
                timestamp = timestamp.replace(".pdf", "")
                try:
                    date_obj = datetime.strptime(timestamp, "%Y-%m-%d_%H-%M-%S")
                except ValueError:
                    pass

            summaries.append(
                {
                    "path": str(path),
                    "filename": filename,
                    "date": date_obj,
                    "title": filename.replace("Meeting_Summary_", "").replace("Meeting_Transcript_", ""),
                    "size": path.stat().st_size,
                }
            )
        except Exception as exc:
            logger.warning("Could not parse meeting file %s: %s", path, exc)

    summaries.sort(key=lambda item: item["date"], reverse=True)
    return summaries


def export_summary_to_pdf(source_path: str) -> str | None:
    """Create a copy of an existing summary PDF for export workflows."""
    source = Path(source_path)
    if not source.exists():
        return None

    target = source.with_name(f"{source.stem}_exported.pdf")
    try:
        shutil.copy2(source, target)
        logger.info("Exported PDF copy: %s", target)
        return str(target)
    except Exception as exc:
        logger.error("Failed to export %s: %s", source_path, exc)
        return None


def delete_summary(filepath: str) -> bool:
    """Delete a summary PDF."""
    try:
        os.remove(filepath)
        logger.info("Deleted summary: %s", filepath)
        return True
    except Exception as exc:
        logger.error("Failed to delete %s: %s", filepath, exc)
        return False


def generate_history_html(output_path: str | None = None) -> str:
    """Generate a scrollable HTML history page for the default browser."""
    if output_path is None:
        output_path = str(Path(MEETING_OUTPUT_DIR) / "Meeting_History.html")

    summaries = get_meeting_summaries()
    rows = []
    for item in summaries:
        date_str = item["date"].strftime("%b %d, %Y %I:%M %p")
        escaped_title = html.escape(str(item["title"]))
        escaped_path = html.escape(str(item["path"]))
        rows.append(
            f"""
            <div class=\"card\">
              <div class=\"meta\">{html.escape(date_str)} · {item['size'] // 1024} KB</div>
              <div class=\"title\">{escaped_title}</div>
              <div class=\"actions\">
                <a href=\"file://{escaped_path}\">Open PDF</a>
                <a href=\"file://{escaped_path}\">Reveal in Finder</a>
              </div>
            </div>
            """
        )

    if not rows:
        rows.append("<p class='empty'>No meeting summaries yet.</p>")

    html_content = f"""<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>AIM Flow Meeting History</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; background: #f6f3ef; color: #141414; }}
    header {{ position: sticky; top: 0; background: rgba(246,243,239,0.94); backdrop-filter: blur(10px); padding: 20px 24px; border-bottom: 1px solid #ddd; }}
    h1 {{ margin: 0; font-size: 22px; }}
    .sub {{ color: #666; margin-top: 6px; }}
    main {{ padding: 20px 24px 32px; display: grid; gap: 12px; }}
    .card {{ background: white; border: 1px solid #e3dfda; border-radius: 16px; padding: 16px 18px; box-shadow: 0 6px 18px rgba(0,0,0,0.04); }}
    .meta {{ font-size: 12px; color: #777; margin-bottom: 6px; }}
    .title {{ font-size: 16px; font-weight: 600; margin-bottom: 10px; word-break: break-word; }}
    .actions {{ display: flex; gap: 12px; flex-wrap: wrap; }}
    .actions a {{ color: #0a5; text-decoration: none; font-weight: 600; }}
    .actions a:hover {{ text-decoration: underline; }}
    .empty {{ color: #666; font-style: italic; }}
  </style>
</head>
<body>
  <header>
    <h1>AIM Flow Meeting History</h1>
    <div class=\"sub\">Scroll through past meeting PDFs and open them from here.</div>
  </header>
  <main>
    {''.join(rows)}
  </main>
</body>
</html>"""

    Path(output_path).write_text(html_content, encoding="utf-8")
    return output_path


def open_history_viewer() -> None:
    """Open the generated history HTML in the default browser."""
    history_path = generate_history_html()
    subprocess.run(["open", history_path], check=False)
