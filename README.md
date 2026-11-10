# Materials Color Grid Generator

- Author: [Richard McQuiston](mailto:richard.mcquiston@gmail.com)
- Website: [https://richardmcquiston.com/](https://richardmcquiston.com/)
- Python Registry: [https://pypi.org/user/richard.mcquiston01/](https://pypi.org/user/richard.mcquiston01/)

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/P1V529Z7ZP)

## Table of Contents

| [Overview](#overview) | [Getting Started](#getting-started) | [Buy Me a Coffee](#buy-me-a-coffee) | [License](#license) | [Copyright](#copyright) |

## Overview

Python library that renders a grid of material colors (e.g. filament colors; acrylic colors) and exports it to a JPG, GIF, or PNG.  The outputted image(s) are perfect for a product on an online store which colors are available.  The Python library can used as part of a development project, or it can also be used in Claude plugins as part of a product creation pipeline.

If you are looking for a TypeScript version for your project, this is directly inspired from my [@richardmcquiston01/material-colors-grid](https://github.com/RichardMcQuiston01/material-colors-grid) TypeScript package.

[Back to Top](#table-of-contents)

## Getting Started

### Prerequisites

- Python 3.10 or newer
- [Pillow](https://python-pillow.org/) (installed automatically)

No display or network access is needed; rendering is headless and
deterministic.

### Installation

```bash
pip install material-colors-grid
# or
uv add material-colors-grid
```

### Usage

#### Command line

```bash
material-colors-grid render --input doc.json --output grid.png
material-colors-grid render --colors colors.json --output grid.jpg --format jpg
cat doc.json | material-colors-grid render --input - --output grid.png
material-colors-grid validate --input doc.json
material-colors-grid schema
material-colors-grid --version
```

Add `--json` to get a single JSON object on stdout. Exit codes: `0` success,
`1` runtime or render failure, `2` invalid input or arguments.

#### Library

```python
from dataclasses import replace

from material_colors_grid import (
    Err,
    create_category,
    create_color,
    create_default_document,
    render_to_image,
    save_image,
)

category = create_category(
    "PLA",
    colors=[
        create_color("Matte Black", "#111111"),
        create_color("Signal Red", "#d62828"),
    ],
)
document = replace(create_default_document(), categories=(category,))

rendered = render_to_image(document)
if isinstance(rendered, Err):
    raise SystemExit(rendered.error)
saved = save_image(rendered.value, "grid.png")  # .jpg and .gif work too
if isinstance(saved, Err):
    raise SystemExit(saved.error)
```

Fallible functions return `Ok` or `Err` instead of raising; check the result
before using `.value`. See [GETTING_STARTED.md](GETTING_STARTED.md) for a
full walkthrough.

### Examples

A color list is the quickest input. Save this as `colors.json`:

```json
[
  { "name": "Matte Black", "hex": "#111111", "category": "PLA" },
  { "name": "Signal Red", "hex": "#d62828", "category": "PLA" }
]
```

```bash
material-colors-grid render --colors colors.json --output grid.png
```

### Claude Plugins

The CLI is designed for Claude Plugins, such as an Etsy plugin that builds a
grid from a listing's color options and attaches it to the listing. See
[docs/claude-plugins.md](docs/claude-plugins.md).

[Back to Top](#table-of-contents)

## Buy Me a Coffee

If this app, code, or repository has helped you or someone you know, please consider donating. I appreciate any help to offset the costs of development and/or AI Credits.

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/P1V529Z7ZP)

[Back to Top](#table-of-contents)

## License

Apache 2

[Back to Top](#table-of-contents)

## Copyright

(c)2026 Richard McQuiston. All rights reserved.

[Back to Top](#table-of-contents)
