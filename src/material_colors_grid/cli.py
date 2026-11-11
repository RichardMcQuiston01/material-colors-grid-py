"""Command line interface (a stable contract for scripts and Claude Plugins).

Commands::

    material-colors-grid render --input doc.json --output grid.png
    material-colors-grid render --colors colors.json --output grid.jpg
    material-colors-grid validate --input doc.json
    material-colors-grid schema [--json]
    material-colors-grid --version

With ``--json``, stdout is exactly one JSON object: ``{"ok": true, ...}`` or
``{"ok": false, "error": "..."}``. Diagnostics always go to stderr. Exit
codes: 0 success, 1 runtime/render/I-O failure, 2 invalid input or arguments.

Untrusted documents: a document's ``style.watermark.image_path`` is ignored
(never opened); a watermark is only loaded from the explicit ``--watermark``
flag. Output files are written atomically and never through a symlink or to a
non-regular file such as ``/dev/stdout``.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import os
import stat
import sys
import warnings
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import NoReturn

from PIL import Image

from material_colors_grid.colorlist import parse_color_list
from material_colors_grid.io import parse_imported_document
from material_colors_grid.models import ProjectDocument
from material_colors_grid.render import ImageFormat, render_to_image, save_image
from material_colors_grid.result import Err, Ok, Result
from material_colors_grid.schema import document_json_schema

PROG: str = "material-colors-grid"
EXIT_OK: int = 0
EXIT_RUNTIME_ERROR: int = 1
EXIT_INVALID_INPUT: int = 2
DEFAULT_QUALITY: int = 90
MAX_WATERMARK_BYTES: int = 20 * 1024 * 1024
STDIN_LABEL: str = "<stdin>"
_FORMAT_BY_NAME: dict[str, ImageFormat] = {"png": "png", "jpg": "jpg", "gif": "gif"}
_FORMAT_BY_SUFFIX: dict[str, ImageFormat] = {
    ".png": "png",
    ".jpg": "jpg",
    ".jpeg": "jpg",
    ".gif": "gif",
}


@dataclasses.dataclass(frozen=True, slots=True)
class CliFailure:
    """A failure to report to the user, with the process exit code to use."""

    message: str
    exit_code: int


class _UsageError(Exception):
    """Raised by the argument parser instead of exiting, so main can report it."""

    def __init__(self, message: str, usage: str, prog: str) -> None:
        super().__init__(message)
        self.message: str = message
        self.usage: str = usage
        self.prog: str = prog


class _ArgumentParser(argparse.ArgumentParser):
    """An ``ArgumentParser`` whose errors are raised, not printed and exited."""

    def error(self, message: str) -> NoReturn:
        raise _UsageError(message, self.format_usage(), self.prog)


def _package_version() -> str:
    """Return the installed package version, or a marker when not installed."""
    try:
        return version("material-colors-grid")
    except PackageNotFoundError:
        return "0.0.0+unknown"


def _positive_int(text: str) -> int:
    """Parse a flag value that must be an integer >= 1."""
    try:
        number: int = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f'"{text}" is not an integer') from None
    if number < 1:
        raise argparse.ArgumentTypeError(f'"{text}" must be an integer >= 1')
    return number


def _quality(text: str) -> int:
    """Parse a JPEG quality flag value, an integer from 1 to 100."""
    number: int = _positive_int(text)
    if number > 100:
        raise argparse.ArgumentTypeError(f'"{text}" must be between 1 and 100')
    return number


def _add_source_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the mutually exclusive, required ``--input`` / ``--colors`` flags."""
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--input",
        metavar="PATH",
        help="full document JSON file, or - for stdin",
    )
    group.add_argument(
        "--colors",
        metavar="PATH",
        help="simple color list JSON file, or - for stdin: "
        '[{"name": "Matte Black", "hex": "#111111", "category": "PLA"}]',
    )
    parser.add_argument(
        "--json", action="store_true", help="print one JSON object on stdout"
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for all commands.

    Returns:
        A parser whose errors raise instead of exiting the process.
    """
    parser = _ArgumentParser(
        prog=PROG,
        allow_abbrev=False,
        description="Render a grid of color swatches to PNG, JPG, or GIF.",
    )
    parser.add_argument("--version", action="version", version=_package_version())
    subparsers = parser.add_subparsers(dest="command", required=True)

    render = subparsers.add_parser(
        "render", allow_abbrev=False, help="render a document to an image"
    )
    _add_source_arguments(render)
    render.add_argument("--output", required=True, metavar="PATH", help="image file")
    render.add_argument(
        "--format",
        choices=sorted(_FORMAT_BY_NAME),
        help="image format (default: inferred from the --output suffix)",
    )
    render.add_argument(
        "--quality",
        type=_quality,
        default=DEFAULT_QUALITY,
        help=f"JPEG quality 1-100 (default {DEFAULT_QUALITY})",
    )
    render.add_argument(
        "--watermark",
        metavar="IMAGE_PATH",
        help="watermark image file (the only way to add a watermark: a "
        "document's style.watermark.image_path is ignored)",
    )
    render.add_argument("--header-text", metavar="TEXT", help="header band text")
    render.add_argument("--footer-text", metavar="TEXT", help="footer band text")
    render.add_argument(
        "--cards-per-row", type=_positive_int, metavar="N", help="cards per row"
    )

    validate = subparsers.add_parser(
        "validate", allow_abbrev=False, help="validate a document or color list"
    )
    _add_source_arguments(validate)

    schema = subparsers.add_parser(
        "schema", allow_abbrev=False, help="print the document JSON Schema"
    )
    schema.add_argument(
        "--json",
        action="store_true",
        help="accepted for uniformity; the schema is always JSON",
    )
    return parser


def _read_text(path: str) -> Result[str]:
    """Read UTF-8 text from ``path``, or from stdin when ``path`` is ``-``."""
    label: str = STDIN_LABEL if path == "-" else path
    try:
        if path == "-":
            return Ok(sys.stdin.read().removeprefix("\ufeff"))
        return Ok(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError) as error:
        return Err(f'Cannot read "{label}": {error}')


def _wrong_flag_hint(text: str, *, is_color_list: bool) -> str:
    """Suggest the other flag when a list was given as a document or vice versa."""
    try:
        decoded: object = json.loads(text)
    except ValueError:
        return ""
    if not is_color_list and isinstance(decoded, list):
        return " (this looks like a color list; did you mean --colors?)"
    if is_color_list and isinstance(decoded, dict):
        return " (did you mean --input?)"
    return ""


def _load_document(args: argparse.Namespace) -> Ok[ProjectDocument] | CliFailure:
    """Read and parse the document named by ``--input`` or ``--colors``."""
    is_color_list: bool = args.colors is not None
    path: str = args.colors if is_color_list else args.input
    text: Result[str] = _read_text(path)
    if isinstance(text, Err):
        return CliFailure(text.error, EXIT_INVALID_INPUT)
    parsed: Result[ProjectDocument] = (
        parse_color_list(text.value)
        if is_color_list
        else parse_imported_document(text.value)
    )
    if isinstance(parsed, Err):
        label: str = STDIN_LABEL if path == "-" else path
        hint: str = _wrong_flag_hint(text.value, is_color_list=is_color_list)
        return CliFailure(f'"{label}": {parsed.error}{hint}', EXIT_INVALID_INPUT)
    return parsed


def _resolve_format(explicit: str | None, output: str) -> Ok[ImageFormat] | CliFailure:
    """Pick the image format from ``--format``, else from the output suffix."""
    if explicit is not None:
        return Ok(_FORMAT_BY_NAME[explicit])
    suffix: str = Path(output).suffix.lower()
    inferred: ImageFormat | None = _FORMAT_BY_SUFFIX.get(suffix)
    if inferred is None:
        return CliFailure(
            f'Cannot infer image format from output "{output}" (suffix '
            f'"{suffix}" is not .png, .jpg, .jpeg or .gif; pass --format)',
            EXIT_INVALID_INPUT,
        )
    return Ok(inferred)


def _apply_overrides(
    document: ProjectDocument, args: argparse.Namespace
) -> ProjectDocument:
    """Apply ``--header-text``, ``--footer-text`` and ``--cards-per-row``."""
    style = document.style
    if args.header_text is not None:
        style = dataclasses.replace(
            style, header=dataclasses.replace(style.header, text=args.header_text)
        )
    if args.footer_text is not None:
        style = dataclasses.replace(
            style, footer=dataclasses.replace(style.footer, text=args.footer_text)
        )
    if args.cards_per_row is not None:
        style = dataclasses.replace(style, cards_per_row=args.cards_per_row)
    return dataclasses.replace(document, style=style)


def _load_watermark(path: str) -> Ok[Image.Image] | CliFailure:
    """Open the explicit ``--watermark`` file, fully loaded, as RGBA.

    The path must be a regular file of at most ``MAX_WATERMARK_BYTES`` (no
    FIFOs, devices or directories, so opening can never hang), and Pillow's
    decompression-bomb warning is treated as an error.
    """

    def failure(reason: str) -> CliFailure:
        return CliFailure(
            f'Cannot read watermark "{path}": {reason}', EXIT_RUNTIME_ERROR
        )

    try:
        status: os.stat_result = os.stat(path)
    except OSError as error:
        return failure(str(error))
    if not stat.S_ISREG(status.st_mode):
        return failure(
            "not a regular file (directories, pipes and devices are refused)"
        )
    if status.st_size > MAX_WATERMARK_BYTES:
        return failure(
            f"file is {status.st_size} bytes, over the {MAX_WATERMARK_BYTES} byte limit"
        )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as opened:
                return Ok(opened.convert("RGBA"))
    except (
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        return failure(f"{type(error).__name__}: {error}")


def _warn_ignored_document_watermark(document: ProjectDocument) -> None:
    """Warn once on stderr when the document names a watermark path (ignored)."""
    document_path: str | None = document.style.watermark.image_path
    if document_path:
        sys.stderr.write(
            f"{PROG}: warning: ignoring style.watermark.image_path "
            f"{json.dumps(document_path)} in the document (documents cannot "
            "load files); pass --watermark IMAGE_PATH to add a watermark\n"
        )


def _watermark_for(
    document: ProjectDocument, flag_path: str | None
) -> Ok[Image.Image | None] | CliFailure:
    """Load the ``--watermark`` image, if given.

    The document's own ``image_path`` is never opened; it only triggers a
    warning. A bad ``--watermark`` is a failure (exit 1).
    """
    _warn_ignored_document_watermark(document)
    if flag_path is None:
        return Ok(None)
    loaded = _load_watermark(flag_path)
    return loaded if isinstance(loaded, CliFailure) else Ok(loaded.value)


def _run_render(args: argparse.Namespace) -> dict[str, object] | CliFailure:
    """Render and save an image; return the success payload or a failure."""
    image_format = _resolve_format(args.format, args.output)
    if isinstance(image_format, CliFailure):
        return image_format
    loaded = _load_document(args)
    if isinstance(loaded, CliFailure):
        return loaded
    document: ProjectDocument = _apply_overrides(loaded.value, args)
    watermark = _watermark_for(document, args.watermark)
    if isinstance(watermark, CliFailure):
        return watermark
    rendered = render_to_image(document, watermark_image=watermark.value)
    if isinstance(rendered, Err):
        return CliFailure(f"Cannot render: {rendered.error}", EXIT_RUNTIME_ERROR)
    saved = save_image(
        rendered.value,
        args.output,
        image_format.value,
        quality=args.quality,
        background_color=document.style.background_color,
    )
    if isinstance(saved, Err):
        return CliFailure(saved.error, EXIT_RUNTIME_ERROR)
    width, height = rendered.value.size
    return {
        "ok": True,
        "output": args.output,
        "width": width,
        "height": height,
        "format": image_format.value,
    }


def _run_validate(args: argparse.Namespace) -> dict[str, object] | CliFailure:
    """Validate the input; return the success payload or a failure."""
    loaded = _load_document(args)
    if isinstance(loaded, CliFailure):
        return loaded
    return {"ok": True}


def _human_summary(args: argparse.Namespace, payload: dict[str, object]) -> str:
    """Describe a success for non-JSON output."""
    if args.command == "render":
        return (
            f"Wrote {payload['output']} "
            f"({payload['width']}x{payload['height']} {payload['format']})"
        )
    path: str = args.colors if args.colors is not None else args.input
    return f"Valid: {STDIN_LABEL if path == '-' else path}"


def _report_failure(
    failure: CliFailure, *, as_json: bool, usage: str = "", prog: str = PROG
) -> int:
    """Print a failure (JSON on stdout, or text on stderr) and return its code."""
    if as_json:
        sys.stdout.write(json.dumps({"ok": False, "error": failure.message}) + "\n")
    else:
        sys.stderr.write(usage)
        sys.stderr.write(f"{prog}: error: {failure.message}\n")
    return failure.exit_code


def _dispatch(args: argparse.Namespace) -> int:
    """Run the parsed command and print its result."""
    if args.command == "schema":
        sys.stdout.write(json.dumps(document_json_schema(), indent=2) + "\n")
        return EXIT_OK
    outcome: dict[str, object] | CliFailure = (
        _run_render(args) if args.command == "render" else _run_validate(args)
    )
    if isinstance(outcome, CliFailure):
        return _report_failure(outcome, as_json=args.json)
    if args.json:
        sys.stdout.write(json.dumps(outcome) + "\n")
    else:
        sys.stdout.write(_human_summary(args, outcome) + "\n")
    return EXIT_OK


def _handle_closed_stdout() -> int:
    """React to a closed stdout pipe: no traceback, no flush error at exit."""
    try:
        devnull: int = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
    except (OSError, ValueError):  # no real file descriptor (e.g. captured)
        pass
    with contextlib.suppress(OSError):
        sys.stderr.write(f"{PROG}: error: stdout was closed before output finished\n")
    return EXIT_RUNTIME_ERROR


def _run(arguments: list[str]) -> int:
    """Parse ``arguments``, run the command and print its result."""
    wants_json: bool = "--json" in arguments
    try:
        args: argparse.Namespace = build_parser().parse_args(arguments)
    except _UsageError as error:
        return _report_failure(
            CliFailure(error.message, EXIT_INVALID_INPUT),
            as_json=wants_json,
            usage=error.usage,
            prog=error.prog,
        )
    except SystemExit as exit_request:  # --help / --version
        return exit_request.code if isinstance(exit_request.code, int) else EXIT_OK
    try:
        return _dispatch(args)
    except BrokenPipeError:
        raise
    except Exception as error:  # noqa: BLE001 - last-resort boundary, no traceback
        message: str = f"Unexpected {type(error).__name__}: {error}"
        return _report_failure(
            CliFailure(message, EXIT_RUNTIME_ERROR),
            as_json=getattr(args, "json", False),
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Argument list, or ``None`` to use ``sys.argv[1:]``.

    Returns:
        Process exit code: 0 success, 1 runtime failure, 2 invalid input.
        Expected failures never raise or print a traceback, including a
        closed stdout pipe (exit 1 with a one-line note on stderr).
    """
    arguments: list[str] = list(sys.argv[1:] if argv is None else argv)
    try:
        code: int = _run(arguments)
        sys.stdout.flush()
        return code
    except BrokenPipeError:
        return _handle_closed_stdout()
