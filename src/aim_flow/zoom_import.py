"""Import and parse Zoom/Teams transcript files."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def parse_vtt_transcript(vtt_path: str) -> Optional[str]:
    """Parse a VTT transcript file into plain text."""
    try:
        content = Path(vtt_path).read_text(encoding="utf-8")
        lines: list[str] = []
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line == "WEBVTT":
                continue
            if line.isdigit() or "-->" in line:
                continue
            if re.match(r"^NOTE\b", line):
                continue
            lines.append(line)

        transcript = "\n".join(lines).strip()
        logger.info("Parsed VTT transcript: %d chars", len(transcript))
        return transcript or None
    except Exception as exc:
        logger.error("Failed to parse VTT file %s: %s", vtt_path, exc)
        return None


def parse_srt_transcript(srt_path: str) -> Optional[str]:
    """Parse an SRT transcript file into plain text."""
    try:
        content = Path(srt_path).read_text(encoding="utf-8")
        lines = []
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.isdigit() or "-->" in line:
                continue
            lines.append(line)

        transcript = "\n".join(lines).strip()
        logger.info("Parsed SRT transcript: %d chars", len(transcript))
        return transcript or None
    except Exception as exc:
        logger.error("Failed to parse SRT file %s: %s", srt_path, exc)
        return None
