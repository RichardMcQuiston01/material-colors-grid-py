import dataclasses

from material_colors_grid import (
    BandStyle,
    Category,
    Color,
    Layout,
    ProjectDocument,
    Style,
    build_render_model,
    compute_layout,
)
from material_colors_grid.layout import (
    BAND_HEIGHT,
    CARD_GAP,
    CARD_HEIGHT,
    HEADING_HEIGHT,
    MARGIN,
    MIN_CARD_WIDTH,
)


def make_colors(count: int) -> tuple[Color, ...]:
    return tuple(
        Color(
            id=f"c{index}",
            name=f"Color {index:03d}",
            hex=f"#{index:02x}{index:02x}{index:02x}",
        )
        for index in range(count)
    )


def layout_for(categories: tuple[Category, ...], style: Style | None = None) -> Layout:
    resolved: Style = style if style is not None else Style()
    document = ProjectDocument(categories=categories, style=resolved)
    return compute_layout(build_render_model(document), resolved)


def test_cards_wrap_at_cards_per_row() -> None:
    category = Category(id="d", name="Default", colors=make_colors(10))
    layout = layout_for((category,), Style(cards_per_row=4))
    rows = sorted({card.rect.y for card in layout.cards})
    assert len(layout.cards) == 10
    assert len(rows) == 3
    first_row = [card for card in layout.cards if card.rect.y == rows[0]]
    assert len(first_row) == 4
    assert rows[1] - rows[0] == CARD_HEIGHT + CARD_GAP


def test_cards_fit_within_canvas_without_overlap() -> None:
    category = Category(id="d", name="Default", colors=make_colors(8))
    layout = layout_for((category,))
    for card in layout.cards:
        assert card.rect.x >= MARGIN
        assert card.rect.x + card.rect.width <= layout.width - MARGIN
    first_row = sorted(
        (card for card in layout.cards if card.rect.y == layout.cards[0].rect.y),
        key=lambda card: card.rect.x,
    )
    for left, right in zip(first_row, first_row[1:], strict=False):
        assert left.rect.x + left.rect.width + CARD_GAP == right.rect.x


def test_default_canvas_size_when_content_is_small() -> None:
    category = Category(id="d", name="Default", colors=make_colors(2))
    layout = layout_for((category,))
    assert (layout.width, layout.height) == (1440, 1280)


def test_canvas_grows_vertically_when_content_clipped() -> None:
    category = Category(id="d", name="Default", colors=make_colors(60))
    layout = layout_for((category,))
    bottom = max(card.rect.y + card.rect.height for card in layout.cards)
    assert layout.height > 1280
    assert layout.height == bottom + MARGIN


def test_canvas_grows_horizontally_when_cards_too_narrow() -> None:
    category = Category(id="d", name="Default", colors=make_colors(3))
    layout = layout_for((category,), Style(width=200, cards_per_row=3))
    assert layout.width == 2 * MARGIN + 3 * MIN_CARD_WIDTH + 2 * CARD_GAP
    assert all(card.rect.width == MIN_CARD_WIDTH for card in layout.cards)


def test_empty_bands_are_omitted() -> None:
    layout = layout_for((Category(id="d", name="Default", colors=make_colors(1)),))
    assert layout.header is None
    assert layout.footer is None
    first_card = layout.cards[0]
    assert first_card.rect.y == MARGIN


def test_bands_included_when_text_present() -> None:
    style = Style(header=BandStyle(text="Top"), footer=BandStyle(text="Bottom"))
    layout = layout_for(
        (Category(id="d", name="Default", colors=make_colors(1)),), style
    )
    assert layout.header is not None
    assert layout.header.rect == dataclasses.replace(
        layout.header.rect, x=0, y=0, width=layout.width, height=BAND_HEIGHT
    )
    assert layout.footer is not None
    assert layout.footer.rect.y + layout.footer.rect.height == layout.height
    assert layout.cards[0].rect.y == BAND_HEIGHT + MARGIN


def test_footer_pushes_canvas_height_when_content_is_tall() -> None:
    style = Style(footer=BandStyle(text="Bottom"))
    category = Category(id="d", name="Default", colors=make_colors(60))
    layout = layout_for((category,), style)
    bottom = max(card.rect.y + card.rect.height for card in layout.cards)
    assert layout.footer is not None
    assert layout.footer.rect.y >= bottom + MARGIN


def test_default_category_prints_no_heading() -> None:
    layout = layout_for((Category(id="d", name="Default", colors=make_colors(1)),))
    assert layout.headings == ()


def test_named_categories_get_headings_in_order() -> None:
    layout = layout_for(
        (
            Category(id="b", name="B", colors=make_colors(1)),
            Category(
                id="a",
                name="A",
                colors=make_colors(1),
                sub_categories=(Category(id="s", name="Sub", colors=make_colors(1)),),
            ),
        )
    )
    assert [heading.text for heading in layout.headings] == ["A", "Sub", "B"]
    assert all(heading.rect.height == HEADING_HEIGHT for heading in layout.headings)
    ys = [heading.rect.y for heading in layout.headings]
    assert ys == sorted(ys)
    sub = layout.headings[1]
    assert sub.rect.x > layout.headings[0].rect.x


def test_zero_cards_per_row_acts_as_one() -> None:
    category = Category(id="d", name="Default", colors=make_colors(3))
    layout = layout_for((category,), Style(cards_per_row=0))
    assert len({card.rect.y for card in layout.cards}) == 3


def test_layout_is_deterministic_and_frozen() -> None:
    category = Category(id="d", name="PLA", colors=make_colors(5))
    assert layout_for((category,)) == layout_for((category,))
    layout = layout_for((category,))
    try:
        layout.width = 1  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("Layout should be frozen")
