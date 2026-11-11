# Roadmap

Development follows `.claude/skills/git-workflow/SKILL.md`: `feature/<name>`
branches off `dev`, draft PRs into `dev`, then `dev` -> `main` via PR. Merge
commits only. Releases are published to PyPI by pushing a `vX.Y.Z` tag on
`main` (owner only).

## 0.1.0

### Stage 0: Foundation (blocks everything else)

- [x] `feature/scaffold`: `pyproject.toml` (hatchling, `src/` layout, console
      script), ruff/mypy/pytest config, `models.py` and `result.py`
      interfaces, bundled open-licensed font, `ci.yml` (Python 3.10-3.13).
- [x] Replace the copied LVGL status checks in
      `.github/rulesets/main-branch.json` with this repo's CI checks.

### Stage 1: Core (parallel, no file overlap)

- [x] `feature/validation-io`: `defaults`, `normalize`, `validate`, `io`.
- [x] `feature/color-layout`: `color` (hex, luminance, WCAG contrast),
      `ordering`, `layout` (pure, no Pillow).
- [x] `feature/release-pipeline`: `publish.yml` (see below).

### Stage 2: Renderer

- [x] `feature/renderer`: Pillow rendering to PNG, JPG, GIF; watermark,
      header/footer bands, auto font color; golden-image tests.

### Stage 3: CLI and docs (parallel)

- [x] `feature/cli`: `render`, `validate`, `schema`; `--json` output; exit
      codes 0/1/2; simple color-list input.
- [x] `feature/docs-plugin-guide`: README, `GETTING_STARTED.md`, Claude
      Plugin (Etsy) usage guide.

### Stage 4: Hardening

- [x] Independent review against `CLAUDE.md`; security review (input
      handling, file paths, Pillow decompression limits).
- [x] Verify the JSON document format is documented and round-trips.
- [x] Fixes on `hotfix/<name>` branches off `dev` (`hotfix/input-limits`,
      `hotfix/untrusted-paths`, `hotfix/docs-and-ci`), all merged.

### Stage 5: Release

- [x] On `dev`: bump version, date the `CHANGELOG.md` entry (`feature/release-0.1.0`).
- [ ] PR `dev` -> `main` (merge commit), then the owner pushes `v0.1.0`.

## PyPI publish pipeline (`publish.yml`)

Trigger: push of a tag matching `v[0-9]+.[0-9]+.[0-9]+`.

1. **Verify**: tag commit is an ancestor of `origin/main`; tag equals the
   `pyproject.toml` version; `CHANGELOG.md` has an entry for it.
2. **Test**: full CI matrix.
3. **Build**: `uv build`, `twine check`, upload artifacts.
4. **Publish**: `pypa/gh-action-pypi-publish` via Trusted Publishing (OIDC),
   in the `pypi` GitHub environment with required reviewers.
5. **Release**: GitHub Release with dist files attached.
6. `workflow_dispatch` publishes to TestPyPI only (dry run).

Actions are pinned to commit SHAs; permissions are `contents: write` and
`id-token: write` only.

### Owner-only setup

- Register `material-colors-grid` as a pending trusted publisher on PyPI and
  TestPyPI (workflow `publish.yml`, environment `pypi` / `testpypi`).
- Create the `pypi` and `testpypi` GitHub environments; add a required
  reviewer to `pypi`.
- Configure the `pypi` environment with required reviewers and a deployment
  tag rule (`v*`) so only release tags can deploy.
- Pin the PyPI trusted publisher to workflow `publish.yml` and environment
  `pypi` (and the TestPyPI one to `testpypi`).
- Re-import the rulesets under `.github/rulesets/` after changing their
  `source` to this repository (they came from another repository).
- Approve the `main` ruleset change; push release tags.

## Later

- Additional output formats (WebP).
- Additional watermark and layout options.
