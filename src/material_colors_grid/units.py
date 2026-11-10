"""CSS size to pixel conversion (pure)."""

from __future__ import annotations

import re
from typing import Final

from material_colors_grid.result import Err, Ok, Result

REM_IN_PIXELS: Final[float] = 16.0
_SIZE_PATTERN: Final = re.compile(r"(-?(?:\d+\.?\d*|\.\d+))(rem|px)?")


def css_size_to_px(
    size: str | int | float, rem_base: float = REM_IN_PIXELS
) -> Result[float]:
    """Convert a CSS size to pixels.

    Args:
        size: ``"1.5rem"``, ``"12px"``, a bare number string such as ``"12"``
            (pixels), or an ``int``/``float`` (pixels). Surrounding whitespace
            is ignored.
        rem_base: Pixels per ``rem`` (16 by default).

    Returns:
        ``Ok`` with the pixel value, or ``Err`` naming the offending value
        when it is not a supported size (other units, booleans, text).
        Never raises.
    """
    if isinstance(size, bool) or not isinstance(size, (str, int, float)):
        return Err(f"CSS size {size!r} is invalid (expected a string or number)")
    if not isinstance(size, str):
        return Ok(float(size))
    match = _SIZE_PATTERN.fullmatch(size.strip())
    if match is None:
        return Err(
            f'CSS size "{size}" is invalid '
            '(expected a number with an optional "rem" or "px" unit)'
        )
    amount = float(match.group(1))
    return Ok(amount * rem_base if match.group(2) == "rem" else amount)
