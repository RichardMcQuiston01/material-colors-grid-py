"""Tests for scripts/verify_release.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "verify_release.py"


def load_script() -> ModuleType:
    """Import the release script by path (it is not part of the package)."""
    spec = importlib.util.spec_from_file_location("verify_release", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_release"] = module
    spec.loader.exec_module(module)
    return module


script = load_script()
parse_tag_version: Callable[[str], tuple[str | None, list[str]]] = (
    script.parse_tag_version
)
check_tag_matches_version: Callable[[str, str], list[str]] = (
    script.check_tag_matches_version
)
changelog_has_version: Callable[[str, str], bool] = script.changelog_has_version
check_changelog: Callable[[Path, str], list[str]] = script.check_changelog
read_project_version: Callable[[Path], tuple[str | None, list[str]]] = (
    script.read_project_version
)
check_ancestor_of_main: Callable[[str, str], list[str]] = script.check_ancestor_of_main
main: Callable[[list[str]], int] = script.main

requires_tomllib = pytest.mark.skipif(
    sys.version_info < (3, 11), reason="tomllib needs Python 3.11+"
)


@pytest.mark.parametrize("tag", ["v1.2.3", "v0.0.1", "v10.20.30"])
def test_parse_tag_version_accepts_release_tags(tag: str) -> None:
    version, problems = parse_tag_version(tag)
    assert version == tag[1:]
    assert problems == []


@pytest.mark.parametrize("tag", ["1.2.3", "v1.2", "v1.2.3-rc1", "v1.2.3.4", "vx.y.z"])
def test_parse_tag_version_rejects_other_tags(tag: str) -> None:
    version, problems = parse_tag_version(tag)
    assert version is None
    assert tag in problems[0]


def test_check_tag_matches_version_names_both_values() -> None:
    assert check_tag_matches_version("1.0.0", "1.0.0") == []
    problems = check_tag_matches_version("1.0.1", "1.0.0")
    assert '"1.0.1"' in problems[0]
    assert '"1.0.0"' in problems[0]


@pytest.mark.parametrize(
    "heading",
    ["## 1.2.3", "## [1.2.3] - 2026-01-01", "### v1.2.3", "# 1.2.3 (2026-01-01)"],
)
def test_changelog_has_version_accepts_headings(heading: str) -> None:
    assert changelog_has_version(f"# CHANGELOG\n\n{heading}\n- item\n", "1.2.3")


@pytest.mark.parametrize(
    "text",
    ["## 1.2.30\n", "## 11.2.3\n", "1.2.3 mentioned in prose\n", "- 1.2.3\n", ""],
)
def test_changelog_has_version_rejects_non_headings(text: str) -> None:
    assert not changelog_has_version(text, "1.2.3")


def test_check_changelog_reports_missing_version(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("## [0.0.1]\n", encoding="utf-8")
    assert check_changelog(changelog, "0.0.1") == []
    problems = check_changelog(changelog, "0.0.2")
    assert '"0.0.2"' in problems[0]
    assert str(changelog) in problems[0]


def test_check_changelog_reports_unreadable_file(tmp_path: Path) -> None:
    problems = check_changelog(tmp_path / "missing.md", "1.0.0")
    assert "Cannot read" in problems[0]


@requires_tomllib
def test_read_project_version(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "x"\nversion = "1.2.3"\n', encoding="utf-8")
    assert read_project_version(pyproject) == ("1.2.3", [])


@requires_tomllib
def test_read_project_version_failures(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'x'\n", encoding="utf-8")
    assert "no string [project].version" in read_project_version(pyproject)[1][0]
    pyproject.write_text("not = = toml", encoding="utf-8")
    assert "not valid TOML" in read_project_version(pyproject)[1][0]
    assert "Cannot read" in read_project_version(tmp_path / "nope.toml")[1][0]


def run_git(repo: Path, *args: str) -> None:
    """Run a git command in a scratch repository."""
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    run_git(tmp_path, "init", "-b", "main")
    run_git(tmp_path, "commit", "--allow-empty", "-m", "on main")
    run_git(tmp_path, "tag", "v1.0.0")
    run_git(tmp_path, "checkout", "-b", "side")
    run_git(tmp_path, "commit", "--allow-empty", "-m", "off main")
    run_git(tmp_path, "tag", "-a", "v2.0.0", "-m", "annotated")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_ancestor_check_accepts_tag_on_main(repo: Path) -> None:
    assert check_ancestor_of_main("v1.0.0", "main") == []


def test_ancestor_check_rejects_tag_off_main(repo: Path) -> None:
    problems = check_ancestor_of_main("v2.0.0", "main")
    assert 'Tag "v2.0.0"' in problems[0]
    assert "not an ancestor of main" in problems[0]


def test_ancestor_check_reports_unknown_tag(repo: Path) -> None:
    assert "Cannot resolve tag" in check_ancestor_of_main("v9.9.9", "main")[0]


@requires_tomllib
def test_main_passes_and_fails(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (repo / "pyproject.toml").write_text(
        '[project]\nversion = "1.0.0"\n', encoding="utf-8"
    )
    (repo / "CHANGELOG.md").write_text("## [1.0.0] - 2026-01-01\n", encoding="utf-8")
    assert main(["--tag", "v1.0.0", "--main-ref", "main"]) == 0
    assert main(["--tag", "v2.0.0", "--main-ref", "main"]) == 1
    error_output = capsys.readouterr().err
    assert "not an ancestor of main" in error_output
    assert 'does not match pyproject.toml version "1.0.0"' in error_output
    assert 'no heading for version "2.0.0"' in error_output
