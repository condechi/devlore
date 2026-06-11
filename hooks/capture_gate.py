"""Opt-in gate for knowledge-base capture.

A session is captured only if its working directory is listed in
scripts/capture-roots (exact match, or subtree if the line ends with "/").
This keeps capture decoupled from arbitrary project code: opting a directory
in/out is a one-line edit to that central file, no per-repo flag files.

Shared by the capture hooks (session-end.py, pre-compact.py).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAPTURE_ROOTS_FILE = ROOT / "scripts" / "capture-roots"

# Re-export the shared capture-sizing loader so the hooks can import everything
# capture-related from one place. capture_config.py lives in scripts/.
sys.path.insert(0, str(ROOT / "scripts"))
from capture_config import get_limits  # noqa: E402


def should_capture(cwd: str) -> bool:
    """True iff `cwd` matches an entry in scripts/capture-roots."""
    if not cwd:
        return False
    cwd = os.path.normpath(cwd)
    try:
        lines = CAPTURE_ROOTS_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        subtree = line.endswith("/")
        root = os.path.normpath(line)  # normpath also strips a trailing slash
        if subtree:
            if cwd == root or cwd.startswith(root + os.sep):
                return True
        elif cwd == root:
            return True
    return False
