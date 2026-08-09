"""
Loader for scripts/capture-config — the central capture-sizing knobs.

Format: `key = value` lines (ints, plus string values for keys whose default
is a string — e.g. compile_model), `#` comments. Missing/invalid keys fall
back to DEFAULTS. Shared by the hooks (via hooks/capture_gate.py), flush.py,
and statusline.py so all four stay in sync from one file.
"""

from __future__ import annotations

from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent / "capture-config"

DEFAULTS = {
    "max_turns": 120,          # fallback first-flush turn window; status-line window;
                               #   Stop-hook safety-valve threshold (turns-since-save)
    "bootstrap_turns": 45,     # Stop hook: auto-fire the FIRST flush once a session
                               #   reaches this many turns (0 disables the bootstrap)
    "max_chars": 50000,        # hard cap on a single flush's captured text
    "chunk_chars": 45000,      # summarizer chunk size for big captures
    "compile_chunk_chars": 40000,  # max daily-log content per compile pass (entry-aligned)
    "compile_part_timeout": 900,   # seconds before a hung compile part is abandoned
                                   #   (SDK sessions log the kill as "Request
                                   #   interrupted", so keep this generous — a too-
                                   #   tight value aborts healthy parts mid-write)
    "compile_model": "sonnet",     # model the compile agent runs on. Without a pin
                                   #   the Agent SDK inherits the interactive CLI's
                                   #   default model — historically Opus/Fable, at
                                   #   several dollars per daily. "inherit" (or an
                                   #   empty value) restores that behavior.
    "query_model": "sonnet",       # model `devlore ask` runs on — same rationale
                                   #   and same "inherit" escape hatch as
                                   #   compile_model.
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
                if isinstance(limits[key], int):
                    try:
                        limits[key] = int(val.strip())
                    except ValueError:
                        pass
                else:
                    limits[key] = val.strip().strip("\"'")
    except OSError:
        pass
    return limits
