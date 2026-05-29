#!/usr/bin/env python3
"""Root app entrypoint kept for compatibility."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
src_str = str(SRC_DIR)
if src_str in sys.path:
    sys.path.remove(src_str)
sys.path.insert(0, src_str)

from ivx.app import main


if __name__ == "__main__":
    raise SystemExit(main())
