import io
import json
import os
import stat
import sys
from importlib.metadata import version
from pathlib import Path

import pytest
from PIL import Image

from material_colors_grid import create_default_document, document_to_json
from material_colors_grid.cli import main

COLORS: list[dict[str, str]] = [
    {"name": "Matte Black", "hex": "#111111", "category": "PLA"},
    {"name": "Red", "hex": "#ff0000", "category": "PLA"},
    {"name": "Clear", "hex": "#eeeeee", "category": "PETG"},
]


def write_colors(tmp_path: Path, colors: object = COLORS) -> Path:
    path = tmp_path / "colors.json"
    path.write_text(json.dumps(colors), encoding="utf-8")
    return path


def write_document(tmp_path: Path) -> Path:
    path = tmp_path / "doc.json"
    path.write_text(document_to_json(create_default_document()), encoding="utf-8")
    return path


def run_json(
    capsys: pytest.CaptureFixture[str], argv: list[str]
) -> tuple[int, dict[str, object], str]:
    code = main([*argv, "--json"])
    captured = capsys.readouterr()
    payload: dict[str, object] = json.loads(captured.out)
    return code, payload, captured.err


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == version("material-colors-grid")


def test_render_from_input_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "grid.png"
    code, payload, err = run_json(
        capsys,
        ["render", "--input", str(write_document(tmp_path)), "--output", str(output)],
    )
    assert code == 0
    assert err == ""
    assert payload == {
        "ok": True,
        "output": str(output),
        "width": 1440,
        "height": 1280,
        "format": "png",
    }


def test_render_from_colors_end_to_end_matches_reported_size(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "grid.png"
    code, payload, _ = run_json(
        capsys,
        ["render", "--colors", str(write_colors(tmp_path)), "--output", str(output)],
    )
    assert code == 0
    with Image.open(output) as image:
        assert image.format == "PNG"
        assert image.size == (payload["width"], payload["height"])


@pytest.mark.parametrize(
    ("suffix", "pillow_format", "expected"),
    [
        (".png", "PNG", "png"),
        (".jpg", "JPEG", "jpg"),
        (".jpeg", "JPEG", "jpg"),
        (".GIF", "GIF", "gif"),
    ],
)
def test_format_inferred_from_suffix(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    suffix: str,
    pillow_format: str,
    expected: str,
) -> None:
    output = tmp_path / f"grid{suffix}"
    code, payload, _ = run_json(
        capsys,
        ["render", "--colors", str(write_colors(tmp_path)), "--output", str(output)],
    )
    assert code == 0
    assert payload["format"] == expected
    with Image.open(output) as image:
        assert image.format == pillow_format


def test_explicit_format_overrides_suffix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "grid.bin"
    code, payload, _ = run_json(
        capsys,
        [
            "render", "--colors", str(write_colors(tmp_path)),
            "--output", str(output), "--format", "gif",
        ],
    )  # fmt: skip
    assert code == 0
    assert payload["format"] == "gif"
    with Image.open(output) as image:
        assert image.format == "GIF"


def test_unknown_suffix_without_format_is_invalid_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, payload, _ = run_json(
        capsys,
        ["render", "--colors", str(write_colors(tmp_path)),
         "--output", str(tmp_path / "grid.bmp")],
    )  # fmt: skip
    assert code == 2
    assert payload["ok"] is False
    assert '"grid.bmp"' in str(payload["error"]) or "grid.bmp" in str(payload["error"])
    assert ".bmp" in str(payload["error"])


def test_render_reads_stdin(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(COLORS)))
    output = tmp_path / "grid.png"
    code, payload, _ = run_json(
        capsys, ["render", "--colors", "-", "--output", str(output)]
    )
    assert code == 0
    assert payload["output"] == str(output)
    assert output.exists()


def test_stdin_invalid_json_names_stdin(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("{nope"))
    code, payload, _ = run_json(capsys, ["validate", "--input", "-"])
    assert code == 2
    assert str(payload["error"]).startswith('"<stdin>": Invalid JSON at line 1')


def test_overrides_change_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plain = tmp_path / "plain.png"
    banded = tmp_path / "banded.png"
    source = str(write_colors(tmp_path))
    run_json(capsys, ["render", "--colors", source, "--output", str(plain)])
    code, _, _ = run_json(
        capsys,
        ["render", "--colors", source, "--output", str(banded),
         "--header-text", "Filament", "--footer-text", "In stock",
         "--cards-per-row", "2"],
    )  # fmt: skip
    assert code == 0
    assert plain.read_bytes() != banded.read_bytes()


def test_missing_input_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "nope.json"
    code, payload, _ = run_json(
        capsys, ["render", "--input", str(missing), "--output", str(tmp_path / "o.png")]
    )
    assert code == 2
    assert f'Cannot read "{missing}"' in str(payload["error"])


def test_invalid_json_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    code, payload, _ = run_json(
        capsys, ["render", "--input", str(bad), "--output", str(tmp_path / "o.png")]
    )
    assert code == 2
    assert str(payload["error"]).startswith(f'"{bad}": Invalid JSON at line 1')


def test_invalid_hex_in_color_list(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_colors(tmp_path, [{"name": "Matte Black", "hex": "#12"}])
    code, payload, _ = run_json(
        capsys, ["render", "--colors", str(path), "--output", str(tmp_path / "o.png")]
    )
    assert code == 2
    assert 'colors[0].hex "#12"' in str(payload["error"])
    assert str(path) in str(payload["error"])
    assert not (tmp_path / "o.png").exists()


def test_invalid_hex_in_document(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "doc.json"
    path.write_text(
        json.dumps(
            {"categories": [{"name": "A", "colors": [{"name": "B", "hex": "red"}]}]}
        ),
        encoding="utf-8",
    )
    code, payload, _ = run_json(capsys, ["validate", "--input", str(path)])
    assert code == 2
    assert 'categories[0].colors[0].hex "red"' in str(payload["error"])


def test_human_output_and_stderr_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "grid.png"
    code = main(
        ["render", "--colors", str(write_colors(tmp_path)), "--output", str(output)]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == f"Wrote {output} (1440x1280 png)\n"
    assert captured.err == ""
    code = main(["validate", "--input", str(tmp_path / "nope.json")])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "nope.json" in captured.err


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["bogus"],
        ["render"],
        ["render", "--output", "o.png"],
        ["render", "--input", "a", "--colors", "b", "--output", "o.png"],
        ["render", "--input", "a", "--output", "o.png", "--format", "bmp"],
        ["render", "--input", "a", "--output", "o.png", "--cards-per-row", "0"],
        ["render", "--input", "a", "--output", "o.png", "--quality", "101"],
        ["render", "--input", "a", "--output", "o.png", "--nope"],
        ["validate"],
    ],
)
def test_bad_arguments_exit_2(
    capsys: pytest.CaptureFixture[str], argv: list[str]
) -> None:
    code = main(argv)
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "error:" in captured.err


def test_bad_arguments_emit_json_error_with_json_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(["render", "--input", "a", "--json"])
    captured = capsys.readouterr()
    assert code == 2
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert "--output" in payload["error"]


def test_bad_flag_value_names_value(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "render",
            "--input",
            "a",
            "--output",
            "o.png",
            "--cards-per-row",
            "x",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert '"x" is not an integer' in payload["error"]


@pytest.mark.skipif(
    os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="permissions are not enforced here",
)
def test_unwritable_output_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        code, payload, _ = run_json(
            capsys,
            ["render", "--colors", str(write_colors(tmp_path)),
             "--output", str(locked / "o.png")],
        )  # fmt: skip
    finally:
        locked.chmod(stat.S_IRWXU)
    assert code == 1
    assert "o.png" in str(payload["error"])


def test_output_in_missing_directory_exit_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "missing" / "o.png"
    code, payload, _ = run_json(
        capsys,
        ["render", "--colors", str(write_colors(tmp_path)), "--output", str(target)],
    )
    assert code == 1
    assert payload["ok"] is False
    assert str(target) in str(payload["error"])


def test_missing_watermark_exit_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "logo.png"
    code, payload, _ = run_json(
        capsys,
        ["render", "--colors", str(write_colors(tmp_path)),
         "--output", str(tmp_path / "o.png"), "--watermark", str(missing)],
    )  # fmt: skip
    assert code == 1
    assert f'Cannot read watermark "{missing}"' in str(payload["error"])


def test_watermark_is_applied(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (200, 200), (255, 0, 0, 255)).save(logo)
    source = str(write_colors(tmp_path))
    plain = tmp_path / "plain.png"
    marked = tmp_path / "marked.png"
    run_json(capsys, ["render", "--colors", source, "--output", str(plain)])
    code, _, _ = run_json(
        capsys,
        [
            "render",
            "--colors",
            source,
            "--output",
            str(marked),
            "--watermark",
            str(logo),
        ],
    )
    assert code == 0
    assert plain.read_bytes() != marked.read_bytes()


def test_bad_document_watermark_path_warns_and_renders(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "doc.json"
    path.write_text(
        json.dumps(
            {"categories": [], "style": {"watermark": {"image_path": "nope.png"}}}
        ),
        encoding="utf-8",
    )
    code, payload, err = run_json(
        capsys, ["render", "--input", str(path), "--output", str(tmp_path / "o.png")]
    )
    assert code == 0
    assert payload["ok"] is True
    assert "warning" in err and "nope.png" in err


def test_jpg_flattens_on_document_background(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "doc.json"
    path.write_text(
        json.dumps({"categories": [], "style": {"background_color": "#336699"}}),
        encoding="utf-8",
    )
    output = tmp_path / "o.jpg"
    code, _, _ = run_json(
        capsys, ["render", "--input", str(path), "--output", str(output)]
    )
    assert code == 0
    with Image.open(output) as image:
        pixel = image.convert("RGB").getpixel((5, 5))
    assert isinstance(pixel, tuple), f"Expected an RGB tuple, got {pixel!r}"
    red, green, blue = pixel
    assert abs(red - 0x33) < 8 and abs(green - 0x66) < 8 and abs(blue - 0x99) < 8


def test_validate_success_json_and_human(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_document(tmp_path)
    code, payload, err = run_json(capsys, ["validate", "--input", str(path)])
    assert (code, payload, err) == (0, {"ok": True}, "")
    code = main(["validate", "--colors", str(write_colors(tmp_path))])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.startswith("Valid: ")


def test_validate_color_list_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_colors(tmp_path, [{"name": "X", "hex": "nope"}])
    code, payload, _ = run_json(capsys, ["validate", "--colors", str(path)])
    assert code == 2
    assert payload["ok"] is False
    assert 'colors[0].hex "nope"' in str(payload["error"])


def test_schema_prints_json_schema(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["schema"]) == 0
    captured = capsys.readouterr()
    schema = json.loads(captured.out)
    assert captured.err == ""
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert set(schema["properties"]) == {"categories", "style"}
    assert "$defs" in schema


def test_unexpected_error_is_reported_without_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*_: object, **__: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("material_colors_grid.cli.render_to_image", explode)
    code, payload, _ = run_json(
        capsys,
        ["render", "--colors", str(write_colors(tmp_path)),
         "--output", str(tmp_path / "o.png")],
    )  # fmt: skip
    assert code == 1
    assert payload == {"ok": False, "error": "Unexpected RuntimeError: boom"}


def test_output_parent_is_a_file_exit_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    target = blocker / "o.png"
    code, payload, _ = run_json(
        capsys,
        ["render", "--colors", str(write_colors(tmp_path)), "--output", str(target)],
    )
    assert code == 1
    assert str(target) in str(payload["error"])
