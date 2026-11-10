import io
import os
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from material_colors_grid import (
    BandStyle,
    Category,
    Color,
    Err,
    Ok,
    ProjectDocument,
    Result,
    Style,
    WatermarkPosition,
    WatermarkStyle,
    build_render_model,
    compute_layout,
    image_to_bytes,
    render_to_image,
    save_image,
)
from material_colors_grid.layout import BAND_HEIGHT, Layout

GOLDEN_DIR: Path = Path(__file__).parent / "golden"
RGB = tuple[int, int, int]


def make_document(
    colors: tuple[Color, ...],
    category_name: str = "Default",
    style: Style | None = None,
) -> ProjectDocument:
    return ProjectDocument(
        categories=(Category(id="c1", name=category_name, colors=colors),),
        style=style if style is not None else Style(),
    )


def colors_from(*hexes: str) -> tuple[Color, ...]:
    return tuple(
        Color(id=f"id{i}", name=f"Color {i}", hex=h) for i, h in enumerate(hexes)
    )


def render(
    document: ProjectDocument, watermark: Image.Image | None = None
) -> Image.Image:
    result: Result[Image.Image] = render_to_image(document, watermark_image=watermark)
    assert isinstance(result, Ok), result
    return result.value


def layout_of(document: ProjectDocument) -> Layout:
    return compute_layout(build_render_model(document), document.style)


def pixel(image: Image.Image, x: int, y: int) -> RGB:
    value = image.convert("RGB").getpixel((x, y))
    assert isinstance(value, tuple)
    return (value[0], value[1], value[2])


def color_set(image: Image.Image) -> set[RGB]:
    colors = image.convert("RGB").getcolors(maxcolors=1_000_000)
    assert colors is not None
    result: set[RGB] = set()
    for _, color in colors:
        assert isinstance(color, tuple)
        result.add((color[0], color[1], color[2]))
    return result


def swatch_sample(image: Image.Image, document: ProjectDocument, index: int) -> RGB:
    rect = layout_of(document).cards[index].rect
    return pixel(image, rect.x + rect.width // 2, rect.y + 30)


def test_size_mode_and_background() -> None:
    image = render(make_document(colors_from("#ff0000")))
    assert image.size == (1440, 1280)
    assert image.mode == "RGBA"
    assert pixel(image, 2, 2) == (255, 255, 255)


def test_canvas_grows_when_content_would_clip() -> None:
    document = make_document(colors_from(*["#123456"] * 40))
    image = render(document)
    assert image.height > 1280
    assert image.size == (layout_of(document).width, layout_of(document).height)


def test_swatch_pixel_matches_color() -> None:
    document = make_document(colors_from("#ff0000", "#00ff00"))
    image = render(document)
    # Dark to light: red (luminance 0.21) precedes green (0.72).
    assert swatch_sample(image, document, 0) == (255, 0, 0)
    assert swatch_sample(image, document, 1) == (0, 255, 0)


def test_custom_background_and_card_border() -> None:
    style = Style(
        background_color="#102030",
        card_border_color="#ff00ff",
        card_border_thickness=3,
        card_corner_radius=0,
    )
    document = make_document(colors_from("#ffffff"), style=style)
    image = render(document)
    rect = layout_of(document).cards[0].rect
    assert pixel(image, 2, 2) == (16, 32, 48)
    assert pixel(image, rect.x + 1, rect.y + rect.height // 2) == (255, 0, 255)


def test_card_background_visible_as_padding() -> None:
    style = Style(
        card_background_color="#00ff00", card_border_thickness=0, card_corner_radius=0
    )
    document = make_document(colors_from("#000000"), style=style)
    rect = layout_of(document).cards[0].rect
    assert pixel(render(document), rect.x + 2, rect.y + 2) == (0, 255, 0)


def test_header_and_footer_bands_only_with_text() -> None:
    plain = render(make_document(colors_from("#ff0000")))
    assert pixel(plain, 10, 10) == (255, 255, 255)
    style = Style(
        header=BandStyle(text="Top", background_color="#112233"),
        footer=BandStyle(text="Bottom", background_color="#445566"),
    )
    document = make_document(colors_from("#ff0000"), style=style)
    image = render(document)
    assert pixel(image, 5, 5) == (17, 34, 51)
    assert pixel(image, 5, image.height - 5) == (68, 85, 102)
    assert pixel(image, 5, BAND_HEIGHT + 2) == (255, 255, 255)


def test_only_header_means_no_footer_band() -> None:
    style = Style(header=BandStyle(text="Top", background_color="#112233"))
    image = render(make_document(colors_from("#ff0000"), style=style))
    assert pixel(image, 5, image.height - 5) == (255, 255, 255)


def test_default_category_header_suppressed() -> None:
    default_document = make_document(colors_from("#ff0000"))
    named_document = make_document(colors_from("#ff0000"), category_name="PLA")
    assert layout_of(default_document).headings == ()
    named_image = render(named_document)
    default_image = render(default_document)
    heading_rect = layout_of(named_document).headings[0].rect
    box = (
        heading_rect.x,
        heading_rect.y,
        heading_rect.x + heading_rect.width,
        heading_rect.y + heading_rect.height,
    )
    assert named_image.crop(box).getextrema() != ((255, 255),) * 4
    assert ImageChops.invert(named_image.convert("RGB").crop(box)).getbbox() is not None
    assert (
        ImageChops.invert(default_image.convert("RGB").crop((0, 0, 1440, 38))).getbbox()
        is None
    )


def test_cards_wrap_at_cards_per_row() -> None:
    style = Style(cards_per_row=2)
    document = make_document(colors_from("#111111", "#222222", "#333333"), style=style)
    image = render(document)
    cards = layout_of(document).cards
    assert cards[2].rect.y > cards[0].rect.y
    assert cards[2].rect.x == cards[0].rect.x
    assert swatch_sample(image, document, 2) == (51, 51, 51)


def test_auto_font_color_is_readable() -> None:
    def text_pixels(hex_color: str) -> set[RGB]:
        document = make_document(colors_from(hex_color))
        image = render(document).convert("RGB")
        rect = layout_of(document).cards[0].rect
        crop = image.crop(
            (
                rect.x + 20,
                rect.y + rect.height - 60,
                rect.x + rect.width - 20,
                rect.y + rect.height - 20,
            )
        )
        return color_set(crop)

    assert (255, 255, 255) in text_pixels("#000000")
    assert (0, 0, 0) in text_pixels("#ffffff")


def test_explicit_font_color_is_used() -> None:
    style = Style(card_font_color="#ff0000")
    document = make_document(colors_from("#ffffff"), style=style)
    rect = layout_of(document).cards[0].rect
    crop = (
        render(document)
        .convert("RGB")
        .crop(
            (
                rect.x,
                rect.y + rect.height - 60,
                rect.x + rect.width,
                rect.y + rect.height,
            )
        )
    )
    assert (255, 0, 0) in color_set(crop)


def test_invalid_hex_renders_placeholder_and_continues() -> None:
    document = make_document(colors_from("#12", "#00ff00"))
    result = render_to_image(document)
    assert isinstance(result, Ok)
    image = result.value
    cards = layout_of(document).cards
    valid_index = next(i for i, c in enumerate(cards) if c.color.hex == "#00ff00")
    invalid_index = 1 - valid_index
    assert swatch_sample(image, document, valid_index) == (0, 255, 0)
    rect = cards[invalid_index].rect
    assert pixel(image, rect.x + 14, rect.y + 40) == (221, 221, 221)
    inner = image.convert("RGB").crop(
        (rect.x, rect.y, rect.x + rect.width, rect.y + rect.height)
    )
    assert (200, 40, 40) in color_set(inner)


def test_invalid_style_color_is_err_naming_field() -> None:
    result = render_to_image(
        make_document(colors_from("#fff"), style=Style(background_color="red"))
    )
    assert isinstance(result, Err)
    assert "background_color" in result.error and "red" in result.error
    header = Style(header=BandStyle(text="x", font_color="nope"))
    result = render_to_image(make_document((), style=header))
    assert isinstance(result, Err)
    assert "header.font_color" in result.error


def test_empty_document_renders_blank_canvas() -> None:
    image = render(ProjectDocument())
    assert image.size == (1440, 1280)


def _watermark(color: RGB = (255, 0, 0)) -> Image.Image:
    return Image.new("RGBA", (50, 50), (*color, 255))


def test_watermark_bottom_right_and_scale() -> None:
    style = Style(
        watermark=WatermarkStyle(position="bottom-right", scale=0.1, opacity=1.0)
    )
    document = make_document((), style=style)
    image = render(document, _watermark())
    assert pixel(image, 1440 - 20 - 10, 1280 - 20 - 10) == (255, 0, 0)
    assert pixel(image, 1440 - 20 - 144 - 5, 1280 - 20 - 10) == (255, 255, 255)
    assert pixel(image, 20 + 10, 20 + 10) == (255, 255, 255)


def test_watermark_other_positions() -> None:
    points: dict[WatermarkPosition, tuple[int, int]] = {
        "top-left": (30, 30),
        "top-right": (1440 - 30, 30),
        "bottom-left": (30, 1280 - 30),
        "center": (720, 640),
    }
    for position, point in points.items():
        style = Style(
            watermark=WatermarkStyle(
                position=position,
                scale=0.1,
                opacity=1.0,
            )
        )
        image = render(make_document((), style=style), _watermark())
        assert pixel(image, *point) == (255, 0, 0), position


def test_watermark_opacity_blends() -> None:
    style = Style(watermark=WatermarkStyle(position="center", scale=0.1, opacity=0.5))
    image = render(make_document((), style=style), _watermark((0, 0, 0)))
    red, green, blue = pixel(image, 720, 640)
    assert 120 <= red <= 135 and red == green == blue


def test_no_watermark_when_image_not_given() -> None:
    style = Style(watermark=WatermarkStyle(position="center", scale=0.1, opacity=1.0))
    assert pixel(render(make_document((), style=style)), 720, 640) == (255, 255, 255)


def test_watermark_invalid_settings_are_err() -> None:
    for watermark in (
        WatermarkStyle(scale=0.0),
        WatermarkStyle(opacity=1.5),
        WatermarkStyle(position="middle"),  # type: ignore[arg-type]
    ):
        result = render_to_image(
            make_document((), style=Style(watermark=watermark)),
            watermark_image=_watermark(),
        )
        assert isinstance(result, Err)
        assert "Watermark" in result.error


# --- encoding -------------------------------------------------------------


def encode(image: Image.Image, fmt: str, **kwargs: object) -> bytes:
    result = image_to_bytes(image, fmt, **kwargs)  # type: ignore[arg-type]
    assert isinstance(result, Ok), result
    return result.value


def test_png_jpg_gif_round_trip() -> None:
    image = render(make_document(colors_from("#336699", "#cc9933")))
    for fmt, pillow_format in (("png", "PNG"), ("jpg", "JPEG"), ("gif", "GIF")):
        reopened = Image.open(io.BytesIO(encode(image, fmt)))
        assert reopened.format == pillow_format
        assert reopened.size == image.size


def test_png_is_lossless() -> None:
    image = render(make_document(colors_from("#336699")))
    reopened = Image.open(io.BytesIO(encode(image, "png")))
    assert ImageChops.difference(reopened.convert("RGBA"), image).getbbox() is None


def test_jpg_has_no_alpha_and_flattens_on_background() -> None:
    transparent = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    reopened = Image.open(
        io.BytesIO(encode(transparent, "jpg", background_color="#ff0000"))
    )
    assert reopened.mode == "RGB"
    red, green, blue = pixel(reopened, 16, 16)
    assert red > 245 and green < 10 and blue < 10


def test_jpg_default_flatten_is_white_and_quality_matters() -> None:
    image = render(make_document(colors_from("#336699", "#cc9933")))
    low = encode(image, "jpg", quality=10)
    high = encode(image, "jpg", quality=95)
    assert len(low) < len(high)
    transparent = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    assert Image.open(io.BytesIO(encode(transparent, "jpg"))).getpixel((4, 4)) == (
        255,
        255,
        255,
    )


def test_gif_is_palette_with_flat_swatches() -> None:
    document = make_document(colors_from("#336699", "#cc9933", "#99cc33"))
    image = render(document)
    reopened = Image.open(io.BytesIO(encode(image, "gif")))
    assert reopened.mode == "P"
    converted = reopened.convert("RGB")
    for index, expected in enumerate(((51, 102, 153), (204, 153, 51), (153, 204, 51))):
        rect = layout_of(document).cards[index].rect
        sample = converted.getpixel((rect.x + rect.width // 2, rect.y + 30))
        assert sample is not None
        assert all(abs(a - b) <= 2 for a, b in zip(sample, expected, strict=False))  # type: ignore[arg-type]
        # No banding: the whole top strip of the swatch is one flat color.
        strip = converted.crop(
            (rect.x + 20, rect.y + 12, rect.x + rect.width - 20, rect.y + 60)
        )
        assert len(strip.getcolors() or []) == 1


def test_image_to_bytes_errors() -> None:
    image = Image.new("RGB", (4, 4))
    unknown = image_to_bytes(image, "webp")  # type: ignore[arg-type]
    assert isinstance(unknown, Err) and "webp" in unknown.error
    bad_quality = image_to_bytes(image, "jpg", 0)
    assert isinstance(bad_quality, Err) and "quality" in bad_quality.error
    bad_background = image_to_bytes(image, "jpg", background_color="blue")
    assert isinstance(bad_background, Err) and "blue" in bad_background.error


# --- save_image ------------------------------------------------------------


def test_save_image_infers_format_from_suffix(tmp_path: Path) -> None:
    image = render(make_document(colors_from("#336699")))
    expected = {"a.png": "PNG", "b.jpg": "JPEG", "c.JPEG": "JPEG", "d.gif": "GIF"}
    for name, pillow_format in expected.items():
        result = save_image(image, tmp_path / name)
        assert result == Ok(tmp_path / name)
        with Image.open(tmp_path / name) as reopened:
            assert reopened.format == pillow_format
            assert reopened.size == image.size


def test_save_image_explicit_format_overrides_suffix(tmp_path: Path) -> None:
    image = Image.new("RGB", (8, 8), "red")
    result = save_image(image, str(tmp_path / "x.dat"), "png")
    assert isinstance(result, Ok)
    with Image.open(tmp_path / "x.dat") as reopened:
        assert reopened.format == "PNG"


def test_save_image_unknown_suffix_is_err(tmp_path: Path) -> None:
    result = save_image(Image.new("RGB", (8, 8)), tmp_path / "x.bmp")
    assert isinstance(result, Err)
    assert "x.bmp" in result.error and ".bmp" in result.error


def test_save_image_unwritable_path_is_err(tmp_path: Path) -> None:
    target = tmp_path / "missing_dir" / "out.png"
    result = save_image(Image.new("RGB", (8, 8)), target)
    assert isinstance(result, Err)
    assert str(target) in result.error and "png" in result.error


# --- golden images ---------------------------------------------------------


def golden_document() -> ProjectDocument:
    return ProjectDocument(
        categories=(
            Category(
                id="pla",
                name="PLA",
                colors=(
                    Color("1", "Matte Black", "#111111"),
                    Color("2", "Signal Red", "#d62828"),
                    Color("3", "Sky", "#87ceeb"),
                ),
                sub_categories=(
                    Category("s", "Silk", colors=(Color("4", "Gold", "#ffd700"),)),
                ),
            ),
        ),
        style=Style(
            width=600,
            height=700,
            cards_per_row=2,
            header=BandStyle(
                text="Filament Colors", background_color="#223344", font_color="#ffffff"
            ),
        ),
    )


def assert_matches_golden(image: Image.Image, name: str) -> None:
    golden_path = GOLDEN_DIR / name
    if os.environ.get("UPDATE_GOLDEN") == "1" or not golden_path.exists():
        GOLDEN_DIR.mkdir(exist_ok=True)
        image.convert("RGB").save(golden_path)
    with Image.open(golden_path) as golden:
        expected = golden.convert("RGB")
    actual = image.convert("RGB")
    assert actual.size == expected.size
    difference = ImageChops.difference(actual, expected)
    mean_difference = sum(ImageStat.Stat(difference).mean) / 3
    assert mean_difference < 1.0, (
        f"{name} differs (mean abs diff {mean_difference:.3f})"
    )


def test_golden_png() -> None:
    assert_matches_golden(render(golden_document()), "grid.png")


def test_golden_gif_round_trip_close_to_png() -> None:
    image = render(golden_document())
    gif = Image.open(io.BytesIO(encode(image, "gif"))).convert("RGB")
    difference = ImageChops.difference(gif, image.convert("RGB"))
    assert sum(ImageStat.Stat(difference).mean) / 3 < 2.0
