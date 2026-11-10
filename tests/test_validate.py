import copy
from typing import Any

import pytest

from material_colors_grid import (
    Err,
    Ok,
    is_hex_color,
    is_project_document,
    normalize_document,
    validate_project_document,
)


def make_valid() -> dict[str, Any]:
    raw = normalize_document(
        {
            "categories": [
                {
                    "name": "PLA",
                    "colors": [
                        {"name": "A", "hex": "#fff"},
                        {"name": "B", "hex": "#000000"},
                        {"name": "C", "hex": "#abc"},
                    ],
                }
            ]
        }
    )
    assert isinstance(raw, dict)
    return raw


@pytest.mark.parametrize("value", ["#fff", "#FFF", "#a1B2c3", "#000000"])
def test_is_hex_color_accepts(value: str) -> None:
    assert is_hex_color(value)


@pytest.mark.parametrize(
    "value",
    ["fff", "#ff", "#ffff", "#fffff", "#fffffff", "#ggg", "#12345678", "", "#fff\n"],
)
def test_is_hex_color_rejects_strings(value: str) -> None:
    assert not is_hex_color(value)


@pytest.mark.parametrize("value", [None, 123, ["#fff"], {"hex": "#fff"}])
def test_is_hex_color_rejects_non_strings(value: object) -> None:
    assert not is_hex_color(value)


def test_valid_document_passes() -> None:
    raw = make_valid()
    result = validate_project_document(raw)
    assert isinstance(result, Ok)
    assert result.value is raw
    assert is_project_document(raw)


def test_partial_document_is_not_valid_until_normalized() -> None:
    assert not is_project_document({"categories": []})
    assert is_project_document(normalize_document({"categories": []}))


@pytest.mark.parametrize("raw", [None, [], "x", 5])
def test_non_object_is_rejected(raw: object) -> None:
    result = validate_project_document(raw)
    assert isinstance(result, Err)
    assert "expected an object" in result.error


def test_invalid_hex_message_names_path_and_value() -> None:
    raw = make_valid()
    raw["categories"][0]["colors"][2]["hex"] = "#12"
    result = validate_project_document(raw)
    assert result == Err(
        'categories[0].colors[2].hex "#12" is invalid (expected 3 or 6 hex digits)'
    )


def test_sub_category_color_path() -> None:
    raw = make_valid()
    raw["categories"][0]["subCategories"] = [
        {
            "id": "x",
            "name": "S",
            "colors": [{"id": "z", "name": "N", "hex": "red"}],
        }
    ]
    result = validate_project_document(raw)
    assert result == Err(
        'categories[0].subCategories[0].colors[0].hex "red" is invalid '
        "(expected 3 or 6 hex digits)"
    )


def test_missing_color_hex() -> None:
    raw = make_valid()
    del raw["categories"][0]["colors"][1]["hex"]
    assert validate_project_document(raw) == Err(
        "categories[0].colors[1].hex is missing"
    )


def test_missing_top_level_keys() -> None:
    assert validate_project_document({"style": {}}) == Err("categories is missing")
    assert validate_project_document({"categories": []}) == Err("style is missing")


@pytest.mark.parametrize(
    ("path", "value", "fragment"),
    [
        (("style", "width"), 0, "style.width 0 is invalid"),
        (("style", "width"), True, "style.width true is invalid"),
        (("style", "cardsPerRow"), "4", 'style.cardsPerRow "4" is invalid'),
        (("style", "orientation"), "square", 'style.orientation "square"'),
        (("style", "aspectRatio"), 4, "style.aspectRatio 4 is invalid"),
        (("style", "cardBackground"), "white", 'style.cardBackground "white"'),
        (("style", "border", "rounded"), "yes", 'style.border.rounded "yes"'),
        (("style", "border", "thickness"), "2em", 'style.border.thickness "2em"'),
        (("style", "border", "thickness"), "-1px", 'style.border.thickness "-1px"'),
        (("style", "border", "color"), "#12", 'style.border.color "#12"'),
        (("style", "fonts", "card", "size"), "12zz", 'style.fonts.card.size "12zz"'),
        (("style", "fonts", "card", "color"), "dark", 'style.fonts.card.color "dark"'),
        (("style", "fonts", "category", "color"), "auto", "style.fonts.category.color"),
        (
            ("style", "fonts", "subCategory", "family"),
            1,
            "style.fonts.subCategory.family 1",
        ),
        (("style", "header", "text"), 5, "style.header.text 5 is invalid"),
        (("style", "header", "background"), "green", 'style.header.background "green"'),
        (("style", "footer", "font", "color"), "#1", 'style.footer.font.color "#1"'),
        (("style", "footer", "font", "size"), "big", 'style.footer.font.size "big"'),
        (("style", "watermark", "position"), "center", 'watermark.position "center"'),
        (("style", "watermark", "scale"), 1.5, "style.watermark.scale 1.5 is invalid"),
        (("style", "watermark", "opacity"), -0.1, "style.watermark.opacity -0.1"),
        (("style", "watermark", "dataUrl"), 3, "style.watermark.dataUrl 3"),
        (("style",), "x", 'style "x" is invalid (expected an object)'),
        (("categories",), {}, "categories {} is invalid (expected an array)"),
        (("categories", 0), "x", 'categories[0] "x" is invalid'),
    ],
)
def test_invalid_fields_report_path_and_value(
    path: tuple[str | int, ...], value: object, fragment: str
) -> None:
    raw = make_valid()
    target: Any = raw
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    result = validate_project_document(raw)
    assert isinstance(result, Err)
    assert fragment in result.error


def test_auto_and_hex_font_colors_valid() -> None:
    for font_color in ("auto", "#fff"):
        raw = copy.deepcopy(make_valid())
        raw["style"]["fonts"]["card"]["color"] = font_color
        assert is_project_document(raw)


def test_null_watermark_data_url_is_valid() -> None:
    raw = make_valid()
    assert raw["style"]["watermark"]["dataUrl"] is None
    assert is_project_document(raw)


def test_missing_nested_style_key_is_reported() -> None:
    raw = make_valid()
    del raw["style"]["fonts"]["card"]["size"]
    assert validate_project_document(raw) == Err("style.fonts.card.size is missing")


@pytest.mark.parametrize("size", ["1rem", "0.25rem", "12px", "12", ".5rem", "0"])
def test_css_sizes_are_accepted(size: str) -> None:
    raw = make_valid()
    raw["style"]["border"]["thickness"] = size
    assert is_project_document(raw)
