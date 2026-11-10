import dataclasses
import json
from typing import Any

from material_colors_grid import (
    BandStyle,
    Category,
    Color,
    ProjectDocument,
    Style,
    WatermarkStyle,
    create_default_document,
)
from material_colors_grid.schema import document_json_schema

Schema = dict[str, Any]


def _resolve(root: Schema, node: Schema) -> Schema:
    """Follow a local ``$ref`` such as ``#/$defs/style``."""
    if "$ref" not in node:
        return node
    target: Any = root
    for part in node["$ref"].removeprefix("#/").split("/"):
        target = target[part]
    return target  # type: ignore[no-any-return]


def _assert_structure(root: Schema, node: Schema, data: object, path: str) -> None:
    """Minimal structural check: refs, object keys, required, arrays."""
    node = _resolve(root, node)
    if "anyOf" in node:
        return
    expected = node.get("type")
    if isinstance(data, dict):
        assert expected == "object", path
        properties: Schema = node["properties"]
        for key in node.get("required", []):
            assert key in data, f"{path}.{key} required by schema"
        for key, value in data.items():
            assert key in properties, f"{path}.{key} not in schema"
            _assert_structure(root, properties[key], value, f"{path}.{key}")
    elif isinstance(data, list):
        assert expected == "array", path
        for index, item in enumerate(data):
            _assert_structure(root, node["items"], item, f"{path}[{index}]")


def test_schema_top_level_keys() -> None:
    schema = document_json_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert set(schema["properties"]) == {"categories", "style"}
    assert set(schema["$defs"]) == {
        "color",
        "category",
        "band",
        "watermark",
        "style",
    }
    json.dumps(schema)


def test_schema_covers_every_model_field() -> None:
    defs = document_json_schema()["$defs"]
    pairs: list[tuple[str, type]] = [
        ("style", Style),
        ("band", BandStyle),
        ("watermark", WatermarkStyle),
        ("color", Color),
        ("category", Category),
    ]
    for name, model in pairs:
        model_fields = {field.name for field in dataclasses.fields(model)}
        assert set(defs[name]["properties"]) == model_fields, name


def test_schema_defaults_match_model_defaults() -> None:
    defs = document_json_schema()["$defs"]
    defaults = dataclasses.asdict(Style())
    for key, value in defaults.items():
        if key in ("header", "footer", "watermark"):
            continue
        assert defs["style"]["properties"][key]["default"] == value, key
    assert defs["watermark"]["properties"]["scale"]["default"] == 0.15


def test_default_document_matches_schema_structure() -> None:
    schema = document_json_schema()
    data = dataclasses.asdict(create_default_document())
    _assert_structure(schema, schema, data, "document")


def test_hand_built_document_matches_schema_structure() -> None:
    document = ProjectDocument(
        categories=(
            Category(
                id="c1",
                name="PLA",
                colors=(Color(id="k1", name="Matte Black", hex="#111111"),),
                sub_categories=(
                    Category(
                        id="c2",
                        name="Silk",
                        colors=(Color(id="k2", name="Gold", hex="#d4af37"),),
                    ),
                ),
            ),
        ),
        style=Style(header=BandStyle(text="Colors")),
    )
    schema = document_json_schema()
    _assert_structure(schema, schema, dataclasses.asdict(document), "document")


def test_schema_rejects_unknown_key_structurally() -> None:
    schema = document_json_schema()
    try:
        _assert_structure(schema, schema, {"colours": []}, "document")
    except AssertionError as error:
        assert "colours" in str(error)
    else:
        raise AssertionError("unknown key was accepted")


def test_schema_returns_independent_copy() -> None:
    first = document_json_schema()
    first["title"] = "changed"
    assert document_json_schema()["title"] == "ProjectDocument"
