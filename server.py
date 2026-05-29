#!/usr/bin/env python3
"""Root server entrypoint kept for compatibility."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ivx.server import run


if __name__ == "__main__":
    raise SystemExit(run())
