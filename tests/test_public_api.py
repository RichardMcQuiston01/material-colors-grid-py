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


def test_public_api_exports_are_stable() -> None:
    assert sorted(package.__all__) == EXPECTED_EXPORTS


def test_every_export_resolves() -> None:
    for name in package.__all__:
        assert hasattr(package, name), f"Missing export: {name}"
