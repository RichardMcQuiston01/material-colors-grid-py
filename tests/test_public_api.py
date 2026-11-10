import material_colors_grid as package

EXPECTED_EXPORTS: list[str] = [
    "BandLayout",
    "BandStyle",
    "CardLayout",
    "Category",
    "Color",
    "Err",
    "HeadingLayout",
    "ImageFormat",
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
    "create_category",
    "create_color",
    "create_default_document",
    "create_sub_category",
    "document_from_dict",
    "document_to_json",
    "image_to_bytes",
    "is_hex_color",
    "is_project_document",
    "load_document_file",
    "normalize_document",
    "parse_hex",
    "parse_imported_document",
    "pick_readable_text_color",
    "relative_luminance",
    "render_to_image",
    "save_image",
    "save_json_file",
    "validate_project_document",
]


def test_public_api_exports_are_stable() -> None:
    assert sorted(package.__all__) == EXPECTED_EXPORTS


def test_every_export_resolves() -> None:
    for name in package.__all__:
        assert hasattr(package, name), f"Missing export: {name}"
