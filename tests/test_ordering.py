import dataclasses

import pytest

from material_colors_grid import (
    Category,
    Color,
    ProjectDocument,
    RenderModel,
    build_render_model,
)


def make_document(*categories: Category) -> ProjectDocument:
    return ProjectDocument(categories=tuple(categories))


def test_colors_sorted_dark_to_light() -> None:
    category = Category(
        id="c",
        name="PLA",
        colors=(
            Color("w", "White", "#ffffff"),
            Color("k", "Black", "#000000"),
            Color("g", "Gray", "#888888"),
        ),
    )
    model = build_render_model(make_document(category))
    assert [color.name for color in model.categories[0].colors] == [
        "Black",
        "Gray",
        "White",
    ]


def test_luminance_ties_broken_by_name_then_id() -> None:
    category = Category(
        id="c",
        name="PLA",
        colors=(
            Color("2", "Same", "#444444"),
            Color("1", "Same", "#444"),
            Color("3", "Alpha", "#444444"),
        ),
    )
    model = build_render_model(make_document(category))
    assert [color.id for color in model.categories[0].colors] == ["3", "1", "2"]


def test_invalid_hex_sorts_last_without_raising() -> None:
    category = Category(
        id="c",
        name="PLA",
        colors=(
            Color("bad", "Bad", "#12"),
            Color("w", "White", "#ffffff"),
        ),
    )
    colors = build_render_model(make_document(category)).categories[0].colors
    assert [color.id for color in colors] == ["w", "bad"]
    assert colors[1].luminance is None


def test_categories_and_sub_categories_alphabetical() -> None:
    document = make_document(
        Category(id="b", name="beta"),
        Category(
            id="a",
            name="Alpha",
            sub_categories=(
                Category(id="s2", name="Zed"),
                Category(id="s1", name="apple"),
            ),
        ),
    )
    model = build_render_model(document)
    assert [category.name for category in model.categories] == ["Alpha", "beta"]
    subs = model.categories[0].sub_categories
    assert [sub.name for sub in subs] == ["apple", "Zed"]
    assert all(sub.depth == 1 and sub.show_header for sub in subs)


def test_sole_default_category_has_no_header() -> None:
    model = build_render_model(make_document(Category(id="d", name="Default")))
    assert model.categories[0].show_header is False


def test_default_with_other_categories_keeps_header() -> None:
    model = build_render_model(
        make_document(Category(id="d", name="Default"), Category(id="p", name="PLA"))
    )
    assert all(category.show_header for category in model.categories)


def test_non_default_sole_category_shows_header() -> None:
    model = build_render_model(make_document(Category(id="p", name="PLA")))
    assert model.categories[0].show_header is True


def test_empty_document() -> None:
    assert build_render_model(ProjectDocument()) == RenderModel(categories=())


def test_deterministic_regardless_of_input_order() -> None:
    colors = (
        Color("1", "A", "#123456"),
        Color("2", "B", "#654321"),
        Color("3", "C", "#abcdef"),
    )
    forward = Category(id="c", name="X", colors=colors)
    backward = Category(id="c", name="X", colors=tuple(reversed(colors)))
    assert build_render_model(make_document(forward)) == build_render_model(
        make_document(backward)
    )


def test_render_model_is_frozen() -> None:
    model = build_render_model(make_document(Category(id="p", name="PLA")))
    with pytest.raises(dataclasses.FrozenInstanceError):
        model.categories = ()  # type: ignore[misc]
