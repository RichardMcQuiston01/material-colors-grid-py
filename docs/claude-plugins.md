# Using material-colors-grid in Claude Plugins

How a Claude Plugin turns a shop listing's color options into a swatch-grid
image. The worked example is the Etsy flow:

```
Etsy listing color options
  -> color-list JSON (name, hex, optional category)
  -> material-colors-grid render --colors - --output grid.png --json
  -> one JSON result (ok / output / width / height, or ok / error)
  -> attach the image to the listing
```

The CLI is a stable contract, so plugins should call it rather than depend on
library internals. Flags, JSON keys, and exit codes change only with a
CHANGELOG entry and a version bump.

> CLI and Python snippets here were run against the CLI and library.

## 1. Build the color list

Each listing color option becomes one item:

```json
[
  { "name": "Matte Black", "hex": "#111111", "category": "PLA" },
  { "name": "Signal Red", "hex": "#d62828", "category": "PLA" },
  { "name": "Clear", "hex": "#eeeeee", "category": "PETG" }
]
```

| Key        | Required | Notes                                          |
| ---------- | -------- | ---------------------------------------------- |
| `name`     | yes      | Shown on the card.                             |
| `hex`      | yes      | `#rgb` or `#rrggbb`. Anything else is invalid. |
| `category` | no       | Groups cards under a heading.                  |

Colors are drawn dark to light inside each category, and categories sort
alphabetically. If every item has no category (or one category, "Default"),
no heading is printed.

## 2. Choose hex values carefully

Etsy variation values are free text ("Forest", "Sunset Orange"). They carry no
color value, so the plugin must supply one. Never guess silently:

1. **Prefer a known source.** The manufacturer's published swatch or hex, a
   product photo the seller picks from, or a hex the seller typed.
2. **If you must propose a value, say so.** Show the seller a table of
   `name -> proposed hex` marked as suggestions and get explicit confirmation
   before rendering. A grid is a promise to buyers about what they will
   receive.
3. **Never invent hex values for ambiguous names** ("Galaxy", "Rainbow",
   "Silk Gold"). Ask, or leave the option out and tell the seller.
4. **Validate before calling the CLI.** Hex must be 3 or 6 digits with a
   leading `#`. Normalize `111111` to `#111111` only when the intent is
   unambiguous.
5. **Remind the seller that screens differ.** Swatches approximate real
   material; say so in the listing text if color accuracy matters.

## 3. Call the CLI

Pipe the list on stdin with `--colors -` and read the single JSON object from
stdout.

```bash
echo '[{"name": "Matte Black", "hex": "#111111", "category": "PLA"}]' \
  | material-colors-grid render --colors - --output grid.png --json
```

Success (exit code `0`):

```json
{
  "ok": true,
  "output": "grid.png",
  "width": 1440,
  "height": 1280,
  "format": "png"
}
```

Failure (exit code `1` or `2`):

```json
{
  "ok": false,
  "error": "\"<stdin>\": colors[0].hex \"#12\" is invalid for color \"X\" (expected 3 or 6 hex digits with a leading #)"
}
```

Rules the plugin can rely on:

- With `--json`, stdout is exactly one JSON object. Diagnostics and warnings
  go to stderr; log them, do not parse them.
- Exit codes: `0` success, `1` runtime or render failure, `2` invalid input
  or arguments.
- Errors name the file, field, and value at fault, so they can be shown to
  the seller as is.

Useful flags: `--format png|jpg|gif`, `--quality` (JPEG), `--cards-per-row`,
`--header-text`, `--footer-text`, `--watermark <image>`. To check a list
without rendering, use `validate`.

## 4. Subprocess example

```python
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def render_color_grid(
    colors: list[dict[str, str]], output: Path
) -> dict[str, object]:
    """Render a color list with the CLI and return its JSON result.

    Raises RuntimeError with the CLI's message on failure.
    """
    completed = subprocess.run(
        [
            "material-colors-grid",
            "render",
            "--colors",
            "-",
            "--output",
            str(output),
            "--json",
        ],
        input=json.dumps(colors),
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        result: dict[str, object] = json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(
            f"CLI exit {completed.returncode}, no JSON on stdout: "
            f"{completed.stderr.strip()}"
        ) from None
    if completed.returncode != 0 or not result.get("ok"):
        raise RuntimeError(
            f"CLI exit {completed.returncode}: {result.get('error')}"
        )
    return result


colors = [
    {"name": "Matte Black", "hex": "#111111", "category": "PLA"},
    {"name": "Signal Red", "hex": "#d62828", "category": "PLA"},
]
result = render_color_grid(colors, Path("grid.png"))
print(result["output"], result["width"], result["height"])
```

If the executable is missing, `subprocess.run` raises `FileNotFoundError`;
tell the plugin user to run `pip install material-colors-grid`.

## Library API example

Plugins that already run Python can skip the subprocess. `parse_color_list`
takes the color-list JSON text; use `color_list_to_document` if the list is
already decoded. Both return a `Result` and never raise for bad data. This
snippet was run as written.

```python
from __future__ import annotations

import json
from pathlib import Path

from material_colors_grid import (
    Err,
    color_list_to_document,
    parse_color_list,
    render_to_image,
    save_image,
)

options_json = (
    '[{"name": "Matte Black", "hex": "#111111", "category": "PLA"},'
    ' {"name": "Signal Red", "hex": "#d62828", "category": "PLA"}]'
)
built = parse_color_list(options_json)
if isinstance(built, Err):
    raise SystemExit(built.error)

# Same result from an already decoded list:
decoded_built = color_list_to_document(json.loads(options_json))
if isinstance(decoded_built, Err):
    raise SystemExit(decoded_built.error)

rendered = render_to_image(built.value)
if isinstance(rendered, Err):
    raise SystemExit(rendered.error)
saved = save_image(rendered.value, Path("grid.png"))
if isinstance(saved, Err):
    raise SystemExit(saved.error)
print(saved.value, rendered.value.size)  # grid.png (1440, 1280)
```

## 5. Attach the image to the listing

Attaching is the plugin's job (via its Etsy connector or API); this package
only produces the file. Before uploading:

- Confirm the `output` path from the JSON result exists, and read the
  reported `width` and `height`.
- Show the image to the seller for approval when the hex values were
  suggested rather than supplied.
- Add it as an additional listing image. Do not replace the main photo
  unless the seller asks.

## Image size guidance

Etsy's image requirements change; check the current Etsy Seller Handbook
before relying on numbers. These are assumptions, not Etsy rules:

- The default 1440x1280 canvas is fine for a listing image. The grid grows
  taller when there are many colors, so a very long list can produce a tall
  image that Etsy crops or shrinks in thumbnails. Prefer more
  `--cards-per-row` or splitting by category over a very tall image.
- PNG keeps text crisp and is the safe default. Use JPG (`--quality 85-90`)
  if file size matters. GIF is limited to 256 colors and rarely better for
  swatches.
- Keep file size modest (a few MB at most) and the image at least as wide as
  the largest size Etsy asks for. Verify both against current Etsy docs.
- Judge readability at thumbnail size: fewer, larger cards beat many small
  ones.

## Troubleshooting by exit code

| Exit | Meaning                      | What to do                                                                                                                                                                                         |
| ---- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `0`  | Success                      | Read `output`, `width`, `height` from the JSON.                                                                                                                                                    |
| `1`  | Runtime or render failure    | Read `error`. Typical causes: unwritable output path or missing directory, unreadable watermark file, encoding failure. Fix and retry.                                                             |
| `2`  | Invalid input or arguments   | Read `error`; it names the file, field, and value. Typical causes: bad hex (`#12`), malformed JSON, missing or unreadable input file, unknown flag or `--format`, unknown output suffix, no input. |
| n/a  | `FileNotFoundError` on `run` | The CLI is not installed or not on `PATH`. Install the package.                                                                                                                                    |
| any  | stdout is not JSON           | `--json` was omitted, or the process crashed. Show the stderr text.                                                                                                                                |

Tip: run `material-colors-grid validate --input doc.json` first when a
document is hand-edited, and `material-colors-grid schema` to see the exact
document shape.

[Back to README](../README.md)
