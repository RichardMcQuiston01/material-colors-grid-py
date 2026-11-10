import copy
import json
from typing import Any

from material_colors_grid import ProjectDocument, document_to_json, normalize_document


def test_empty_object_gets_defaults() -> None:
    result = normalize_document({})
    assert result == {"categories": [], "style": default_style_json()}


def default_style_json() -> dict[str, Any]:
    style: dict[str, Any] = json.loads(document_to_json(ProjectDocument()))["style"]
    return style


def test_normalize_defaults_equal_model_defaults() -> None:
    result: Any = normalize_document({})
    assert result["style"] == default_style_json()


def test_partial_style_keeps_provided_and_fills_rest() -> None:
    result: Any = normalize_document(
        {"style": {"width": 800, "header": {"text": "Hi"}}}
    )
    assert result["style"]["width"] == 800
    assert result["style"]["height"] == 1280
    assert result["style"]["header"]["text"] == "Hi"
    assert result["style"]["header"]["background"] == "#1b5e20"
    assert result["style"]["header"]["font"]["size"] == "1.5rem"
    assert result["style"]["watermark"]["position"] == "bottom-right"


def test_missing_ids_and_lists_are_filled() -> None:
    result: Any = normalize_document(
        {"categories": [{"name": "PLA", "colors": [{"name": "A", "hex": "#fff"}]}]}
    )
    category = result["categories"][0]
    assert isinstance(category["id"], str) and category["id"]
    assert category["subCategories"] == []
    assert isinstance(category["colors"][0]["id"], str)


def test_required_user_data_is_not_invented() -> None:
    result: Any = normalize_document({"categories": [{"colors": [{"name": "A"}]}]})
    assert "name" not in result["categories"][0]
    assert "hex" not in result["categories"][0]["colors"][0]


def test_null_style_value_falls_back_to_default() -> None:
    result: Any = normalize_document({"style": {"width": None}})
    assert result["style"]["width"] == 1440


def test_null_watermark_data_url_stays_null() -> None:
    result: Any = normalize_document({"style": {"watermark": {"dataUrl": None}}})
    assert result["style"]["watermark"]["dataUrl"] is None


def test_sub_categories_get_ids_and_colors() -> None:
    result: Any = normalize_document(
        {"categories": [{"name": "P", "subCategories": [{"name": "S"}]}]}
    )
    sub_category = result["categories"][0]["subCategories"][0]
    assert sub_category["colors"] == []
    assert isinstance(sub_category["id"], str) and sub_category["id"]
    assert "subCategories" not in sub_category


def test_input_is_not_mutated() -> None:
    raw = {"categories": [{"name": "A"}], "style": {"width": 1}}
    snapshot = copy.deepcopy(raw)
    normalize_document(raw)
    assert raw == snapshot


def test_never_raises_on_odd_input() -> None:
    odd_inputs: list[object] = [
        None,
        5,
        "x",
        [],
        [1],
        {"categories": 5},
        {"style": 5},
        {"categories": [None, 1, "x"]},
        {"categories": [{"colors": 3}]},
    ]
    for raw in odd_inputs:
        normalize_document(raw)


def test_non_mappings_returned_unchanged() -> None:
    assert normalize_document(None) is None
    assert normalize_document([1]) == [1]


def test_result_is_json_serializable() -> None:
    json.dumps(normalize_document({}))
