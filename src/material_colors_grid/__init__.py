"""Render a grid of material colors to PNG, JPG, or GIF."""

from __future__ import annotations

from material_colors_grid.defaults import (
    create_category,
    create_color,
    create_default_document,
    create_sub_category,
)
from material_colors_grid.io import (
    document_from_dict,
    document_to_json,
    load_document_file,
    parse_imported_document,
    save_json_file,
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
from material_colors_grid.normalize import normalize_document
from material_colors_grid.result import Err, Ok, Result
from material_colors_grid.validate import (
    is_hex_color,
    is_project_document,
    validate_project_document,
)

__all__ = [
    "BandStyle",
    "Category",
    "Color",
    "Err",
    "Ok",
    "ProjectDocument",
    "Result",
    "Style",
    "WatermarkPosition",
    "WatermarkStyle",
    "create_category",
    "create_color",
    "create_default_document",
    "create_sub_category",
    "document_from_dict",
    "document_to_json",
    "is_hex_color",
    "is_project_document",
    "load_document_file",
    "normalize_document",
    "parse_imported_document",
    "save_json_file",
    "validate_project_document",
]
