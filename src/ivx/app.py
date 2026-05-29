#!/usr/bin/env python3
"""Common app entry for dashboard server."""

from __future__ import annotations

from .server import run


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
