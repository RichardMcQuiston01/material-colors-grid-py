import material_colors_grid as package

EXPECTED_EXPORTS: list[str] = [
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
]


def test_public_api_exports_are_stable() -> None:
    assert sorted(package.__all__) == EXPECTED_EXPORTS


def test_every_export_resolves() -> None:
    for name in package.__all__:
        assert hasattr(package, name), f"Missing export: {name}"
