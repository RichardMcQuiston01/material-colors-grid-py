"""Render a grid of material colors to PNG, JPG, or GIF."""

from __future__ import annotations

from material_colors_grid.color import (
    contrast_ratio,
    parse_hex,
    pick_readable_text_color,
    relative_luminance,
)
from material_colors_grid.defaults import (
    DEFAULT_CATEGORY_ID,
    DEFAULT_CATEGORY_NAME,
    create_category,
    create_color,
    create_default_document,
    create_default_style,
    create_sub_category,
)
from material_colors_grid.io import (
    document_from_dict,
    document_to_json,
    load_document_file,
    parse_imported_document,
    save_json_file,
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
    BorderStyle,
    CardFontStyle,
    Category,
    Color,
    FontsStyle,
    FontStyle,
    Orientation,
    ProjectDocument,
    Style,
    SubCategory,
    WatermarkPosition,
    WatermarkStyle,
)
from material_colors_grid.normalize import normalize_document
from material_colors_grid.ordering import (
    RenderCategory,
    RenderColor,
    RenderModel,
    build_render_model,
)
from material_colors_grid.result import Err, Ok, Result
from material_colors_grid.units import REM_IN_PIXELS, css_size_to_px
from material_colors_grid.validate import (
    is_hex_color,
    is_project_document,
    validate_project_document,
)

__all__ = [
    "BandLayout",
    "BandStyle",
    "BorderStyle",
    "CardFontStyle",
    "CardLayout",
    "Category",
    "Color",
    "DEFAULT_CATEGORY_ID",
    "DEFAULT_CATEGORY_NAME",
    "Err",
    "FontStyle",
    "FontsStyle",
    "HeadingLayout",
    "Layout",
    "Ok",
    "Orientation",
    "ProjectDocument",
    "REM_IN_PIXELS",
    "Rect",
    "RenderCategory",
    "RenderColor",
    "RenderModel",
    "Result",
    "Style",
    "SubCategory",
    "WatermarkPosition",
    "WatermarkStyle",
    "build_render_model",
    "compute_layout",
    "contrast_ratio",
    "create_category",
    "create_color",
    "create_default_document",
    "create_default_style",
    "create_sub_category",
    "css_size_to_px",
    "document_from_dict",
    "document_to_json",
    "is_hex_color",
    "is_project_document",
    "load_document_file",
    "normalize_document",
    "parse_hex",
    "parse_imported_document",
    "pick_readable_text_color",
    "relative_luminance",
    "save_json_file",
    "validate_project_document",
]
