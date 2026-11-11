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
