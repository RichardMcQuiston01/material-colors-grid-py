import material_colors_grid as package

EXPECTED_EXPORTS: list[str] = [
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


def test_public_api_exports_are_stable() -> None:
    assert sorted(package.__all__) == EXPECTED_EXPORTS


def test_every_export_resolves() -> None:
    for name in package.__all__:
        assert hasattr(package, name), f"Missing export: {name}"
