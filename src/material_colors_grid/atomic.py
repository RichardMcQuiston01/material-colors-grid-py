"""Safe, atomic file writing shared by the image and JSON savers.

The destination is checked first: it must not be a symlink and, when it
already exists, must be a regular file (never a directory, FIFO, socket or
device such as ``/dev/stdout`` or ``/dev/null``). The bytes are then written
to a temporary file in the destination directory (same filesystem) and moved
into place with ``os.replace``, so a failure never leaves a partial file and
the temporary file is always removed.
"""

from __future__ import annotations

import contextlib
import os
import stat
import tempfile
from pathlib import Path

from material_colors_grid.result import Err, Ok, Result

DEFAULT_FILE_MODE: int = 0o666


def _describe_file_type(mode: int) -> str:
    """Name the kind of file a ``st_mode`` describes."""
    if stat.S_ISDIR(mode):
        return "a directory"
    if stat.S_ISFIFO(mode):
        return "a FIFO (named pipe)"
    if stat.S_ISCHR(mode):
        return "a character device"
    if stat.S_ISBLK(mode):
        return "a block device"
    if stat.S_ISSOCK(mode):
        return "a socket"
    return "not a regular file"


def check_destination(destination: Path) -> Result[int | None]:
    """Check that ``destination`` is safe to replace.

    Args:
        destination: The file that is about to be written.

    Returns:
        ``Ok(mode)`` with the permission bits of an existing regular file,
        ``Ok(None)`` when it does not exist yet, or ``Err`` naming the path
        when it is a symlink, is not a regular file, or cannot be inspected.
    """
    try:
        status: os.stat_result = destination.lstat()
    except FileNotFoundError:
        return Ok(None)
    except OSError as error:
        return Err(f'Cannot inspect output "{destination}": {error}')
    if stat.S_ISLNK(status.st_mode):
        return Err(
            f'Refusing to write to "{destination}": it is a symlink '
            "(write to the real path instead)"
        )
    if not stat.S_ISREG(status.st_mode):
        return Err(
            f'Refusing to write to "{destination}": it exists and is '
            f"{_describe_file_type(status.st_mode)}, not a regular file"
        )
    return Ok(stat.S_IMODE(status.st_mode))


def _default_mode() -> int:
    """Return the permission bits a plain ``open`` would give a new file."""
    current_umask: int = os.umask(0)
    os.umask(current_umask)
    return DEFAULT_FILE_MODE & ~current_umask


def write_bytes_atomically(destination: Path, data: bytes) -> Result[Path]:
    """Write ``data`` to ``destination`` atomically and safely.

    Args:
        destination: Target file. Its directory must already exist.
        data: The bytes to write.

    Returns:
        ``Ok(destination)``, or ``Err`` naming the path and the reason (symlink,
        not a regular file, missing directory, permission denied, disk full).
        No partial file and no temporary file is left behind on failure.
    """
    checked: Result[int | None] = check_destination(destination)
    if isinstance(checked, Err):
        return checked
    mode: int = _default_mode() if checked.value is None else checked.value
    directory: Path = destination.parent
    temporary_path: str | None = None
    try:
        descriptor, temporary_path = tempfile.mkstemp(
            dir=directory, prefix=f".{destination.name}.", suffix=".tmp"
        )
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, destination)
        temporary_path = None
    except OSError as error:
        return Err(f'Could not write "{destination}": {error}')
    finally:
        if temporary_path is not None:
            with contextlib.suppress(OSError):
                os.unlink(temporary_path)
    return Ok(destination)
