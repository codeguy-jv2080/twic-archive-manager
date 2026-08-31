"""One entry point for the desktop window and headless scheduled commands."""

from __future__ import annotations

import sys
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments:
        from .cli import main as cli_main

        return cli_main(arguments)

    from .main import run_desktop_app

    return run_desktop_app()


if __name__ == "__main__":
    raise SystemExit(main())
