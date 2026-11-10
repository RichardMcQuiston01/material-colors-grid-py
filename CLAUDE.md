# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project Overview

`material-colors-grid` (PyPI) is a standalone Python package, inspired by the
TypeScript package
[`@richardmcquiston01/material-colors-grid`](https://github.com/RichardMcQuiston01/material-colors-grid).
It lays out a grid of color swatches (filament, acrylic, etc.) and exports it
as **PNG, JPG, or GIF** for online store listings.

Primary consumers:

1. **CLI** (`material-colors-grid`) - humans and scripts.
2. **Claude Plugins** - e.g. the Etsy plugin builds a grid from a listing's
   color options and attaches the image to the listing.
3. **Python projects** - imported as a library.

Constraints:

- Python 3.10+, fully typed (`py.typed` shipped), Apache-2.0.
- Minimal dependencies: **Pillow** for rendering, stdlib for everything else
  (`argparse`, `json`, `dataclasses`). Do not add a dependency without asking.
- Rendering is headless and deterministic (no display, no network).
- The TypeScript package is **inspiration only**. This is a normal Python
  package: idiomatic Python names, types, and conventions, and its own JSON
  document format. Do not copy the TypeScript API or document shape, and do
  not aim for compatibility with it.

## Project Structure

```
src/material_colors_grid/
  __init__.py      # Public API barrel (only place exports are declared)
  models.py        # Dataclasses: ProjectDocument, Category, Color, Style
  defaults.py      # create_default_document / create_category / create_color
  normalize.py     # Fill missing fields in partial documents
  validate.py      # is_hex_color, is_project_document (untrusted JSON)
  ordering.py      # Sorting + render model
  layout.py        # Pure layout engine (no drawing, no Pillow)
  color.py         # Hex parsing, luminance, WCAG contrast
  render.py        # Pillow renderer
  io.py            # document_to_json / parse_imported_document, file helpers
  result.py        # Result types (Ok / Err)
  cli.py           # CLI entry point
tests/             # pytest; mirrors src layout
pyproject.toml
CHANGELOG.md  ROADMAP.md  README.md  GETTING_STARTED.md
```

Keep `layout.py` and `ordering.py` free of Pillow so they stay pure and
easy to test.

## Domain Rules

- A `ProjectDocument` is a JSON-serializable tree of categories plus style
  settings. Categories hold colors and/or sub-categories. A color has `id`,
  `name`, `hex`.
- Hex colors: 3- or 6-digit only, with leading `#`. Reject everything else.
- **Ordering**: categories alphabetical, then sub-categories alphabetical,
  then colors **dark to light** (by luminance).
- Cards wrap at `cards_per_row`.
- A sole "Default" category prints **no header**.
- Header/footer bands render only when they have text.
- Card font color `"auto"` picks a readable color using WCAG contrast.
- Default canvas is 1440x1280; grow the canvas if content would be clipped.
- Watermark: image path/bytes, position (e.g. `bottom-right`), scale, opacity.
- Persist only user-authored data. The render model and layout are always
  derived, never stored.
- JPG has no alpha: flatten onto the document background. GIF is palette
  based: quantize without visible banding on swatches.

## Python API Shape

Fallible functions **return a result, they do not raise** for expected
failures (bad JSON, invalid hex, unwritable path). Callers must check it.

```python
from material_colors_grid import (
    Ok, Err, Result,
    ProjectDocument, create_default_document, create_color,
    parse_imported_document, render_to_image, save_image,
)

result: Result[ProjectDocument] = parse_imported_document(raw_json)
if isinstance(result, Err):
    print(result.error)  # descriptive: what failed, where, and why
else:
    document: ProjectDocument = result.value
```

Public names are idiomatic Python (snake_case):
`create_default_document`, `create_category`, `create_sub_category`,
`create_color`, `render_to_image`, `image_to_bytes`, `save_image`,
`document_to_json`, `parse_imported_document`, `is_hex_color`,
`is_project_document`, `build_render_model`, `compute_layout`.

Exceptions are reserved for programmer errors (wrong argument types).

## CLI Contract (important for Claude Plugins)

Plugins call the CLI, so its interface is a stable contract:

```bash
material-colors-grid render --input doc.json --output grid.png
material-colors-grid render --colors colors.json --output grid.jpg --format jpg
cat doc.json | material-colors-grid render --input - --output grid.png
material-colors-grid validate --input doc.json
material-colors-grid schema            # prints the document JSON schema
material-colors-grid --version
```

Rules:

- **JSON in, JSON out.** With `--json`, stdout is a single JSON object, e.g.
  `{"ok": true, "output": "grid.png", "width": 1440, "height": 1280}` or
  `{"ok": false, "error": "..."}`.
- Accept a full document, or a simple color list for quick use:
  `[{"name": "Matte Black", "hex": "#111111", "category": "PLA"}]`.
  This simple form is what the Etsy plugin builds from listing options.
- Never print prompts or progress to stdout. Diagnostics go to stderr.
- Exit codes: `0` success, `1` runtime/render failure, `2` invalid input or
  arguments. Errors name the file, field, and value at fault.
- Do not change flags, JSON keys, or exit codes without a CHANGELOG entry
  and a minor/major version bump.

## Development Commands

Uses [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --all-extras          # install with dev tools
uv run ruff format .          # format
uv run ruff check .           # lint
uv run mypy src tests         # strict type check
uv run pytest                 # tests
uv build                      # sdist + wheel
uv run twine check dist/*     # validate package metadata
```

Before opening a PR all of format, lint, mypy, pytest, and build must pass.

## Code Style

- Format with **ruff** (line length 88, double quotes). Prettier covers
  Markdown/JSON only (`.prettierrc.json`).
- **Type everything**: all function parameters, return types, and variables
  where inference is not obvious. `mypy --strict` must pass. Use
  `from __future__ import annotations`, `dataclasses(frozen=True, slots=True)`
  for models, and `Literal`/`TypedDict` where they add clarity.
- Descriptive names: `snake_case` functions/variables, `PascalCase` classes,
  `UPPER_SNAKE` constants. No abbreviations like `cfg`, `tmp`, `d`.
- Small, reusable, single-purpose functions. Return values, check them in
  the caller.
- Error messages must be specific, e.g.
  `Color "Matte Black" has invalid hex "#12" (expected 3 or 6 hex digits)`
  rather than `Invalid color`.
- Catch expected errors (I/O, JSON, Pillow) at the boundary and convert to
  `Err`. Continue where possible (e.g. skip a bad watermark with a warning
  in the result); otherwise exit gracefully with a clear message.
- Docstrings on all public functions (what, args, returns, failure modes).
- JSON everywhere for data interchange. No XML/SOAP.

## Testing

- `pytest`, with a test for every public export and a public-API test that
  fails when `__init__.py` exports change unintentionally.
- Test layout, ordering, validation, and contrast as pure functions (no
  images needed).
- Renderer tests: assert image size, mode, and sampled pixel colors; add a
  few golden-image tests with a tolerance. Cover PNG, JPG, and GIF.
- CLI tests call `main(argv)` and assert stdout JSON, stderr, and exit codes.
- Fonts: bundle one open-licensed font so output is identical across
  machines. Never depend on system fonts.

## Workflow

Follow `.claude/skills/git-workflow/SKILL.md`:

- Branch `feature/<name>` off `dev`, or `hotfix/<name>` for fixes. Merge to
  `dev` via PR, then `dev` -> `main` via PR. Merge commits only.
- Conventional Commits, summary <= 50 chars, body explains *why*.
- Open PRs as drafts. Do not delete branches after merge.
- **Never publish, tag, or merge to `main` without explicit owner approval.**

## Packaging and Release (PyPI)

- Build backend: `hatchling`; `src/` layout; version in `pyproject.toml`
  (single source of truth).
- Console script: `material-colors-grid = material_colors_grid.cli:main`.
- Release: bump version and date the `CHANGELOG.md` entry on `dev`, merge to
  `main`, then push a `vX.Y.Z` tag. The publish workflow verifies tag ==
  version, runs all checks, and publishes via PyPI **Trusted Publishing**
  (OIDC; no API tokens in the repo).
- Test releases go to TestPyPI first.

## Documentation

- `README.md` keeps the Buy Me a Coffee, License (Apache 2), and Copyright
  sections. Fill in Prerequisites / Installation / Usage / Examples.
- `GETTING_STARTED.md` snippets must be runnable; verify them in tests or CI.
- Add a short section documenting Claude Plugin usage (the Etsy flow:
  listing color options -> color list JSON -> CLI -> image).
- Update `CHANGELOG.md` for every user-visible change and `ROADMAP.md` for
  planned work.
