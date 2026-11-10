# Getting Started

A task-oriented guide to `material-colors-grid`. Python snippets were run
against the library; CLI snippets follow the CLI contract in `CLAUDE.md`.

- [Install](#install)
- [Build a document](#build-a-document)
- [Render and save an image](#render-and-save-an-image)
- [Save and load document JSON](#save-and-load-document-json)
- [The simple color-list format](#the-simple-color-list-format)
- [Use the CLI](#use-the-cli)
- [Handle errors with Result](#handle-errors-with-result)

## Install

```bash
pip install material-colors-grid
# or
uv add material-colors-grid
```

Requires Python 3.10+. Pillow is installed automatically.

## Build a document

A document is a tree of categories (each holding colors and/or
sub-categories) plus style settings. Objects are frozen dataclasses, so change
them with `dataclasses.replace`.

```python
from dataclasses import replace

from material_colors_grid import (
    create_category,
    create_color,
    create_default_document,
)

document = create_default_document()  # one empty "Default" category
pla = create_category(
    "PLA",
    colors=[
        create_color("Matte Black", "#111111"),
        create_color("Signal Red", "#d62828"),
        create_color("Snow White", "#fafafa"),
    ],
)
document = replace(document, categories=(pla,))
```

Rules to know: hex values are `#rgb` or `#rrggbb` only. Categories sort
alphabetically, then sub-categories, then colors dark to light. A sole
`Default` category prints no header. Use `create_sub_category` to nest.

Change the look through `document.style`:

```python
from dataclasses import replace

from material_colors_grid import BandStyle

styled = replace(
    document,
    style=replace(
        document.style,
        cards_per_row=3,
        header=BandStyle(text="Available colors"),
    ),
)
```

The default canvas is 1440x1280. It grows when content would be clipped.

## Render and save an image

`render_to_image` returns a Pillow `Image` inside a `Result`. `save_image`
infers the format from the suffix (`.png`, `.jpg`, `.jpeg`, `.gif`).

```python
from material_colors_grid import Err, render_to_image, save_image

rendered = render_to_image(document)
if isinstance(rendered, Err):
    raise SystemExit(rendered.error)
image = rendered.value  # RGBA, 1440x1280 for this document

for filename in ("grid.png", "grid.jpg", "grid.gif"):
    saved = save_image(image, filename)
    if isinstance(saved, Err):
        raise SystemExit(saved.error)
```

Pass the format explicitly, set JPEG quality, and give the color that
transparent pixels are flattened onto (JPG and GIF have no full alpha):

```python
save_image(
    image,
    "grid.jpg",
    "jpg",
    quality=85,
    background_color=document.style.background_color,
)
```

Need bytes instead of a file (for an upload)? Use `image_to_bytes(image,
"png")`, which also returns a `Result`.

## Save and load document JSON

```python
from material_colors_grid import (
    Err,
    document_to_json,
    load_document_file,
    parse_imported_document,
    save_json_file,
)

text = document_to_json(document)  # indent=None for compact output
saved = save_json_file("doc.json", text)
loaded = load_document_file("doc.json")  # Result[ProjectDocument]
if isinstance(loaded, Err):
    raise SystemExit(loaded.error)
assert loaded.value == document

parsed = parse_imported_document(text)  # from a string instead of a file
```

Missing fields in partial documents are filled with defaults. Only
user-authored data is stored; layout and the render model are derived.

## The simple color-list format

The CLI also accepts a plain list, which is the easiest thing for a script to
produce. `category` is optional (colors without one go into `Default`):

```json
[
  { "name": "Matte Black", "hex": "#111111", "category": "PLA" },
  { "name": "Signal Red", "hex": "#d62828", "category": "PLA" },
  { "name": "Clear", "hex": "#eeeeee" }
]
```

The library has no list parser of its own; to use the list from Python, build
a document from it (see
[docs/claude-plugins.md](docs/claude-plugins.md#library-api-example)).

## Use the CLI

> CLI snippets in this section follow the documented CLI contract.

```bash
# Full document in, PNG out
material-colors-grid render --input doc.json --output grid.png

# Simple color list in, JPG out
material-colors-grid render --colors colors.json --output grid.jpg --format jpg

# Read from stdin
cat doc.json | material-colors-grid render --input - --output grid.png

# Check a document without rendering
material-colors-grid validate --input doc.json

# Print the document JSON schema
material-colors-grid schema

material-colors-grid --version
```

Other `render` flags: `--quality`, `--watermark`, `--header-text`,
`--footer-text`, `--cards-per-row`.

With `--json`, stdout is one JSON object and nothing else:

```bash
material-colors-grid render --colors colors.json --output grid.png --json
# {"ok": true, "output": "grid.png", "width": 1440, "height": 1280}
# {"ok": false, "error": "..."}
```

Exit codes: `0` success, `1` runtime or render failure, `2` invalid input or
arguments. Diagnostics go to stderr; stdout never carries prompts or progress.

## Handle errors with Result

Fallible functions return a result instead of raising. Check it before using
the value:

```python
from material_colors_grid import Err, parse_imported_document

result = parse_imported_document(
    '{"categories": [{"name": "PLA", "colors": '
    '[{"name": "Matte Black", "hex": "#12"}]}]}'
)
if isinstance(result, Err):
    print(result.error)
    # categories[0].colors[0].hex "#12" is invalid
    # (expected 3 or 6 hex digits)
else:
    document = result.value
```

Errors say what failed, where (a JSON path or file path), and why. Other
examples: `Invalid JSON at line 1, column 2: ...` and `Cannot read
"missing.json": ...`. Exceptions are reserved for programmer errors such as
passing the wrong argument types.

[Back to README](README.md)
