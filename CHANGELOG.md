# CHANGELOG

## Unreleased

### Changed

- Document JSON now matches the TypeScript package exactly (camelCase keys,
  `subCategories` one level deep, `fonts`, `border`, `header`/`footer` with
  `background` and `font`, watermark `dataUrl`). Python models mirror it in
  snake_case. Defaults match the TS defaults (5 cards per row, `#f7f7f7`
  card background, default category id `default`).

### Added

- `SubCategory`, `FontStyle`, `FontsStyle`, `CardFontStyle`, `BorderStyle`,
  `Orientation`, `create_default_style`, `css_size_to_px`.
