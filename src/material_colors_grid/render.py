"""Pillow renderer: draws a document to an image and encodes it.

Font choice: text is drawn with Pillow's built-in scalable default font
(``ImageFont.load_default(size=...)``, Aileron, SIL OFL-licensed and shipped
inside Pillow itself). It needs Pillow >= 10.1 built with FreeType, which is
the package's minimum requirement, and it never touches system fonts, so
output only depends on the installed Pillow version.

Invalid swatch colors do not fail a render: the card shows a visible
placeholder (light gray with a red cross) and rendering continues. Invalid
*style* colors (background, card, border, band, font) are a caller error and
return ``Err``. The renderer has no warnings channel; use
``validate_project_document`` to learn about bad colors up front.

The watermark image is supplied by the caller (``watermark_image``); the
renderer never reads ``style.watermark.image_path`` so that rendering does no
file I/O. Position, scale and opacity come from ``style.watermark``. The
watermark is drawn only when an image is passed.
"""

from __future__ import annotations

import io
from functools import cache
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

from material_colors_grid.color import parse_hex, pick_readable_text_color
from material_colors_grid.layout import (
    BandLayout,
    CardLayout,
    HeadingLayout,
    Layout,
    Rect,
    compute_layout,
)
from material_colors_grid.limits import (
    MAX_BAND_TEXT_LENGTH,
    MAX_CANVAS_DIMENSION,
    MAX_CANVAS_PIXELS,
    MAX_CATEGORIES,
    MAX_CATEGORY_DEPTH,
    MAX_COLORS,
)
from material_colors_grid.models import BandStyle, Category, ProjectDocument, Style
from material_colors_grid.ordering import RenderModel, build_render_model
from material_colors_grid.result import Err, Ok, Result

ImageFormat = Literal["png", "jpg", "gif"]
RGB = tuple[int, int, int]

HEADING_FONT_SIZE: int = 32
BAND_FONT_SIZE: int = 44
CARD_FONT_SIZE: int = 28
MIN_CARD_FONT_SIZE: int = 14
CARD_PADDING: int = 8
WATERMARK_MARGIN: int = 20
PLACEHOLDER_FILL: RGB = (221, 221, 221)
PLACEHOLDER_CROSS: RGB = (200, 40, 40)
PLACEHOLDER_TEXT: RGB = (0, 0, 0)
_ELLIPSIS: str = "..."
# Text is cut to this many characters before it is measured, so unvalidated
# models cannot make measuring expensive. Validated names are shorter.
_MAX_RENDERED_TEXT_LENGTH: int = MAX_BAND_TEXT_LENGTH
_SUFFIX_FORMATS: dict[str, ImageFormat] = {
    ".png": "png",
    ".jpg": "jpg",
    ".jpeg": "jpg",
    ".gif": "gif",
}


@cache
def _font(size: int) -> ImageFont.FreeTypeFont:
    """Return Pillow's built-in scalable font at ``size`` pixels (cached)."""
    font = ImageFont.load_default(size=size)
    if not isinstance(font, ImageFont.FreeTypeFont):  # pragma: no cover
        raise RuntimeError("Pillow was built without FreeType; need Pillow >= 10.1")
    return font


def _style_color(label: str, hex_color: str) -> Result[RGB]:
    """Parse a style color, prefixing the error with the field it came from."""
    parsed: Result[RGB] = parse_hex(hex_color)
    if isinstance(parsed, Err):
        return Err(f"Style {label}: {parsed.error}")
    return parsed


def _fit_text(text: str, max_width: int, start_size: int) -> tuple[str, int]:
    """Shrink, then ellipsize, ``text`` so it fits in ``max_width`` pixels.

    Text longer than ``_MAX_RENDERED_TEXT_LENGTH`` is cut first. The truncation
    point is found by binary search, so only O(log n) measurements are made.
    Returns ``""`` when not even the ellipsis fits.
    """
    if len(text) > _MAX_RENDERED_TEXT_LENGTH:
        text = text[: _MAX_RENDERED_TEXT_LENGTH - len(_ELLIPSIS)] + _ELLIPSIS
    size: int = start_size
    while size > MIN_CARD_FONT_SIZE and _font(size).getlength(text) > max_width:
        size -= 2
    font: ImageFont.FreeTypeFont = _font(size)
    if font.getlength(text) <= max_width:
        return text, size
    # Largest ``kept`` such that text[:kept] plus the ellipsis fits.
    low: int = 0
    high: int = len(text) - 1
    best: int = -1
    while low <= high:
        middle: int = (low + high) // 2
        if font.getlength(text[:middle].rstrip() + _ELLIPSIS) <= max_width:
            best = middle
            low = middle + 1
        else:
            high = middle - 1
    if best < 0:
        return "", size
    return text[:best].rstrip() + _ELLIPSIS, size


def _draw_band(
    draw: ImageDraw.ImageDraw, band: BandLayout, style: BandStyle, label: str
) -> Result[None]:
    """Fill a header/footer band and center its text."""
    background: Result[RGB] = _style_color(
        f"{label}.background_color", style.background_color
    )
    if isinstance(background, Err):
        return background
    font_color: Result[RGB] = _style_color(f"{label}.font_color", style.font_color)
    if isinstance(font_color, Err):
        return font_color
    rect: Rect = band.rect
    draw.rectangle(
        (rect.x, rect.y, rect.x + rect.width - 1, rect.y + rect.height - 1),
        fill=background.value,
    )
    text, size = _fit_text(band.text, rect.width - 80, BAND_FONT_SIZE)
    draw.text(
        (rect.x + rect.width // 2, rect.y + rect.height // 2),
        text,
        font=_font(size),
        fill=font_color.value,
        anchor="mm",
    )
    return Ok(None)


def _draw_heading(draw: ImageDraw.ImageDraw, heading: HeadingLayout, fill: RGB) -> None:
    """Draw a category heading left-aligned and vertically centered."""
    rect: Rect = heading.rect
    text, size = _fit_text(heading.text, rect.width, HEADING_FONT_SIZE)
    draw.text(
        (rect.x, rect.y + rect.height // 2),
        text,
        font=_font(size),
        fill=fill,
        anchor="lm",
    )


def _draw_placeholder(
    draw: ImageDraw.ImageDraw, swatch: tuple[int, int, int, int], radius: int
) -> None:
    """Draw the visible stand-in for a swatch whose hex is invalid."""
    left, top, right, bottom = swatch
    draw.rounded_rectangle(swatch, radius=radius, fill=PLACEHOLDER_FILL)
    draw.line((left, top, right, bottom), fill=PLACEHOLDER_CROSS, width=3)
    draw.line((left, bottom, right, top), fill=PLACEHOLDER_CROSS, width=3)


def _draw_card(
    draw: ImageDraw.ImageDraw, card: CardLayout, style: Style
) -> Result[None]:
    """Draw one card: frame, swatch, and the color name over the swatch."""
    card_background: Result[RGB] = _style_color(
        "card_background_color", style.card_background_color
    )
    if isinstance(card_background, Err):
        return card_background
    border: Result[RGB] = _style_color("card_border_color", style.card_border_color)
    if isinstance(border, Err):
        return border
    rect: Rect = card.rect
    half_card: int = min(rect.width, rect.height) // 2
    # Keep the swatch inset non-inverted for absurd thickness or radius.
    thickness: int = min(
        max(0, style.card_border_thickness), max(0, half_card - CARD_PADDING - 1)
    )
    radius: int = min(max(0, style.card_corner_radius), half_card)
    left: int = rect.x
    top: int = rect.y
    right: int = rect.x + rect.width - 1
    bottom: int = rect.y + rect.height - 1
    draw.rounded_rectangle(
        (left, top, right, bottom),
        radius=radius,
        fill=card_background.value,
        outline=border.value if thickness > 0 else None,
        width=thickness,
    )
    inset: int = thickness + CARD_PADDING
    swatch: tuple[int, int, int, int] = (
        left + inset,
        top + inset,
        right - inset,
        bottom - inset,
    )
    swatch_radius: int = max(0, radius - inset)
    parsed: Result[RGB] = parse_hex(card.color.hex)
    text_fill: RGB
    if isinstance(parsed, Err):
        _draw_placeholder(draw, swatch, swatch_radius)
        text_fill = PLACEHOLDER_TEXT
    else:
        draw.rounded_rectangle(swatch, radius=swatch_radius, fill=parsed.value)
        font_hex: str = style.card_font_color
        if font_hex == "auto":
            font_hex = pick_readable_text_color(card.color.hex)
        font_color: Result[RGB] = _style_color("card_font_color", font_hex)
        if isinstance(font_color, Err):
            return font_color
        text_fill = font_color.value
    swatch_width: int = swatch[2] - swatch[0]
    text, size = _fit_text(card.color.name, swatch_width - 16, CARD_FONT_SIZE)
    text_y: int = swatch[3] - size
    center_x: int = swatch[0] + swatch_width // 2
    if isinstance(parsed, Err):
        # Keep the name legible on top of the red cross.
        draw.rectangle(
            (
                swatch[0] + 8,
                text_y - size // 2 - 2,
                swatch[2] - 8,
                text_y + size // 2 + 2,
            ),
            fill=PLACEHOLDER_FILL,
        )
    draw.text((center_x, text_y), text, font=_font(size), fill=text_fill, anchor="mm")
    return Ok(None)


def _apply_watermark(
    canvas: Image.Image, watermark: Image.Image, style: Style
) -> Result[None]:
    """Composite ``watermark`` onto ``canvas`` per ``style.watermark``."""
    settings = style.watermark
    if not 0.0 < settings.scale <= 1.0:
        return Err(f"Watermark scale {settings.scale!r} must be > 0 and <= 1")
    if not 0.0 <= settings.opacity <= 1.0:
        return Err(f"Watermark opacity {settings.opacity!r} must be between 0 and 1")
    overlay: Image.Image = watermark.convert("RGBA")
    target_width: int = max(1, round(canvas.width * settings.scale))
    target_height: int = max(1, round(overlay.height * target_width / overlay.width))
    if target_width > canvas.width or target_height > canvas.height:
        # Shrink to fit inside the canvas, keeping the aspect ratio. The sizes
        # are computed first so a very tall or wide source never allocates a
        # giant intermediate image.
        fit: float = min(canvas.width / target_width, canvas.height / target_height)
        target_width = min(canvas.width, max(1, int(target_width * fit)))
        target_height = min(canvas.height, max(1, int(target_height * fit)))
    overlay = overlay.resize((target_width, target_height), Image.Resampling.LANCZOS)
    alpha: Image.Image = overlay.getchannel("A").point(
        lambda value: round(value * settings.opacity)
    )
    overlay.putalpha(alpha)
    x_left: int = WATERMARK_MARGIN
    x_right: int = canvas.width - target_width - WATERMARK_MARGIN
    y_top: int = WATERMARK_MARGIN
    y_bottom: int = canvas.height - target_height - WATERMARK_MARGIN
    positions: dict[str, tuple[int, int]] = {
        "top-left": (x_left, y_top),
        "top-right": (x_right, y_top),
        "bottom-left": (x_left, y_bottom),
        "bottom-right": (x_right, y_bottom),
        "center": (
            (canvas.width - target_width) // 2,
            (canvas.height - target_height) // 2,
        ),
    }
    position: tuple[int, int] | None = positions.get(settings.position)
    if position is None:
        return Err(
            f'Watermark position "{settings.position}" must be one of '
            + ", ".join(sorted(positions))
        )
    canvas.alpha_composite(overlay, dest=(max(0, position[0]), max(0, position[1])))
    return Ok(None)


def _check_document_size(document: ProjectDocument) -> str | None:
    """Return an error when the model is too big or too deep to render safely.

    Iterative, so a hostile model cannot hit the recursion limit.
    """
    colors: int = 0
    categories: int = 0
    pending: list[tuple[Category, int]] = [
        (category, 1) for category in document.categories
    ]
    while pending:
        category, depth = pending.pop()
        categories += 1
        colors += len(category.colors)
        if depth > MAX_CATEGORY_DEPTH:
            return (
                f"Category nesting deeper than {MAX_CATEGORY_DEPTH} levels "
                f'at category "{category.name[:40]}"'
            )
        if categories > MAX_CATEGORIES:
            return (
                f"Document has more than {MAX_CATEGORIES} categories and "
                "sub-categories (the maximum)"
            )
        if colors > MAX_COLORS:
            return f"Document has more than {MAX_COLORS} colors (the maximum)"
        pending.extend((child, depth + 1) for child in category.sub_categories)
    return None


def _check_layout_size(layout: Layout) -> str | None:
    """Return an error when the computed canvas is larger than the limits."""
    if layout.width > MAX_CANVAS_DIMENSION or layout.height > MAX_CANVAS_DIMENSION:
        return (
            f"Computed canvas {layout.width}x{layout.height} exceeds the maximum "
            f"dimension of {MAX_CANVAS_DIMENSION} pixels"
        )
    pixels: int = layout.width * layout.height
    if pixels > MAX_CANVAS_PIXELS:
        return (
            f"Computed canvas {layout.width}x{layout.height} = {pixels} pixels "
            f"exceeds the maximum of {MAX_CANVAS_PIXELS} pixels"
        )
    return None


def render_to_image(
    document: ProjectDocument, *, watermark_image: Image.Image | None = None
) -> Result[Image.Image]:
    """Render a document to a Pillow image.

    Args:
        document: The document to draw. Its categories are ordered by
            ``build_render_model`` and positioned by ``compute_layout``.
        watermark_image: Optional watermark. Placed per
            ``document.style.watermark`` (position, scale as a fraction of
            canvas width, opacity). ``None`` draws no watermark.

    Returns:
        ``Ok(image)`` with an RGBA image whose size is the computed layout
        size (the canvas grows when content would be clipped), or ``Err``
        naming the style field when a style color, watermark scale, opacity
        or position is invalid, or when the document or the computed canvas
        exceeds the limits in ``material_colors_grid.limits`` (checked before
        any image is allocated). Swatches with an invalid hex are drawn as a
        placeholder and do not cause an error.
    """
    style: Style = document.style
    size_error: str | None = _check_document_size(document)
    if size_error is not None:
        return Err(size_error)
    render_model: RenderModel = build_render_model(document)
    layout: Layout = compute_layout(render_model, style)
    layout_error: str | None = _check_layout_size(layout)
    if layout_error is not None:
        return Err(layout_error)
    background: Result[RGB] = _style_color("background_color", style.background_color)
    if isinstance(background, Err):
        return background
    canvas: Image.Image = Image.new(
        "RGBA", (layout.width, layout.height), (*background.value, 255)
    )
    draw: ImageDraw.ImageDraw = ImageDraw.Draw(canvas)
    heading_hex: str = pick_readable_text_color(style.background_color)
    heading_fill: RGB = (255, 255, 255) if heading_hex == "#ffffff" else (0, 0, 0)
    for heading in layout.headings:
        _draw_heading(draw, heading, heading_fill)
    for card in layout.cards:
        card_result: Result[None] = _draw_card(draw, card, style)
        if isinstance(card_result, Err):
            return card_result
    if layout.header is not None:
        header_result: Result[None] = _draw_band(
            draw, layout.header, style.header, "header"
        )
        if isinstance(header_result, Err):
            return header_result
    if layout.footer is not None:
        footer_result: Result[None] = _draw_band(
            draw, layout.footer, style.footer, "footer"
        )
        if isinstance(footer_result, Err):
            return footer_result
    if watermark_image is not None:
        watermark_result: Result[None] = _apply_watermark(
            canvas, watermark_image, style
        )
        if isinstance(watermark_result, Err):
            return watermark_result
    return Ok(canvas)


def _flatten(image: Image.Image, background_color: str) -> Result[Image.Image]:
    """Flatten any alpha onto ``background_color`` and return an RGB image."""
    background: Result[RGB] = _style_color("background_color", background_color)
    if isinstance(background, Err):
        return background
    rgba: Image.Image = image.convert("RGBA")
    flattened: Image.Image = Image.new("RGBA", rgba.size, (*background.value, 255))
    flattened.alpha_composite(rgba)
    return Ok(flattened.convert("RGB"))


def image_to_bytes(
    image: Image.Image,
    format: ImageFormat,  # noqa: A002 - part of the documented public API
    quality: int = 90,
    *,
    background_color: str = "#ffffff",
) -> Result[bytes]:
    """Encode an image as PNG, JPG, or GIF bytes.

    Args:
        image: The image to encode (any Pillow mode).
        format: ``"png"``, ``"jpg"`` or ``"gif"``.
        quality: JPEG quality, 1-100. Ignored for PNG and GIF.
        background_color: ``#rgb``/``#rrggbb`` color that transparent pixels
            are flattened onto for JPG (no alpha) and GIF. Pass the
            document's ``style.background_color``.

    Returns:
        ``Ok(bytes)``, or ``Err`` naming the format when it is unknown, the
        quality or background color is invalid, or Pillow cannot encode.
    """
    if format not in ("png", "jpg", "gif"):
        return Err(f'Unknown image format "{format}" (expected png, jpg or gif)')
    if not 1 <= quality <= 100:
        return Err(f"JPEG quality {quality} must be between 1 and 100")
    buffer: io.BytesIO = io.BytesIO()
    try:
        if format == "png":
            image.save(buffer, format="PNG")
        else:
            flattened: Result[Image.Image] = _flatten(image, background_color)
            if isinstance(flattened, Err):
                return flattened
            if format == "jpg":
                flattened.value.save(
                    buffer, format="JPEG", quality=quality, optimize=True
                )
            else:
                palette_image: Image.Image = flattened.value.quantize(
                    colors=256,
                    method=Image.Quantize.MEDIANCUT,
                    dither=Image.Dither.NONE,
                )
                palette_image.save(buffer, format="GIF")
    except (OSError, ValueError) as error:
        return Err(f"Could not encode image as {format}: {error}")
    return Ok(buffer.getvalue())


def _infer_format(path: Path) -> Result[ImageFormat]:
    """Infer the image format from a file suffix (``.jpeg`` means jpg)."""
    format_for_suffix: ImageFormat | None = _SUFFIX_FORMATS.get(path.suffix.lower())
    if format_for_suffix is None:
        return Err(
            f'Cannot infer image format from "{path}" (suffix "{path.suffix}"; '
            "expected .png, .jpg, .jpeg or .gif)"
        )
    return Ok(format_for_suffix)


def save_image(
    image: Image.Image,
    path: str | Path,
    format: ImageFormat | None = None,  # noqa: A002 - part of the public API
    *,
    quality: int = 90,
    background_color: str = "#ffffff",
) -> Result[Path]:
    """Write an image to ``path``.

    Args:
        image: The image to save.
        path: Destination file. The parent directory must exist.
        format: ``"png"``, ``"jpg"`` or ``"gif"``; inferred from the suffix
            when ``None`` (``.jpeg`` is jpg).
        quality: JPEG quality, 1-100.
        background_color: Flattening color for JPG/GIF, see ``image_to_bytes``.

    Returns:
        ``Ok(path)``, or ``Err`` naming the path and format when the format
        cannot be determined, encoding fails, or the file cannot be written.
    """
    destination: Path = Path(path)
    resolved_format: ImageFormat
    if format is None:
        inferred: Result[ImageFormat] = _infer_format(destination)
        if isinstance(inferred, Err):
            return inferred
        resolved_format = inferred.value
    else:
        resolved_format = format
    encoded: Result[bytes] = image_to_bytes(
        image, resolved_format, quality, background_color=background_color
    )
    if isinstance(encoded, Err):
        return Err(f'Could not save "{destination}": {encoded.error}')
    try:
        destination.write_bytes(encoded.value)
    except OSError as error:
        return Err(f'Could not write {resolved_format} to "{destination}": {error}')
    return Ok(destination)
