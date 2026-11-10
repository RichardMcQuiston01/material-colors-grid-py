import json

from material_colors_grid import Err, Ok, build_render_model, is_project_document
from material_colors_grid.colorlist import color_list_to_document, parse_color_list
from material_colors_grid.defaults import DEFAULT_CATEGORY_NAME
from material_colors_grid.io import document_to_json


def test_groups_colors_by_category_and_default() -> None:
    result = color_list_to_document(
        [
            {"name": "Matte Black", "hex": "#111111", "category": "PLA"},
            {"name": "White", "hex": "#fff", "category": "PLA"},
            {"name": "Red", "hex": "#ff0000"},
        ]
    )
    assert isinstance(result, Ok)
    names = {
        category.name: len(category.colors) for category in result.value.categories
    }
    assert names == {"PLA": 2, DEFAULT_CATEGORY_NAME: 1}


def test_sub_category_is_nested_under_category() -> None:
    result = color_list_to_document(
        [{"name": "Gold", "hex": "#d4af37", "category": "PLA", "sub_category": "Silk"}]
    )
    assert isinstance(result, Ok)
    (category,) = result.value.categories
    assert category.colors == ()
    assert category.sub_categories[0].name == "Silk"
    assert category.sub_categories[0].colors[0].name == "Gold"


def test_sub_category_without_category_uses_default() -> None:
    result = color_list_to_document(
        [{"name": "Gold", "hex": "#d4af37", "sub_category": "Silk"}]
    )
    assert isinstance(result, Ok)
    assert result.value.categories[0].name == DEFAULT_CATEGORY_NAME


def test_empty_list_gives_default_category() -> None:
    result = color_list_to_document([])
    assert isinstance(result, Ok)
    assert [category.name for category in result.value.categories] == ["Default"]


def test_result_round_trips_as_valid_document() -> None:
    result = color_list_to_document([{"name": "Red", "hex": "#f00"}])
    assert isinstance(result, Ok)
    assert is_project_document(json.loads(document_to_json(result.value)))
    assert build_render_model(result.value) is not None


def test_invalid_hex_names_index_field_and_value() -> None:
    result = color_list_to_document(
        [
            {"name": "Ok", "hex": "#111"},
            {"name": "Matte Black", "hex": "#12"},
        ]
    )
    assert isinstance(result, Err)
    assert result.error.startswith('colors[1].hex "#12" is invalid')
    assert '"Matte Black"' in result.error


def test_missing_and_malformed_fields() -> None:
    missing = color_list_to_document([{"hex": "#111111"}])
    assert isinstance(missing, Err)
    assert missing.error == "colors[0].name is missing"
    bad_category = color_list_to_document([{"name": "A", "hex": "#111", "category": 5}])
    assert isinstance(bad_category, Err)
    assert bad_category.error.startswith("colors[0].category 5 is invalid")
    not_object = color_list_to_document(["red"])
    assert isinstance(not_object, Err)
    assert not_object.error.startswith('colors[0] "red" is invalid')
    unknown = color_list_to_document([{"name": "A", "hex": "#111", "colour": "x"}])
    assert isinstance(unknown, Err)
    assert unknown.error.startswith('colors[0].colour "x" is invalid')


def test_non_list_is_rejected() -> None:
    result = color_list_to_document({"name": "A"})
    assert isinstance(result, Err)
    assert "expected an array" in result.error


def test_parse_color_list_reports_json_position() -> None:
    result = parse_color_list("[{")
    assert isinstance(result, Err)
    assert result.error.startswith("Invalid JSON at line 1, column")
    ok = parse_color_list('[{"name": "A", "hex": "#111"}]')
    assert isinstance(ok, Ok)
