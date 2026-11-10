import uuid

from material_colors_grid import (
    create_category,
    create_color,
    create_default_document,
    create_sub_category,
)


def test_create_color_generates_uuid_id() -> None:
    color = create_color("Matte Black", "#111111")
    assert color.name == "Matte Black"
    assert color.hex == "#111111"
    assert str(uuid.UUID(color.id)) == color.id


def test_create_color_ids_are_unique() -> None:
    assert create_color("A", "#fff").id != create_color("A", "#fff").id


def test_create_color_accepts_explicit_id() -> None:
    assert create_color("A", "#fff", id="fixed").id == "fixed"


def test_create_category_holds_colors_and_children() -> None:
    color = create_color("Red", "#f00")
    child = create_sub_category("Silk")
    category = create_category("PLA", colors=[color], sub_categories=[child])
    assert category.colors == (color,)
    assert category.sub_categories == (child,)
    assert str(uuid.UUID(category.id)) == category.id


def test_create_sub_category_matches_category_shape() -> None:
    sub_category = create_sub_category("Silk", id="s1")
    assert (sub_category.id, sub_category.name) == ("s1", "Silk")
    assert sub_category.colors == ()


def test_default_document_has_sole_default_category() -> None:
    document = create_default_document()
    assert [category.name for category in document.categories] == ["Default"]
    assert document.style.width == 1440
    assert document.style.height == 1280
    assert document.categories[0].id == "default"
    assert document.categories[0].sub_categories == ()
