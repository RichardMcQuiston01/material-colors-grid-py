"""Render a grid of material colors to PNG, JPG, or GIF."""

from __future__ import annotations

from material_colors_grid.color import (
    contrast_ratio,
    parse_hex,
    pick_readable_text_color,
    relative_luminance,
)
from material_colors_grid.layout import (
    BandLayout,
    CardLayout,
    HeadingLayout,
    Layout,
    Rect,
    compute_layout,
)
from material_colors_grid.models import (
    BandStyle,
    Category,
    Color,
    ProjectDocument,
    Style,
    WatermarkPosition,
    WatermarkStyle,
)
from material_colors_grid.ordering import (
    RenderCategory,
    RenderColor,
    RenderModel,
    build_render_model,
)
from material_colors_grid.result import Err, Ok, Result

__all__ = [
    "BandLayout",
    "BandStyle",
    "CardLayout",
    "Category",
    "Color",
    "Err",
    "HeadingLayout",
    "Layout",
    "Ok",
    "ProjectDocument",
    "Rect",
    "RenderCategory",
    "RenderColor",
    "RenderModel",
    "Result",
    "Style",
    "WatermarkPosition",
    "WatermarkStyle",
    "build_render_model",
    "compute_layout",
    "contrast_ratio",
    "parse_hex",
    "pick_readable_text_color",
    "relative_luminance",
]
