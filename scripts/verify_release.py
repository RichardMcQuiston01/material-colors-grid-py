"""Verify that a release tag is safe to publish.

Used by ``.github/workflows/publish.yml``. Every check returns a list of
human-readable problems; an empty list means the check passed. Requires
Python 3.11+ to read ``pyproject.toml`` (``tomllib``).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

TAG_PATTERN = re.compile(r"^v(?P<version>[0-9]+\.[0-9]+\.[0-9]+)$")


def parse_tag_version(tag: str) -> tuple[str | None, list[str]]:
    """Extract the version from a ``vX.Y.Z`` release tag.

    Args:
        tag: The tag name, for example ``v1.2.3``.

    Returns:
        ``(version, [])`` on success, or ``(None, problems)`` when the tag
        does not match ``v<major>.<minor>.<patch>``.
    """
    match = TAG_PATTERN.match(tag)
    if match is None:
        return None, [
            f'Tag "{tag}" does not match the release format vX.Y.Z (for example v1.2.3)'
        ]
    return match.group("version"), []


def parse_toml(
    raw_bytes: bytes, source: Path
) -> tuple[dict[str, object] | None, list[str]]:
    """Parse TOML bytes (Python 3.11+ only, via ``tomllib``).

    Args:
        raw_bytes: The file contents.
        source: Path used in error messages.

    Returns:
        ``(data, [])`` on success, or ``(None, problems)`` on invalid TOML or
        when running on Python older than 3.11.
    """
    if sys.version_info >= (3, 11):
        import tomllib

        try:
            return tomllib.loads(raw_bytes.decode("utf-8")), []
        except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
            return None, [f'"{source}" is not valid TOML: {error}']
    return None, ["Reading pyproject.toml requires Python 3.11 or newer"]


def read_project_version(pyproject_path: Path) -> tuple[str | None, list[str]]:
    """Read ``[project].version`` from a ``pyproject.toml`` file.

    Args:
        pyproject_path: Path to the ``pyproject.toml`` file.

    Returns:
        ``(version, [])`` on success, or ``(None, problems)`` when the file
        is missing, is not valid TOML, or has no string ``project.version``.
    """
    try:
        raw_bytes = pyproject_path.read_bytes()
    except OSError as error:
        return None, [f'Cannot read "{pyproject_path}": {error}']
    data, parse_problems = parse_toml(raw_bytes, pyproject_path)
    if data is None:
        return None, parse_problems
    project = data.get("project")
    version = project.get("version") if isinstance(project, dict) else None
    if not isinstance(version, str):
        return None, [f'"{pyproject_path}" has no string [project].version']
    return version, []


def check_tag_matches_version(tag_version: str, project_version: str) -> list[str]:
    """Check that the tag version equals the ``pyproject.toml`` version.

    Args:
        tag_version: Version taken from the tag, without the leading ``v``.
        project_version: Version declared in ``pyproject.toml``.

    Returns:
        A list with one problem naming both values when they differ.
    """
    if tag_version == project_version:
        return []
    return [
        f'Tag version "{tag_version}" does not match pyproject.toml '
        f'version "{project_version}"'
    ]


def changelog_has_version(changelog_text: str, version: str) -> bool:
    """Tell whether a changelog has a heading for a version.

    Accepts headings such as ``## 1.2.3``, ``## [1.2.3] - 2026-01-01`` and
    ``## v1.2.3``. ``## 1.2.30`` does not count as ``1.2.3``.

    Args:
        changelog_text: Full text of ``CHANGELOG.md``.
        version: Version without a leading ``v``.

    Returns:
        True when a level 1-6 Markdown heading names the version.
    """
    pattern = re.compile(
        rf"^#{{1,6}}[ \t]+\[?v?{re.escape(version)}\]?(?![0-9A-Za-z.])",
        re.MULTILINE,
    )
    return pattern.search(changelog_text) is not None


def check_changelog(changelog_path: Path, version: str) -> list[str]:
    """Check that ``CHANGELOG.md`` has a heading for the version.

    Args:
        changelog_path: Path to the changelog file.
        version: Version without a leading ``v``.

    Returns:
        A list of problems; empty when the heading exists.
    """
    try:
        changelog_text = changelog_path.read_text(encoding="utf-8")
    except OSError as error:
        return [f'Cannot read "{changelog_path}": {error}']
    if changelog_has_version(changelog_text, version):
        return []
    return [
        f'"{changelog_path}" has no heading for version "{version}" '
        f'(expected a heading such as "## [{version}] - YYYY-MM-DD")'
    ]


def check_ancestor_of_main(tag: str, main_ref: str) -> list[str]:
    """Check that the tagged commit is an ancestor of the main branch.

    Args:
        tag: The tag name.
        main_ref: Ref of the main branch, for example ``origin/main``.

    Returns:
        A list of problems; empty when the tag commit is reachable from
        ``main_ref``.
    """
    resolved = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if resolved.returncode != 0:
        return [f'Cannot resolve tag "{tag}" to a commit: {resolved.stderr.strip()}']
    commit = resolved.stdout.strip()
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, main_ref],
        capture_output=True,
        text=True,
        check=False,
    )
    if ancestry.returncode == 0:
        return []
    if ancestry.returncode == 1:
        return [
            f'Tag "{tag}" points at commit {commit}, which is not an ancestor '
            f"of {main_ref}; merge it to main before tagging"
        ]
    return [
        f'Cannot compare commit {commit} with "{main_ref}": {ancestry.stderr.strip()}'
    ]


def verify_release(
    tag: str,
    pyproject_path: Path,
    changelog_path: Path,
    main_ref: str,
) -> list[str]:
    """Run every release check and collect all problems.

    Args:
        tag: The pushed tag name.
        pyproject_path: Path to ``pyproject.toml``.
        changelog_path: Path to ``CHANGELOG.md``.
        main_ref: Ref of the main branch, for example ``origin/main``.

    Returns:
        All problems found; an empty list means the release may proceed.
    """
    tag_version, problems = parse_tag_version(tag)
    if tag_version is None:
        return problems
    problems.extend(check_ancestor_of_main(tag, main_ref))
    project_version, version_problems = read_project_version(pyproject_path)
    problems.extend(version_problems)
    if project_version is not None:
        problems.extend(check_tag_matches_version(tag_version, project_version))
    problems.extend(check_changelog(changelog_path, tag_version))
    return problems


def main(argv: list[str] | None = None) -> int:
    """Run the release verification from the command line.

    Args:
        argv: Arguments, defaulting to ``sys.argv[1:]``.

    Returns:
        0 when all checks pass, 1 when any check fails.
    """
    parser = argparse.ArgumentParser(description="Verify a release tag.")
    parser.add_argument("--tag", required=True, help="Tag name, e.g. v1.2.3")
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    parser.add_argument("--changelog", type=Path, default=Path("CHANGELOG.md"))
    parser.add_argument("--main-ref", default="origin/main")
    args = parser.parse_args(argv)
    problems = verify_release(args.tag, args.pyproject, args.changelog, args.main_ref)
    for problem in problems:
        print(f"::error::{problem}", file=sys.stderr)
    if problems:
        print(
            f"Release verification failed with {len(problems)} problem(s).",
            file=sys.stderr,
        )
        return 1
    print(f"Release verification passed for {args.tag}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
