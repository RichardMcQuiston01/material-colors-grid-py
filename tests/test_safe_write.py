"""Output safety for save_image, image_to_bytes and save_json_file."""

import os
import stat
from pathlib import Path

import pytest
from PIL import Image

from material_colors_grid import (
    Err,
    Ok,
    create_default_document,
    document_to_json,
    image_to_bytes,
    load_document_file,
    save_image,
    save_json_file,
)

needs_symlink = pytest.mark.skipif(
    os.name == "nt", reason="symlinks need privileges on Windows"
)


def small_image() -> Image.Image:
    return Image.new("RGB", (8, 8), (10, 20, 30))


@needs_symlink
def test_save_image_refuses_symlink_and_keeps_victim(tmp_path: Path) -> None:
    victim = tmp_path / "victim.txt"
    victim.write_text("precious", encoding="utf-8")
    link = tmp_path / "out.png"
    link.symlink_to(victim)
    result = save_image(small_image(), link)
    assert isinstance(result, Err)
    assert str(link) in result.error and "symlink" in result.error
    assert victim.read_text(encoding="utf-8") == "precious"


@needs_symlink
def test_save_image_refuses_dangling_symlink(tmp_path: Path) -> None:
    link = tmp_path / "out.png"
    link.symlink_to(tmp_path / "does-not-exist")
    result = save_image(small_image(), link)
    assert isinstance(result, Err) and "symlink" in result.error
    assert not (tmp_path / "does-not-exist").exists()


def test_save_image_refuses_directory(tmp_path: Path) -> None:
    target = tmp_path / "out.png"
    target.mkdir()
    result = save_image(small_image(), target)
    assert isinstance(result, Err)
    assert str(target) in result.error and "directory" in result.error


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs named pipes")
def test_save_image_refuses_fifo_without_hanging(tmp_path: Path) -> None:
    target = tmp_path / "out.png"
    os.mkfifo(target)
    result = save_image(small_image(), target)  # would block if it opened the FIFO
    assert isinstance(result, Err) and "FIFO" in result.error


@pytest.mark.skipif(not Path("/dev/null").exists(), reason="needs /dev/null")
def test_save_image_refuses_devices() -> None:
    result = save_image(small_image(), "/dev/null", "png")
    assert isinstance(result, Err) and "/dev/null" in result.error
    assert "not a regular file" in result.error


def test_save_image_missing_directory_leaves_nothing(tmp_path: Path) -> None:
    result = save_image(small_image(), tmp_path / "missing" / "out.png")
    assert isinstance(result, Err)
    assert list(tmp_path.iterdir()) == []


def test_save_image_replaces_existing_file_and_keeps_its_mode(
    tmp_path: Path,
) -> None:
    target = tmp_path / "out.png"
    target.write_bytes(b"old")
    if os.name != "nt":
        target.chmod(0o640)
    result = save_image(small_image(), target)
    assert result == Ok(target)
    assert target.read_bytes().startswith(b"\x89PNG")
    if os.name != "nt":
        assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert [p.name for p in tmp_path.iterdir()] == ["out.png"]


def test_save_image_encoding_failure_leaves_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "out.png"
    target.write_bytes(b"old")
    result = save_image(small_image(), target, quality=0)
    assert isinstance(result, Err)
    assert target.read_bytes() == b"old"
    assert [p.name for p in tmp_path.iterdir()] == ["out.png"]


def test_save_image_failed_replace_removes_temp_file(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "x.png").mkdir()  # an empty directory cannot be a replace target
    result = save_image(small_image(), out_dir / "x.png")
    assert isinstance(result, Err)
    assert [p.name for p in out_dir.iterdir()] == ["x.png"]


def test_gif_wider_than_65535_is_err_not_exception() -> None:
    result = image_to_bytes(Image.new("RGB", (65536, 1)), "gif")
    assert isinstance(result, Err)
    assert "gif" in result.error and "65536x1" in result.error


def test_jpg_too_large_is_err_not_exception() -> None:
    result = image_to_bytes(Image.new("RGB", (65536, 1)), "jpg")
    assert isinstance(result, Err)
    assert "jpg" in result.error and "65536x1" in result.error


@needs_symlink
def test_save_json_file_refuses_symlink(tmp_path: Path) -> None:
    victim = tmp_path / "victim.json"
    victim.write_text("keep", encoding="utf-8")
    link = tmp_path / "doc.json"
    link.symlink_to(victim)
    result = save_json_file(link, "{}")
    assert isinstance(result, Err) and str(link) in result.error
    assert victim.read_text(encoding="utf-8") == "keep"


def test_save_json_file_is_atomic_and_clean(tmp_path: Path) -> None:
    target = tmp_path / "doc.json"
    assert save_json_file(target, "{}") == Ok(target)
    assert target.read_text(encoding="utf-8") == "{}"
    assert [p.name for p in tmp_path.iterdir()] == ["doc.json"]


def test_load_document_file_accepts_bom(tmp_path: Path) -> None:
    document = create_default_document()
    target = tmp_path / "bom.json"
    target.write_bytes(b"\xef\xbb\xbf" + document_to_json(document).encode())
    assert load_document_file(target) == Ok(document)
