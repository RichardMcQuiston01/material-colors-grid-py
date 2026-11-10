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
