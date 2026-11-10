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
