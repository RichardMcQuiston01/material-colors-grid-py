"""Hardening against hostile input: every limit, and each reported attack."""

import json
import time
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from material_colors_grid import (
    BandStyle,
    Category,
    Color,
    Err,
    Ok,
    ProjectDocument,
    Style,
    WatermarkStyle,
    document_to_json,
    parse_imported_document,
    render_to_image,
)
from material_colors_grid import render as render_module
from material_colors_grid.cli import main
from material_colors_grid.colorlist import color_list_to_document, parse_color_list
from material_colors_grid.io import document_from_dict, load_document_file
from material_colors_grid.limits import (
    MAX_BAND_TEXT_LENGTH,
    MAX_CANVAS_DIMENSION,
    MAX_CANVAS_PIXELS,
    MAX_CARDS_PER_ROW,
    MAX_COLORS,
    MAX_JSON_INPUT_BYTES,
    MAX_JSON_NESTING_DEPTH,
    MAX_NAME_LENGTH,
)
from material_colors_grid.validate import check_json_text, validate_project_document


def parse_style(**style: object) -> Err | Ok[ProjectDocument]:
    return parse_imported_document(json.dumps({"style": style}))


def error_of(result: object) -> str:
    assert isinstance(result, Err), result
    return result.error


def category_json(name: str = "A", colors: int = 1) -> dict[str, Any]:
    return {
        "name": name,
        "colors": [{"name": f"c{index}", "hex": "#fff"} for index in range(colors)],
    }


def document_text(categories: list[dict[str, Any]]) -> str:
    return json.dumps({"categories": categories})


def color_list(count: int) -> str:
    return json.dumps([{"name": f"c{i}", "hex": "#fff"} for i in range(count)])


def test_limit_values() -> None:
    assert MAX_CANVAS_DIMENSION == 8192
    assert MAX_CARDS_PER_ROW == 50
    assert MAX_COLORS == 500
    assert MAX_CANVAS_PIXELS == 50_000_000
    assert MAX_NAME_LENGTH == 100
    assert MAX_BAND_TEXT_LENGTH == 200
    assert MAX_JSON_NESTING_DEPTH == 32
    assert MAX_JSON_INPUT_BYTES == 5_000_000


# --- style limits -----------------------------------------------------------


@pytest.mark.parametrize("key", ["width", "height"])
def test_canvas_dimension_boundary(key: str) -> None:
    assert isinstance(parse_style(**{key: MAX_CANVAS_DIMENSION}), Ok)
    message = error_of(parse_style(**{key: MAX_CANVAS_DIMENSION + 1}))
    assert message == f"style.{key} 8193 exceeds the maximum of 8192"


def test_cards_per_row_boundary() -> None:
    assert isinstance(parse_style(cards_per_row=50), Ok)
    message = error_of(parse_style(cards_per_row=51))
    assert message == "style.cards_per_row 51 exceeds the maximum of 50"
    assert error_of(parse_style(cards_per_row=1000000)) == (
        "style.cards_per_row 1000000 exceeds the maximum of 50"
    )


def test_canvas_pixel_boundary() -> None:
    assert isinstance(parse_style(width=8192, height=6103), Ok)
    message = error_of(parse_style(width=8192, height=6104))
    assert "style.width x style.height 8192 x 6104" in message
    assert "exceeds the maximum of 50000000 pixels" in message


def test_huge_integers_are_rejected_with_short_messages() -> None:
    for value in (10**9, 10**400):
        message = error_of(parse_style(width=value))
        assert message.startswith("style.width ")
        assert message.endswith("exceeds the maximum of 8192")
        assert len(message) < 120


def test_integer_over_4300_digits_is_an_error_not_a_crash() -> None:
    text = '{"style": {"width": ' + "9" * 5000 + "}}"
    message = error_of(parse_imported_document(text))
    assert "number that cannot be parsed" in message
    list_text = '[{"name": "A", "hex": "#fff", "category": ' + "9" * 5000 + "}]"
    assert "number that cannot be parsed" in error_of(parse_color_list(list_text))


def test_huge_integer_in_a_python_mapping_does_not_raise() -> None:
    message = error_of(document_from_dict({"style": {"width": 10**5000}}))
    assert "style.width" in message


# --- whole floats -----------------------------------------------------------


@pytest.mark.parametrize("text", ["1440.0", "1e3", "1E3", "1000.00"])
def test_whole_floats_become_ints(text: str) -> None:
    result = parse_imported_document('{"style": {"width": ' + text + "}}")
    assert isinstance(result, Ok)
    assert isinstance(result.value.style.width, int)
    assert result.value.style.width == int(float(text))


def test_whole_float_for_other_integer_fields() -> None:
    result = parse_style(cards_per_row=3.0, card_corner_radius=4.0)
    assert isinstance(result, Ok)
    assert result.value.style.cards_per_row == 3
    assert isinstance(result.value.style.card_corner_radius, int)


@pytest.mark.parametrize("text", ["1440.5", "NaN", "Infinity", "-Infinity", "1e999"])
def test_non_whole_floats_are_rejected(text: str) -> None:
    message = error_of(parse_imported_document('{"style": {"width": ' + text + "}}"))
    assert message.startswith("style.width ")
    assert "expected an integer >= 1" in message


def test_bool_is_still_rejected_for_integers() -> None:
    assert "style.width true" in error_of(parse_style(width=True))


def test_whole_float_over_limit_still_exceeds() -> None:
    assert error_of(parse_style(width=1e300)).endswith("exceeds the maximum of 8192")


# --- counts and lengths -----------------------------------------------------


def test_color_count_boundary_across_categories() -> None:
    at_limit = document_text([category_json("A", 250), category_json("B", 250)])
    assert isinstance(parse_imported_document(at_limit), Ok)
    over = document_text([category_json("A", 250), category_json("B", 251)])
    message = error_of(parse_imported_document(over))
    assert message.startswith("categories[1].colors has 251 entries")
    assert "501 colors" in message
    assert message.endswith("maximum of 500")


def test_20000_colors_rejected() -> None:
    text = document_text([category_json("A", 20000)])
    assert "20000 entries" in error_of(parse_imported_document(text))


def test_category_count_boundary() -> None:
    at_limit = document_text([category_json(f"c{i}", 0) for i in range(500)])
    assert isinstance(parse_imported_document(at_limit), Ok)
    over = document_text([category_json(f"c{i}", 0) for i in range(501)])
    message = error_of(parse_imported_document(over))
    assert message.startswith("categories[500] is category number 501")
    assert "maximum of 500 categories" in message


def test_sub_categories_count_toward_category_limit() -> None:
    parent: dict[str, Any] = category_json("P", 0)
    parent["sub_categories"] = [category_json(f"s{i}", 0) for i in range(500)]
    message = error_of(parse_imported_document(document_text([parent])))
    assert "category number 501" in message


@pytest.mark.parametrize("field", ["color", "category", "sub_category"])
def test_name_length_boundary_in_documents(field: str) -> None:
    def build(length: int) -> str:
        name = "x" * length
        color = {"name": "c", "hex": "#fff"}
        if field == "color":
            color["name"] = name
            category: dict[str, Any] = {"name": "A", "colors": [color]}
        elif field == "category":
            category = {"name": name, "colors": [color]}
        else:
            category = {
                "name": "A",
                "sub_categories": [{"name": name, "colors": [color]}],
            }
        return document_text([category])

    assert isinstance(parse_imported_document(build(100)), Ok)
    message = error_of(parse_imported_document(build(101)))
    assert "(101 characters) exceeds the maximum of 100 characters" in message
    assert len(message) < 250


@pytest.mark.parametrize("band", ["header", "footer"])
def test_band_text_length_boundary(band: str) -> None:
    assert isinstance(parse_style(**{band: {"text": "x" * 200}}), Ok)
    message = error_of(parse_style(**{band: {"text": "x" * 201}}))
    assert message.startswith(f"style.{band}.text ")
    assert "(201 characters) exceeds the maximum of 200 characters" in message


def test_2000_char_name_and_header_text_rejected() -> None:
    long_name = "y" * 2000
    named = document_text([{"name": long_name, "colors": []}])
    assert "categories[0].name" in error_of(parse_imported_document(named))
    assert "style.header.text" in error_of(parse_style(header={"text": long_name}))


# --- color lists ------------------------------------------------------------


def test_color_list_count_boundary() -> None:
    assert isinstance(parse_color_list(color_list(500)), Ok)
    message = error_of(parse_color_list(color_list(501)))
    assert message == "Color list has 501 entries, which exceeds the maximum of 500"
    assert "20000 entries" in error_of(parse_color_list(color_list(20000)))


@pytest.mark.parametrize("field", ["name", "category", "sub_category"])
def test_color_list_name_length_boundary(field: str) -> None:
    def build(length: int) -> str:
        entry = {"name": "c", "hex": "#fff", field: "z" * length}
        return json.dumps([entry])

    assert isinstance(parse_color_list(build(100)), Ok)
    message = error_of(parse_color_list(build(101)))
    assert message.startswith(f"colors[0].{field} ")
    assert "(101 characters) exceeds the maximum of 100 characters" in message


def test_color_list_category_total_limit() -> None:
    entries = [
        {"name": "c", "hex": "#fff", "category": f"cat{i}", "sub_category": "s"}
        for i in range(251)
    ]
    message = error_of(parse_color_list(json.dumps(entries)))
    assert "502 categories and sub-categories" in message


def test_color_list_groups_categories_case_insensitively() -> None:
    entries = [
        {"name": "a", "hex": "#111", "category": "PLA"},
        {"name": "b", "hex": "#222", "category": " pla "},
        {"name": "c", "hex": "#333", "category": "Pla", "sub_category": "Matte"},
        {"name": "d", "hex": "#444", "category": "pla", "sub_category": " matte"},
        {"name": "e", "hex": "#555"},
        {"name": "f", "hex": "#666", "category": "default"},
    ]
    result = parse_color_list(json.dumps(entries))
    assert isinstance(result, Ok)
    categories = result.value.categories
    assert [category.name for category in categories] == ["PLA", "Default"]
    pla, default = categories
    assert [color.name for color in pla.colors] == ["a", "b"]
    assert [sub.name for sub in pla.sub_categories] == ["Matte"]
    assert [color.name for color in pla.sub_categories[0].colors] == ["c", "d"]
    assert [color.name for color in default.colors] == ["e", "f"]


# --- nesting and size -------------------------------------------------------


def nested_sub_categories(levels: int) -> str:
    """A document whose categories nest ``levels`` deep (top level is 1)."""
    inner: dict[str, Any] = {"name": "leaf", "colors": [], "sub_categories": []}
    for _ in range(levels - 1):
        inner = {"name": "n", "colors": [], "sub_categories": [inner]}
    return json.dumps({"categories": [inner]})


def test_json_nesting_depth_boundary_in_text() -> None:
    assert check_json_text("[" * 32 + "]" * 32) is None
    message = check_json_text("[" * 33 + "]" * 33)
    assert message is not None
    assert "nesting deeper than 32 levels" in message


def test_brackets_inside_strings_do_not_count() -> None:
    name = "[" * 500 + '\\"{{{{'
    text = json.dumps({"categories": [{"name": name, "colors": []}]})
    assert check_json_text(text) is None


def test_category_nesting_boundary() -> None:
    accepted = parse_imported_document(nested_sub_categories(15))
    assert isinstance(accepted, Ok)
    assert isinstance(document_to_json(accepted.value), str)
    assert "nesting deeper than 32 levels" in error_of(
        parse_imported_document(nested_sub_categories(16))
    )


@pytest.mark.parametrize("depth", [5000, 100_000])
def test_deeply_nested_documents_are_errors(depth: int) -> None:
    deep_array = "[" * depth + "]" * depth
    assert "nesting deeper than 32" in error_of(parse_imported_document(deep_array))
    assert "nesting deeper than 32" in error_of(parse_color_list(deep_array))
    sub_categories = '{"categories": [{"name": "a", "sub_categories": ['
    sub_categories += '{"name": "a", "sub_categories": [' * depth
    sub_categories += "]}" * depth + "]}]}"
    assert "nesting deeper than 32" in error_of(parse_imported_document(sub_categories))
    deep_value = '{"style": {"width": ' + "[" * depth + "]" * depth + "}}"
    assert isinstance(parse_imported_document(deep_value), Err)


def test_deep_python_structures_are_errors_not_recursion_errors() -> None:
    node: dict[str, Any] = {"name": "a", "colors": [], "sub_categories": []}
    for _ in range(5000):
        node = {"name": "a", "colors": [], "sub_categories": [node]}
    assert isinstance(document_from_dict({"categories": [node]}), Err)
    assert isinstance(
        validate_project_document({"categories": [node], "style": {}}), Err
    )
    deep: list[Any] = []
    for _ in range(5000):
        deep = [deep]
    assert "nested deeper" in error_of(color_list_to_document(deep))


def test_json_input_size_boundary() -> None:
    at_limit = "{}" + " " * (MAX_JSON_INPUT_BYTES - 2)
    assert isinstance(parse_imported_document(at_limit), Ok)
    over = at_limit + " "
    assert "exceeds the maximum of 5000000 bytes" in error_of(
        parse_imported_document(over)
    )
    assert "exceeds the maximum of 5000000 bytes" in error_of(parse_color_list(over))


def test_json_input_size_counts_bytes_not_characters() -> None:
    text = '["' + "é" * 2_600_000 + '"]'
    assert "bytes exceeds the maximum" in error_of(parse_color_list(text))


def test_load_document_file_rejects_oversize_file(tmp_path: Path) -> None:
    path = tmp_path / "big.json"
    path.write_bytes(b" " * (MAX_JSON_INPUT_BYTES + 1))
    assert "file exceeds the maximum of 5000000 bytes" in error_of(
        load_document_file(path)
    )


# --- render-time guards -----------------------------------------------------


def forbid_allocation(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> Image.Image:
        raise AssertionError("Image.new must not be called")

    monkeypatch.setattr(Image, "new", refuse)


def single_color_document(style: Style) -> ProjectDocument:
    return ProjectDocument(
        categories=(Category("c", "Default", (Color("i", "Red", "#f00"),)),),
        style=style,
    )


def test_render_rejects_oversize_pixels_before_allocating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forbid_allocation(monkeypatch)
    message = error_of(
        render_to_image(single_color_document(Style(width=8192, height=8192)))
    )
    assert "Computed canvas 8192x8192 = 67108864 pixels" in message
    assert "maximum of 50000000" in message


@pytest.mark.parametrize("width", [10**9, 10**400])
def test_render_rejects_huge_dimensions_before_allocating(
    monkeypatch: pytest.MonkeyPatch, width: int
) -> None:
    forbid_allocation(monkeypatch)
    message = error_of(render_to_image(single_color_document(Style(width=width))))
    assert "exceeds the maximum dimension of 8192" in message


def test_render_rejects_layout_widened_past_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forbid_allocation(monkeypatch)
    message = error_of(
        render_to_image(single_color_document(Style(cards_per_row=1_000_000)))
    )
    assert "exceeds the maximum dimension of 8192" in message


def test_render_rejects_tall_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    forbid_allocation(monkeypatch)
    colors = tuple(Color(f"i{n}", f"c{n}", "#fff") for n in range(MAX_COLORS))
    document = ProjectDocument(
        categories=(Category("c", "Default", colors),), style=Style(cards_per_row=1)
    )
    assert "exceeds the maximum dimension of 8192" in error_of(
        render_to_image(document)
    )


def test_render_rejects_too_many_colors_directly() -> None:
    colors = tuple(Color(f"i{n}", "c", "#fff") for n in range(MAX_COLORS + 1))
    document = ProjectDocument(categories=(Category("c", "Default", colors),))
    assert "more than 500 colors" in error_of(render_to_image(document))


def test_render_rejects_deep_model_without_recursion_error() -> None:
    category = Category("c", "leaf")
    for _ in range(3000):
        category = Category("c", "n", sub_categories=(category,))
    document = ProjectDocument(categories=(category,))
    assert "nesting deeper than 15 levels" in error_of(render_to_image(document))


def test_render_accepts_the_maximum_cards_per_row() -> None:
    colors = tuple(Color(f"i{n}", f"c{n}", "#abc") for n in range(50))
    document = ProjectDocument(
        categories=(Category("c", "Default", colors),),
        style=Style(cards_per_row=50),
    )
    result = render_to_image(document)
    assert isinstance(result, Ok)
    assert result.value.width <= MAX_CANVAS_DIMENSION


def test_huge_border_and_radius_are_clamped() -> None:
    style = Style(card_border_thickness=10**9, card_corner_radius=10**9)
    started = time.perf_counter()
    result = render_to_image(single_color_document(style))
    assert isinstance(result, Ok)
    assert time.perf_counter() - started < 2


# --- text rendering ---------------------------------------------------------


class CountingFont:
    def __init__(self) -> None:
        self.calls = 0
        self.longest = 0

    def getlength(self, text: str) -> float:
        self.calls += 1
        self.longest = max(self.longest, len(text))
        return 10.0 * len(text)


def test_fit_text_uses_logarithmic_measurements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = CountingFont()
    monkeypatch.setattr(render_module, "_font", lambda size: font)
    text, _ = render_module._fit_text("w" * 100_000, 300, 28)
    assert font.calls <= 40
    assert font.longest <= 200
    assert text == "w" * 27 + "..."


def test_fit_text_result_fits() -> None:
    text, size = render_module._fit_text("Abcdefghij " * 40, 200, 28)
    assert size == 14
    assert text.endswith("...")
    assert render_module._font(14).getlength(text) <= 200


def test_fit_text_keeps_short_text_and_drops_text_that_cannot_fit() -> None:
    assert render_module._fit_text("Red", 400, 28) == ("Red", 28)
    assert render_module._fit_text("Red", 1, 28)[0] == ""


def test_100k_character_name_renders_quickly() -> None:
    document = ProjectDocument(
        categories=(
            Category("c", "N" * 100_000, (Color("i", "W" * 100_000, "#336699"),)),
        ),
        style=Style(
            header=BandStyle(text="H" * 100_000), footer=BandStyle(text="F" * 100_000)
        ),
    )
    started = time.perf_counter()
    result = render_to_image(document)
    elapsed = time.perf_counter() - started
    assert isinstance(result, Ok)
    assert elapsed < 1.0


# --- watermark --------------------------------------------------------------


@pytest.mark.parametrize("size", [(1, 60000), (60000, 1), (3, 100000)])
def test_extreme_aspect_watermark_is_clamped(
    monkeypatch: pytest.MonkeyPatch, size: tuple[int, int]
) -> None:
    requested: list[tuple[int, int]] = []
    original = Image.Image.resize

    def recording_resize(
        self: Image.Image, new_size: tuple[int, int], *args: Any, **kwargs: Any
    ) -> Image.Image:
        requested.append(new_size)
        return original(self, new_size, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "resize", recording_resize)
    style = Style(watermark=WatermarkStyle(scale=1.0, opacity=1.0))
    watermark = Image.new("RGBA", size, (255, 0, 0, 255))
    result = render_to_image(single_color_document(style), watermark_image=watermark)
    assert isinstance(result, Ok)
    canvas = result.value
    assert canvas.size == (1440, 1280)
    assert requested
    for width, height in requested:
        assert 1 <= width <= canvas.width
        assert 1 <= height <= canvas.height


def test_normal_watermark_size_is_unchanged() -> None:
    style = Style(watermark=WatermarkStyle(scale=0.25, opacity=1.0, position="center"))
    watermark = Image.new("RGBA", (100, 50), (0, 0, 255, 255))
    result = render_to_image(single_color_document(style), watermark_image=watermark)
    assert isinstance(result, Ok)
    assert result.value.getpixel((720, 640)) == (0, 0, 255, 255)


# --- CLI --------------------------------------------------------------------


def run_cli_json(
    capsys: pytest.CaptureFixture[str], argv: list[str]
) -> tuple[int, dict[str, object]]:
    code = main([*argv, "--json"])
    captured = capsys.readouterr()
    payload: dict[str, object] = json.loads(captured.out)
    return code, payload


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        ({"style": {"cards_per_row": 1000000}}, "style.cards_per_row 1000000 exceeds"),
        ({"style": {"width": 10**9}}, "style.width 1000000000 exceeds"),
        ({"style": {"width": 10**400}}, "exceeds the maximum of 8192"),
        ({"categories": [category_json("A", 20000)]}, "20000 entries"),
    ],
)
def test_cli_rejects_hostile_documents_with_exit_2(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    document: dict[str, Any],
    expected: str,
) -> None:
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    output = tmp_path / "out.png"
    for command in (["render", "--output", str(output)], ["validate"]):
        code, payload = run_cli_json(capsys, [*command, "--input", str(path)])
        assert code == 2
        assert payload["ok"] is False
        assert expected in str(payload["error"])
    assert not output.exists()


def test_cli_rejects_deep_and_huge_number_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    deep = tmp_path / "deep.json"
    deep.write_text("[" * 5000 + "]" * 5000, encoding="utf-8")
    code, payload = run_cli_json(capsys, ["validate", "--colors", str(deep)])
    assert code == 2
    assert "nesting deeper than 32 levels" in str(payload["error"])
    huge = tmp_path / "huge.json"
    huge.write_text('{"style": {"width": ' + "9" * 5000 + "}}", encoding="utf-8")
    code, payload = run_cli_json(capsys, ["validate", "--input", str(huge)])
    assert code == 2
    assert "cannot be parsed" in str(payload["error"])


def test_cli_color_list_with_too_many_colors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "colors.json"
    path.write_text(color_list(20000), encoding="utf-8")
    code, payload = run_cli_json(
        capsys, ["render", "--colors", str(path), "--output", str(tmp_path / "o.png")]
    )
    assert code == 2
    assert "20000 entries" in str(payload["error"])
