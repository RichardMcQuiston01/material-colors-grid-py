import pytest

from material_colors_grid import (
    Err,
    Ok,
    contrast_ratio,
    parse_hex,
    pick_readable_text_color,
    relative_luminance,
)


def test_parse_hex_six_digits() -> None:
    assert parse_hex("#ff8000") == Ok((255, 128, 0))


def test_parse_hex_three_digits_expands() -> None:
    assert parse_hex("#f80") == Ok((255, 136, 0))


@pytest.mark.parametrize("bad", ["ff8000", "#12", "#1234", "#gggggg", "", "#"])
def test_parse_hex_rejects_invalid(bad: str) -> None:
    result = parse_hex(bad)
    assert isinstance(result, Err)
    assert f'"{bad}"' in result.error
    assert "3 or 6 hex digits" in result.error


def test_parse_hex_rejects_non_string() -> None:
    result = parse_hex(123)  # type: ignore[arg-type]
    assert isinstance(result, Err)
    assert "int" in result.error


def test_luminance_extremes() -> None:
    assert relative_luminance(0, 0, 0) == 0.0
    assert relative_luminance(255, 255, 255) == pytest.approx(1.0)


def test_luminance_rejects_out_of_range_channel() -> None:
    with pytest.raises(ValueError, match="red"):
        relative_luminance(256, 0, 0)


def test_black_white_contrast_is_21() -> None:
    white = relative_luminance(255, 255, 255)
    black = relative_luminance(0, 0, 0)
    assert contrast_ratio(white, black) == pytest.approx(21.0)
    assert contrast_ratio(black, white) == pytest.approx(21.0)


def test_contrast_of_identical_is_one() -> None:
    assert contrast_ratio(0.3, 0.3) == pytest.approx(1.0)


def test_known_gray_contrast() -> None:
    # #777777 on white is the well-known ~4.48:1 pair.
    gray = relative_luminance(0x77, 0x77, 0x77)
    assert contrast_ratio(gray, 1.0) == pytest.approx(4.48, abs=0.01)


def test_pick_readable_text_color() -> None:
    assert pick_readable_text_color("#000000") == "#ffffff"
    assert pick_readable_text_color("#ffffff") == "#000000"
    assert pick_readable_text_color("#111") == "#ffffff"
    assert pick_readable_text_color("#ffff00") == "#000000"


def test_pick_readable_text_color_invalid_falls_back_to_black() -> None:
    assert pick_readable_text_color("nope") == "#000000"
