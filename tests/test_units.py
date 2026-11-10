import pytest

from material_colors_grid import Err, Ok, css_size_to_px


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        ("1rem", 16.0),
        ("0.25rem", 4.0),
        ("1.5rem", 24.0),
        (".5rem", 8.0),
        ("12px", 12.0),
        ("12", 12.0),
        (" 8px ", 8.0),
        ("-2px", -2.0),
        (12, 12.0),
        (0.5, 0.5),
    ],
)
def test_converts_supported_sizes(size: str | int | float, expected: float) -> None:
    assert css_size_to_px(size) == Ok(expected)


def test_custom_rem_base() -> None:
    assert css_size_to_px("2rem", rem_base=10) == Ok(20.0)


@pytest.mark.parametrize("size", ["", "rem", "12zz", "1em", "1 rem", "1.2.3px", "#fff"])
def test_bad_strings_are_errors_naming_the_value(size: str) -> None:
    result = css_size_to_px(size)
    assert isinstance(result, Err)
    assert f'"{size}"' in result.error


@pytest.mark.parametrize("size", [True, None, [1]])
def test_non_size_types_are_errors(size: object) -> None:
    assert isinstance(css_size_to_px(size), Err)  # type: ignore[arg-type]
