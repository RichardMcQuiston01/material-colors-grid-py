"""Hard limits that keep untrusted input from exhausting time or memory.

Every limit is enforced by the validators (document and color-list paths) so
hostile input is rejected with a descriptive ``Err``. The canvas limits are
enforced a second time inside ``render_to_image`` because layout can widen the
canvas and models can be built without validation.

These constants are intentionally not re-exported from the package root.
"""

from __future__ import annotations

from typing import Final

MAX_CANVAS_DIMENSION: Final[int] = 8192
"""Maximum canvas width and height in pixels (each, after layout growth)."""

MAX_CARDS_PER_ROW: Final[int] = 50
"""Maximum value of ``style.cards_per_row``."""

MAX_COLORS: Final[int] = 500
"""Maximum number of colors across the whole document."""

MAX_CANVAS_PIXELS: Final[int] = 50_000_000
"""Maximum canvas area (width * height) in pixels."""

MAX_NAME_LENGTH: Final[int] = 100
"""Maximum characters in a color, category or sub-category name."""

MAX_BAND_TEXT_LENGTH: Final[int] = 200
"""Maximum characters in header or footer text."""

MAX_JSON_NESTING_DEPTH: Final[int] = 32
"""Maximum nesting of JSON arrays/objects in parsed input."""

MAX_JSON_INPUT_BYTES: Final[int] = 5_000_000
"""Maximum size of JSON text accepted by the parsers (UTF-8 bytes)."""

MAX_CATEGORIES: Final[int] = 500
"""Maximum categories plus sub-categories across the whole document."""

MAX_CATEGORY_DEPTH: Final[int] = 15
"""Maximum category nesting (top level counts as 1).

This is what ``MAX_JSON_NESTING_DEPTH`` allows for a document: each level of
sub-category costs two JSON levels (the array and the object).
"""
