"""
Unified activity event stream for the knowledge pipeline.

Every background component (flush, compile, doc-ingest) appends a structured
event here so a single surface — the Obsidian plugin — can notify the user of
automated actions happening in the background. One append-only JSONL file; the
plugin tails it.

Event shape: {"ts","source","kind","msg","level"}
  source: flush | compile | ingest
  level:  info | warn | error   (the plugin decides what to toast vs. just show)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ACTIVITY_FILE = Path(__file__).resolve().parent / "activity.jsonl"
_MAX_BYTES = 512 * 1024  # keep the tail when it grows past this


def emit(source: str, kind: str, msg: str, level: str = "info") -> None:
    """Append one activity event. Never raises (best-effort notifier)."""
    try:
        event = {
            "ts": datetime.now(timezone.utc).astimezone().isoformat(),
            "source": source,
            "kind": kind,
            "msg": msg,
            "level": level,
        }
        if ACTIVITY_FILE.exists() and ACTIVITY_FILE.stat().st_size > _MAX_BYTES:
            tail = ACTIVITY_FILE.read_text(encoding="utf-8").splitlines()[-2000:]
            ACTIVITY_FILE.write_text("\n".join(tail) + "\n", encoding="utf-8")
        with open(ACTIVITY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except OSError:
        pass
