import json
from pathlib import Path

from material_colors_grid import (
    Err,
    Ok,
    ProjectDocument,
    create_category,
    create_color,
    create_default_document,
    create_sub_category,
    document_from_dict,
    document_to_json,
    load_document_file,
    parse_imported_document,
    save_json_file,
)
from material_colors_grid.models import BandStyle, Style, WatermarkStyle


def make_document() -> ProjectDocument:
    nested = create_sub_category("Silk", colors=[create_color("Gold", "#ffd700")])
    category = create_category(
        "PLA",
        colors=[create_color("Matte Black", "#111111")],
        sub_categories=[nested],
    )
    style = Style(
        width=800,
        cards_per_row=3,
        card_font_color="#222",
        header=BandStyle(text="Colors", background_color="#eee"),
        watermark=WatermarkStyle(image_path="logo.png", scale=0.3, opacity=1.0),
    )
    return ProjectDocument(categories=(category,), style=style)


def test_round_trip_equality() -> None:
    document = make_document()
    result = parse_imported_document(document_to_json(document))
    assert result == Ok(document)


def test_round_trip_default_document() -> None:
    document = create_default_document()
    assert parse_imported_document(document_to_json(document)) == Ok(document)


def test_compact_json_round_trip() -> None:
    document = make_document()
    text = document_to_json(document, indent=None)
    assert "\n" not in text
    assert parse_imported_document(text) == Ok(document)


def test_json_uses_snake_case_keys() -> None:
    data = json.loads(document_to_json(make_document()))
    assert set(data) == {"categories", "style"}
    assert "sub_categories" in data["categories"][0]
    assert "cards_per_row" in data["style"]


def test_parse_partial_document_fills_defaults() -> None:
    result = parse_imported_document(
        '{"categories": [{"name": "PLA", "colors": [{"name": "A", "hex": "#fff"}]}]}'
    )
    assert isinstance(result, Ok)
    assert result.value.style == Style()
    assert result.value.categories[0].colors[0].hex == "#fff"
    assert result.value.categories[0].id


def test_parse_empty_object() -> None:
    assert parse_imported_document("{}") == Ok(ProjectDocument())


def test_parse_malformed_json() -> None:
    result = parse_imported_document('{"categories": [')
    assert isinstance(result, Err)
    assert result.error.startswith("Invalid JSON at line 1, column ")


def test_parse_non_object_json() -> None:
    result = parse_imported_document("[1, 2]")
    assert isinstance(result, Err)
    assert "expected an object" in result.error


def test_parse_invalid_hex() -> None:
    raw = '{"categories": [{"name": "P", "colors": [{"name": "A", "hex": "#12"}]}]}'
    assert parse_imported_document(raw) == Err(
        'categories[0].colors[0].hex "#12" is invalid (expected 3 or 6 hex digits)'
    )


def test_parse_missing_required_field() -> None:
    raw = '{"categories": [{"name": "P", "colors": [{"name": "A"}]}]}'
    assert parse_imported_document(raw) == Err("categories[0].colors[0].hex is missing")


def test_parse_invalid_style_value() -> None:
    result = parse_imported_document('{"style": {"width": "wide"}}')
    assert result == Err('style.width "wide" is invalid (expected an integer >= 1)')


def test_document_from_dict() -> None:
    assert document_from_dict({}) == Ok(ProjectDocument())
    assert isinstance(document_from_dict({"categories": "x"}), Err)


def test_save_and_load_file(tmp_path: Path) -> None:
    document = make_document()
    target = tmp_path / "doc.json"
    saved = save_json_file(target, document_to_json(document))
    assert saved == Ok(target)
    assert load_document_file(target) == Ok(document)
    assert load_document_file(str(target)) == Ok(document)


def test_load_missing_file_names_path(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    result = load_document_file(missing)
    assert isinstance(result, Err)
    assert str(missing) in result.error


def test_load_directory_is_error(tmp_path: Path) -> None:
    result = load_document_file(tmp_path)
    assert isinstance(result, Err)
    assert str(tmp_path) in result.error


def test_load_non_utf8_file(tmp_path: Path) -> None:
    target = tmp_path / "bad.json"
    target.write_bytes(b"\xff\xfe\x00")
    result = load_document_file(target)
    assert isinstance(result, Err)
    assert str(target) in result.error


def test_load_invalid_content_names_file(tmp_path: Path) -> None:
    target = tmp_path / "broken.json"
    target.write_text("{oops", encoding="utf-8")
    result = load_document_file(target)
    assert isinstance(result, Err)
    assert result.error.startswith(f'"{target}": Invalid JSON')


def test_save_to_missing_directory_names_path(tmp_path: Path) -> None:
    target = tmp_path / "missing" / "doc.json"
    result = save_json_file(target, "{}")
    assert isinstance(result, Err)
    assert str(target) in result.error
