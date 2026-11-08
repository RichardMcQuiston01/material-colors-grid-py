"""Command line entry point (implemented in ``feature/cli``)."""

from __future__ import annotations

import sys
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Argument list, or ``None`` to use ``sys.argv[1:]``.

    Returns:
        Process exit code: 0 success, 1 runtime failure, 2 invalid input.
    """
    arguments: list[str] = list(sys.argv[1:] if argv is None else argv)
    if "--version" in arguments:
        sys.stdout.write("0.0.1\n")
        return 0
    sys.stderr.write("material-colors-grid: CLI not implemented yet\n")
    return 1
