#!/usr/bin/env python3
"""Common app entry for dashboard server.

This is a stable entrypoint alias to server.py for users who expect app.py.
"""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> int:
    target = Path(__file__).resolve().with_name("server.py")
    runpy.run_path(str(target), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
