"""System-tray icon rendering for Linux using Pillow (PIL).

Mirrors the public API of visuals.py (macOS/AppKit) so that app_linux.py can
swap implementations without touching any shared logic.

Rendered icon size: TRAY_ICON_SIZE × TRAY_ICON_SIZE pixels (default 64).
pystray accepts PIL.Image objects directly, so no temp-file round-trips are
needed.

State mapping (identical concept to macOS):
  idle        — logo only
  recording   — logo + animated waveform bars (right-side overlay)
  processing  — logo + pulsing dots (right-side overlay)
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw

from . import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal geometry (scaled to TRAY_ICON_SIZE)
# ---------------------------------------------------------------------------

_S = config.TRAY_ICON_SIZE           # e.g. 64
_SCALE = _S / config.STATUS_ICON_HEIGHT   # macOS baseline → pixel scale

# Waveform panel width in pixels (mirrors macOS STATUS_WAVE_WIDTH scaled up).
_WAVE_PANEL_PX = int(config.STATUS_WAVE_WIDTH * _SCALE)
_LOGO_PX = _S                        # logo fills the square icon
_SPACING_PX = max(2, int(config.STATUS_ITEM_SPACING * _SCALE))

# Bar geometry
_BAR_W = max(3, int(config.WAVE_BAR_WIDTH * _SCALE))
_BAR_GAP = max(2, int(config.WAVE_BAR_GAP * _SCALE))
_BAR_MIN_H = max(4, int(config.WAVE_MIN_HEIGHT * _SCALE))
_BAR_MAX_H = min(_S - 4, int(config.WAVE_MAX_HEIGHT * _SCALE))

# Dot geometry (processing indicator)
_DOT_SIZE = max(4, int(4.0 * _SCALE))
_DOT_SPACING = max(6, int(8.0 * _SCALE))
_DOT_Y = (_S - _DOT_SIZE) // 2

# Waveform bar colour: matches macOS (0.08, 0.08, 0.10, 1.0)
_BAR_COLOR = (20, 20, 26, 255)


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

class StatusIconRenderer:
    """Builds PIL Images for idle, recording, and processing states."""

    def __init__(self) -> None:
        self._base_logo = self._load_logo()

    # ------------------------------------------------------------------
    # Public state images (mirrors macOS API)
    # ------------------------------------------------------------------

    def idle_image(self) -> Image.Image:
        return self._composite_image(None, None)

    def recording_image(self, levels: Sequence[float]) -> Image.Image:
        return self._composite_image(levels, None)

    def processing_image(self, phase: float) -> Image.Image:
        return self._composite_image(None, phase)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_logo(self) -> Image.Image:
        path = config.resource_path(config.STATUS_LOGO_NAME)
        try:
            img = Image.open(str(path)).convert("RGBA")
        except FileNotFoundError:
            logger.warning("Status logo not found at %s; using blank icon", path)
            img = Image.new("RGBA", (_S, _S), (0, 0, 0, 0))
        img = img.resize((_S, _S), Image.LANCZOS)
        return img

    def _composite_image(
        self,
        levels: Sequence[float] | None,
        processing_phase: float | None,
    ) -> Image.Image:
        has_panel = levels is not None or processing_phase is not None
        total_width = _LOGO_PX + (_SPACING_PX + _WAVE_PANEL_PX if has_panel else 0)

        # Start with a transparent canvas.
        canvas = Image.new("RGBA", (total_width, _S), (0, 0, 0, 0))
        canvas.paste(self._base_logo, (0, 0), self._base_logo)

        if has_panel:
            draw = ImageDraw.Draw(canvas)
            panel_x = _LOGO_PX + _SPACING_PX
            if levels is not None:
                self._draw_waveform(draw, panel_x, levels)
            elif processing_phase is not None:
                self._draw_processing_indicator(draw, panel_x, processing_phase)

        return canvas

    def _draw_waveform(
        self,
        draw: ImageDraw.ImageDraw,
        panel_x: int,
        levels: Sequence[float],
    ) -> None:
        total_bar_width = (
            config.WAVE_BAR_COUNT * _BAR_W
            + (config.WAVE_BAR_COUNT - 1) * _BAR_GAP
        )
        origin_x = panel_x + max((_WAVE_PANEL_PX - total_bar_width) // 2, 0)

        for index, level in enumerate(levels):
            height = int(_BAR_MIN_H + level * (_BAR_MAX_H - _BAR_MIN_H))
            height = max(_BAR_MIN_H, min(_BAR_MAX_H, height))
            x = origin_x + index * (_BAR_W + _BAR_GAP)
            y = (_S - height) // 2
            radius = _BAR_W // 2
            self._draw_rounded_rect(draw, x, y, _BAR_W, height, radius, _BAR_COLOR)

    def _draw_processing_indicator(
        self,
        draw: ImageDraw.ImageDraw,
        panel_x: int,
        phase: float,
    ) -> None:
        alpha = int(255 * (0.35 + 0.45 * (0.5 + 0.5 * math.sin(phase))))
        color = (20, 20, 26, alpha)
        for i in range(3):
            x = panel_x + i * _DOT_SPACING
            radius = _DOT_SIZE // 2
            self._draw_rounded_rect(draw, x, _DOT_Y, _DOT_SIZE, _DOT_SIZE, radius, color)

    @staticmethod
    def _draw_rounded_rect(
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        w: int,
        h: int,
        radius: int,
        fill: tuple,
    ) -> None:
        """Draw a filled rounded rectangle (works on Pillow >= 8.2 and older)."""
        try:
            draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill)
        except AttributeError:
            # Pillow < 8.2 fallback: plain rectangle.
            draw.rectangle([x, y, x + w, y + h], fill=fill)
