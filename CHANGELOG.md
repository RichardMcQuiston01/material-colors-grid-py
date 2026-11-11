# CHANGELOG

## Unreleased

- Add the CLI: `render` (document via `--input` or simple color list via
  `--colors`; PNG/JPG/GIF; `--quality`, `--watermark`, `--header-text`,
  `--footer-text`, `--cards-per-row`), `validate`, `schema` (JSON Schema
  draft 2020-12) and `--version`. `--json` prints one JSON object on stdout.
  Exit codes: 0 success, 1 runtime/render/I-O failure, 2 invalid input or
  arguments.
- Add the Pillow renderer: `render_to_image`, `image_to_bytes`, `save_image`
  (PNG, JPG, GIF) with header/footer bands, auto font color, placeholder for
  invalid swatch colors, and caller-supplied watermark image.
- Security/hardening: reject hostile or oversized input with descriptive
  errors instead of exhausting memory or time. New limits (module
  `material_colors_grid.limits`, not exported from the package root): canvas
  width/height 8192, canvas area 50,000,000 pixels, 50 cards per row, 500
  colors, 500 categories plus sub-categories, names 100 characters, header and
  footer text 200 characters, JSON nesting 32 levels, JSON input 5,000,000
  bytes. `render_to_image` re-checks the computed canvas before allocating.
  Deeply nested JSON and integers over 4300 digits return an error rather
  than raising. Text fitting is now logarithmic and cuts text to 200
  characters first; an oversized or extreme-aspect watermark is scaled to fit
  inside the canvas. Whole-number floats (`1440.0`, `1e3`) are accepted for
  integer style fields. Color-list categories now group case-insensitively and
  ignoring surrounding whitespace.
- Add the document model (`ProjectDocument`, `Category`, `Color`, `Style`),
  defaults, normalization, validation of untrusted JSON, and JSON import and
  export helpers. Fallible functions return `Ok` or `Err`.
- Add ordering (categories, sub-categories, then colors dark to light), the
  pure layout engine, and color utilities (hex parsing, luminance, WCAG
  contrast).
- Add the simple color-list parser (`parse_color_list`,
  `color_list_to_document`) and `document_json_schema` to the public API.
- Add the release pipeline: PyPI Trusted Publishing workflow and tag, version
  and changelog verification script.
- Change (watermark): a document's `style.watermark.image_path` is now ignored
  and never opened, by the CLI and by `render_to_image`. Use
  `render --watermark IMAGE_PATH`; the CLI prints one warning on stderr when
  a document sets a non-empty `image_path`. The `--watermark` file must be a
  regular file of at most 20 MB, and Pillow's decompression-bomb warning is
  an error (exit 1).
- Harden output files: `save_image`, `save_json_file` and `render --output`
  refuse symlinks and existing non-regular destinations (directories, FIFOs,
  devices such as `/dev/stdout`) and write atomically through a temporary
  file in the destination directory, leaving no partial or temp file on
  failure. `image_to_bytes` returns `Err` instead of raising when an encoder
  fails (for example a GIF wider than 65535 pixels).
- CLI polish: a closed stdout pipe exits 1 without a traceback; UTF-8 BOM
  files and stdin are accepted; a color list given to `--input` (or a
  document given to `--colors`) gets a hint naming the other flag; argparse
  errors carry a single `material-colors-grid[ command]: error:` prefix
  (JSON `error` text has no prefix); `schema` accepts `--json`.
