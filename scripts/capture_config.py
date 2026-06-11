"""
Loader for scripts/capture-config — the central capture-sizing knobs.

Format: `key = value` lines (ints), `#` comments. Missing/invalid keys fall
back to DEFAULTS. Shared by the hooks (via hooks/capture_gate.py), flush.py,
and statusline.py so all four stay in sync from one file.
"""

from __future__ import annotations

from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent / "capture-config"

DEFAULTS = {
    "max_turns": 120,          # fallback first-flush turn window; status-line window
    "max_chars": 50000,        # hard cap on a single flush's captured text
    "chunk_chars": 45000,      # summarizer chunk size for big captures
    "compile_chunk_chars": 40000,  # max daily-log content per compile pass (entry-aligned)
    "compile_part_timeout": 300,   # seconds before a hung compile part is abandoned
}


def get_limits() -> dict:
    """Return the capture limits, falling back to DEFAULTS for anything missing."""
    limits = dict(DEFAULTS)
    try:
        for line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key in limits:
                try:
                    limits[key] = int(val.strip())
                except ValueError:
                    pass
    except OSError:
        pass
    return limits
