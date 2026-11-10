"""CLI behavior for untrusted documents, paths and pipes."""

import io
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from PIL import Image

from material_colors_grid import create_default_document, document_to_json
from material_colors_grid.cli import main

COLORS: list[dict[str, str]] = [
    {"name": "Matte Black", "hex": "#111111", "category": "PLA"},
    {"name": "Red", "hex": "#ff0000", "category": "PLA"},
]
BOM: bytes = b"\xef\xbb\xbf"

needs_fifo = pytest.mark.skipif(
    not hasattr(os, "mkfifo"), reason="named pipes are not available"
)
needs_symlink = pytest.mark.skipif(
    os.name == "nt", reason="symlinks need privileges on Windows"
)


def write_colors(tmp_path: Path) -> Path:
    path = tmp_path / "colors.json"
    path.write_text(json.dumps(COLORS), encoding="utf-8")
    return path


def write_document(tmp_path: Path) -> Path:
    path = tmp_path / "doc.json"
    path.write_text(document_to_json(create_default_document()), encoding="utf-8")
    return path


def write_watermark_document(tmp_path: Path, image_path: str | None) -> Path:
    path = tmp_path / "wm.json"
    path.write_text(
        json.dumps(
            {"categories": [], "style": {"watermark": {"image_path": image_path}}}
        ),
        encoding="utf-8",
    )
    return path


def run_json(
    capsys: pytest.CaptureFixture[str], argv: list[str]
) -> tuple[int, dict[str, object], str]:
    code = main([*argv, "--json"])
    captured = capsys.readouterr()
    payload: dict[str, object] = json.loads(captured.out)
    return code, payload, captured.err


# --- document watermark path is ignored ------------------------------------


@needs_fifo
def test_document_image_path_is_never_opened_and_warns_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fifo = tmp_path / "pipe.png"
    os.mkfifo(fifo)  # opening this for reading would hang forever
    document = write_watermark_document(tmp_path, str(fifo))
    code, payload, err = run_json(
        capsys,
        ["render", "--input", str(document), "--output", str(tmp_path / "o.png")],
    )
    assert code == 0 and payload["ok"] is True
    assert err.count("warning") == 1
    assert "style.watermark.image_path" in err and "--watermark" in err


def test_missing_document_image_path_still_renders(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    document = write_watermark_document(tmp_path, "/nonexistent/logo.png")
    code, payload, err = run_json(
        capsys,
        ["render", "--input", str(document), "--output", str(tmp_path / "o.png")],
    )
    assert code == 0 and payload["ok"] is True
    assert err.count("warning") == 1


@pytest.mark.parametrize("image_path", ["", None])
def test_no_warning_without_a_document_image_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], image_path: str | None
) -> None:
    document = write_watermark_document(tmp_path, image_path)
    code, _, err = run_json(
        capsys,
        ["render", "--input", str(document), "--output", str(tmp_path / "o.png")],
    )
    assert code == 0 and err == ""


def test_explicit_watermark_is_applied_and_document_path_ignored(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (10, 10), (255, 0, 0, 255)).save(logo)
    document = write_watermark_document(tmp_path, "/nonexistent/other.png")
    plain = tmp_path / "plain.png"
    marked = tmp_path / "marked.png"
    base = ["render", "--input", str(document)]
    assert run_json(capsys, [*base, "--output", str(plain)])[0] == 0
    code, _, err = run_json(
        capsys, [*base, "--output", str(marked), "--watermark", str(logo)]
    )
    assert code == 0 and err.count("warning") == 1
    assert plain.read_bytes() != marked.read_bytes()


# --- explicit watermark file checks ----------------------------------------


@needs_fifo
def test_fifo_watermark_is_rejected_without_hanging(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fifo = tmp_path / "pipe.png"
    os.mkfifo(fifo)
    outcome: list[tuple[int, str]] = []

    def run() -> None:
        code = main(
            ["render", "--colors", str(write_colors(tmp_path)),
             "--output", str(tmp_path / "o.png"), "--watermark", str(fifo), "--json"]
        )  # fmt: skip
        outcome.append((code, capsys.readouterr().out))

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout=10)
    assert not worker.is_alive(), "loading a FIFO watermark hung"
    code, out = outcome[0]
    payload = json.loads(out)
    assert code == 1
    assert str(fifo) in payload["error"] and "not a regular file" in payload["error"]
    assert not (tmp_path / "o.png").exists()


def test_directory_watermark_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, payload, _ = run_json(
        capsys,
        ["render", "--colors", str(write_colors(tmp_path)),
         "--output", str(tmp_path / "o.png"), "--watermark", str(tmp_path)],
    )  # fmt: skip
    assert code == 1
    assert "not a regular file" in str(payload["error"])


def test_oversized_watermark_is_rejected(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (10, 10)).save(logo)
    monkeypatch.setattr("material_colors_grid.cli.MAX_WATERMARK_BYTES", 10)
    code, payload, _ = run_json(
        capsys,
        ["render", "--colors", str(write_colors(tmp_path)),
         "--output", str(tmp_path / "o.png"), "--watermark", str(logo)],
    )  # fmt: skip
    assert code == 1
    assert "byte limit" in str(payload["error"]) and str(logo) in str(payload["error"])


def test_decompression_bomb_warning_is_an_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (100, 100)).save(logo)
    # Between the limit and twice the limit Pillow warns instead of raising.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 6000)
    code, payload, _ = run_json(
        capsys,
        ["render", "--colors", str(write_colors(tmp_path)),
         "--output", str(tmp_path / "o.png"), "--watermark", str(logo)],
    )  # fmt: skip
    assert code == 1
    assert "DecompressionBomb" in str(payload["error"])


# --- output safety ----------------------------------------------------------


@needs_symlink
def test_symlink_output_is_refused_and_victim_untouched(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    victim = tmp_path / "victim.txt"
    victim.write_text("precious", encoding="utf-8")
    link = tmp_path / "o.png"
    link.symlink_to(victim)
    code, payload, _ = run_json(
        capsys,
        ["render", "--colors", str(write_colors(tmp_path)), "--output", str(link)],
    )
    assert code == 1
    assert str(link) in str(payload["error"]) and "symlink" in str(payload["error"])
    assert victim.read_text(encoding="utf-8") == "precious"
    assert link.is_symlink()


@pytest.mark.skipif(
    not Path("/dev/stdout").exists() or not Path("/dev/null").exists(),
    reason="needs POSIX device files",
)
@pytest.mark.parametrize("device", ["/dev/stdout", "/dev/null"])
def test_device_output_is_refused_and_json_stdout_is_one_object(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], device: str
) -> None:
    code = main(
        ["render", "--colors", str(write_colors(tmp_path)),
         "--output", device, "--format", "png", "--json"]
    )  # fmt: skip
    payload = json.loads(capsys.readouterr().out)  # exactly one JSON object
    assert code == 1
    assert payload["ok"] is False and device in payload["error"]


def test_directory_output_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "out.png"
    target.mkdir()
    code, payload, _ = run_json(
        capsys,
        ["render", "--colors", str(write_colors(tmp_path)), "--output", str(target)],
    )
    assert code == 1
    assert "directory" in str(payload["error"]) and str(target) in str(payload["error"])


def test_failed_output_leaves_no_temp_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    blocker = out_dir / "o.png"
    blocker.mkdir()  # makes the final os.replace fail after the temp is written
    code, _, _ = run_json(
        capsys,
        ["render", "--colors", str(write_colors(tmp_path)), "--output", str(blocker)],
    )
    assert code == 1
    assert [p.name for p in out_dir.iterdir()] == ["o.png"]


def test_successful_output_leaves_only_the_image(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    code, _, _ = run_json(
        capsys,
        ["render", "--colors", str(write_colors(tmp_path)),
         "--output", str(out_dir / "o.png")],
    )  # fmt: skip
    assert code == 0
    assert [p.name for p in out_dir.iterdir()] == ["o.png"]


# --- BOM, hints, argparse prefix, schema --json ----------------------------


def test_bom_prefixed_files_are_accepted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    colors = tmp_path / "bom_colors.json"
    colors.write_bytes(BOM + json.dumps(COLORS).encode())
    code, payload, _ = run_json(capsys, ["validate", "--colors", str(colors)])
    assert code == 0 and payload == {"ok": True}
    document = tmp_path / "bom_doc.json"
    document.write_bytes(BOM + document_to_json(create_default_document()).encode())
    code, payload, _ = run_json(capsys, ["validate", "--input", str(document)])
    assert code == 0 and payload == {"ok": True}


def test_bom_on_stdin_is_accepted(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("﻿" + json.dumps(COLORS)))
    code, payload, _ = run_json(capsys, ["validate", "--colors", "-"])
    assert code == 0 and payload == {"ok": True}


@pytest.mark.parametrize("command", ["validate", "render"])
def test_color_list_passed_to_input_hints_colors_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    extra = ["--output", str(tmp_path / "o.png")] if command == "render" else []
    code, payload, _ = run_json(
        capsys, [command, "--input", str(write_colors(tmp_path)), *extra]
    )
    assert code == 2
    assert "(this looks like a color list; did you mean --colors?)" in str(
        payload["error"]
    )


@pytest.mark.parametrize("command", ["validate", "render"])
def test_document_passed_to_colors_hints_input_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    extra = ["--output", str(tmp_path / "o.png")] if command == "render" else []
    code, payload, _ = run_json(
        capsys, [command, "--colors", str(write_document(tmp_path)), *extra]
    )
    assert code == 2
    assert "(did you mean --input?)" in str(payload["error"])


def test_no_hint_for_plain_invalid_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    code, payload, _ = run_json(capsys, ["validate", "--input", str(broken)])
    assert code == 2
    assert "did you mean" not in str(payload["error"])


@pytest.mark.parametrize(
    ("argv", "prefix"),
    [
        (["render", "--input", "a"], "material-colors-grid render: error: "),
        (["validate"], "material-colors-grid validate: error: "),
        (["bogus"], "material-colors-grid: error: "),
    ],
)
def test_argparse_errors_have_exactly_one_prefix(
    capsys: pytest.CaptureFixture[str], argv: list[str], prefix: str
) -> None:
    code = main(argv)
    error_lines = [
        line for line in capsys.readouterr().err.splitlines() if ": error: " in line
    ]
    assert code == 2
    assert len(error_lines) == 1
    assert error_lines[0].startswith(prefix)
    assert error_lines[0].count(": error: ") == 1
    assert "error: material-colors-grid" not in error_lines[0]


def test_argparse_error_json_has_no_prefix(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, payload, _ = run_json(capsys, ["render", "--input", "a"])
    assert code == 2
    assert not str(payload["error"]).startswith("material-colors-grid")


def test_schema_accepts_json_flag(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["schema", "--json"]) == 0
    with_flag = json.loads(capsys.readouterr().out)
    assert main(["schema"]) == 0
    assert json.loads(capsys.readouterr().out) == with_flag


# --- closed stdout ----------------------------------------------------------


def test_broken_pipe_is_handled_without_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ClosedStdout:
        def write(self, _: str) -> int:
            raise BrokenPipeError

        def flush(self) -> None:
            raise BrokenPipeError

        def fileno(self) -> int:
            raise io.UnsupportedOperation

    monkeypatch.setattr(sys, "stdout", ClosedStdout())
    code = main(["validate", "--colors", str(write_colors(tmp_path)), "--json"])
    assert code == 1
    assert "stdout was closed" in capsys.readouterr().err


def test_closed_pipe_in_a_real_process_has_no_traceback() -> None:
    process = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; from material_colors_grid.cli import main; "
         "sys.exit(main(['schema']))"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )  # fmt: skip
    assert process.stdout is not None and process.stderr is not None
    process.stdout.close()  # the reader goes away before the output is written
    stderr = process.stderr.read().decode()
    process.stderr.close()
    assert process.wait(timeout=60) in (0, 1)
    assert "Traceback" not in stderr
