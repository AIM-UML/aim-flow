#!/usr/bin/env python3
"""Convenience launcher — run AIM Flow (Linux) from the repo root.

Usage:
    .venv/bin/python launch_aim_flow_linux.py
or simply:
    ./run_linux.sh
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from aim_flow.__main__ import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
