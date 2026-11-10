import copy
import json
from dataclasses import asdict
from typing import Any

from material_colors_grid import Style, normalize_document


def test_empty_object_gets_defaults() -> None:
    result = normalize_document({})
    assert result == {"categories": [], "style": asdict(Style())}


def test_partial_style_keeps_provided_and_fills_rest() -> None:
    result: Any = normalize_document(
        {"style": {"width": 800, "header": {"text": "Hi"}}}
    )
    assert result["style"]["width"] == 800
    assert result["style"]["height"] == 1280
    assert result["style"]["header"]["text"] == "Hi"
    assert result["style"]["header"]["font_color"] == "#000000"
    assert result["style"]["watermark"]["position"] == "bottom-right"


def test_missing_ids_and_lists_are_filled() -> None:
    result: Any = normalize_document(
        {"categories": [{"name": "PLA", "colors": [{"name": "A", "hex": "#fff"}]}]}
    )
    category = result["categories"][0]
    assert isinstance(category["id"], str) and category["id"]
    assert category["sub_categories"] == []
    assert isinstance(category["colors"][0]["id"], str)


def test_required_user_data_is_not_invented() -> None:
    result: Any = normalize_document({"categories": [{"colors": [{"name": "A"}]}]})
    assert "name" not in result["categories"][0]
    assert "hex" not in result["categories"][0]["colors"][0]


def test_null_style_value_falls_back_to_default() -> None:
    result: Any = normalize_document({"style": {"width": None}})
    assert result["style"]["width"] == 1440


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
