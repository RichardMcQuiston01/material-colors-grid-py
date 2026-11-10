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
