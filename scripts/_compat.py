"""Cross-platform helpers shared by the map generators.

Centralizes the two things that were OS-specific in the original scripts:
UTF-8 stdout (Windows consoles default to cp1252) and the SVG output
location (previously a cwd-relative "../svg/" that only worked when run
from inside scripts/).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def enable_utf8_stdout() -> None:
    # reconfigure() exists on the real TextIOWrapper stdout (3.7+); under
    # pytest capture or a redirected pipe it may be absent — that's fine.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass


def svg_dir() -> Path:
    out = REPO_ROOT / "svg"
    out.mkdir(parents=True, exist_ok=True)
    return out
