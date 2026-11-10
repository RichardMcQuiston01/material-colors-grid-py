"""Pure color math: hex parsing, WCAG luminance and contrast.

No Pillow and no I/O. Follows WCAG 2.x definitions for sRGB relative
luminance and contrast ratio.
"""

from __future__ import annotations

import re

from material_colors_grid.result import Err, Ok, Result

_HEX_PATTERN: re.Pattern[str] = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
_BLACK: str = "#000000"
_WHITE: str = "#ffffff"


def parse_hex(hex_color: str) -> Result[tuple[int, int, int]]:
    """Parse a ``#rgb`` or ``#rrggbb`` string into 0-255 channel values.

    Args:
        hex_color: Color string with a leading ``#`` and 3 or 6 hex digits.

    Returns:
        ``Ok((red, green, blue))``, or ``Err`` naming the offending value
        when it is not a string, lacks ``#``, or has the wrong digit count.
    """
    if not isinstance(hex_color, str):
        return Err(
            f"Hex color {hex_color!r} must be a string, got {type(hex_color).__name__}"
        )
    if _HEX_PATTERN.fullmatch(hex_color) is None:
        return Err(
            f'Invalid hex color "{hex_color}" '
            "(expected # followed by 3 or 6 hex digits)"
        )
    digits: str = hex_color[1:]
    if len(digits) == 3:
        digits = "".join(character * 2 for character in digits)
    return Ok((int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16)))


def _linearize_channel(channel_value: int) -> float:
    """Convert one 0-255 sRGB channel to linear light (WCAG 2.x)."""
    srgb: float = channel_value / 255
    if srgb <= 0.03928:
        return srgb / 12.92
    return float(((srgb + 0.055) / 1.055) ** 2.4)


def relative_luminance(red: int, green: int, blue: int) -> float:
    """Return WCAG relative luminance (0.0 black to 1.0 white).

    Args:
        red: Red channel, 0-255.
        green: Green channel, 0-255.
        blue: Blue channel, 0-255.

    Returns:
        The luminance as a float.

    Raises:
        ValueError: If a channel is outside 0-255 (programmer error).
    """
    channels: tuple[tuple[str, int], ...] = (
        ("red", red),
        ("green", green),
        ("blue", blue),
    )
    for channel_name, channel_value in channels:
        if not 0 <= channel_value <= 255:
            raise ValueError(
                f"Channel {channel_name} must be 0-255, got {channel_value}"
            )
    return (
        0.2126 * _linearize_channel(red)
        + 0.7152 * _linearize_channel(green)
        + 0.0722 * _linearize_channel(blue)
    )


def contrast_ratio(first_luminance: float, second_luminance: float) -> float:
    """Return the WCAG contrast ratio (1.0 to 21.0) of two luminances.

    Args:
        first_luminance: Relative luminance of one color.
        second_luminance: Relative luminance of the other color.

    Returns:
        ``(lighter + 0.05) / (darker + 0.05)``, independent of argument order.
    """
    lighter: float = max(first_luminance, second_luminance)
    darker: float = min(first_luminance, second_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def pick_readable_text_color(background_hex: str) -> str:
    """Pick black or white text, whichever contrasts more with a background.

    Args:
        background_hex: Background color as ``#rgb`` or ``#rrggbb``.

    Returns:
        ``"#000000"`` or ``"#ffffff"``. An invalid background yields
        ``"#000000"`` (callers validate hex separately; this never raises).
    """
    parsed: Result[tuple[int, int, int]] = parse_hex(background_hex)
    if isinstance(parsed, Err):
        return _BLACK
    background_luminance: float = relative_luminance(*parsed.value)
    black_contrast: float = contrast_ratio(background_luminance, 0.0)
    white_contrast: float = contrast_ratio(background_luminance, 1.0)
    return _BLACK if black_contrast >= white_contrast else _WHITE
