"""
PreCompact hook - captures conversation transcript before auto-compaction.

When the agent's context window fills up, it auto-compacts (summarizes and
discards detail). This hook fires BEFORE that happens, extracting conversation
context and spawning flush.py to extract knowledge that would otherwise
be lost to summarization.

The hook itself does NO API calls - only local file I/O for speed (<10s).
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from capture_gate import should_capture, get_limits

# Recursion guard
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
STATE_DIR = SCRIPTS_DIR
sys.path.insert(0, str(SCRIPTS_DIR))
from transcripts import iter_transcript_turns, parse_iso  # noqa: E402

logging.basicConfig(
    filename=str(SCRIPTS_DIR / "flush.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [pre-compact] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_LIMITS = get_limits()       # from scripts/capture-config (editable, no code change)
MAX_TURNS = _LIMITS["max_turns"]        # fallback tail when no save marker yet
DELTA_CAP_CHARS = _LIMITS["max_chars"]  # cap on a single captured context
MIN_TURNS_TO_FLUSH = 5

def load_last_ts(session_id: str):
    """The high-water timestamp of this session's last flush (None if never)."""
    p = SCRIPTS_DIR / f"flush-marker-{session_id}.json"
    if p.exists():
        try:
            return parse_iso(json.loads(p.read_text(encoding="utf-8")).get("last_ts"))
        except Exception:
            return None
    return None


def extract_conversation_context(transcript_path: Path, session_id: str) -> tuple[str, int, str, int]:
    """Delta capture: collect every user/assistant text turn since this session's
    last saved timestamp, so nothing between widely-spaced saves is lost. Falls
    back to the last MAX_TURNS turns when there is no marker yet (first flush).
    Returns (context, kept_turn_count, high_water_iso, deferred_turn_count)."""
    last_ts = load_last_ts(session_id)
    turns: list[tuple] = []  # (timestamp_or_None, text)

    for turn in iter_transcript_turns(transcript_path):
        label = "User" if turn.role == "user" else "Assistant"
        turns.append((turn.timestamp, f"**{label}:** {turn.text}\n"))

    if last_ts is not None:
        # Include turns newer than the last save; a turn with no timestamp is
        # kept (conservative — better a rare re-capture than a silent loss).
        delta = [t for t in turns if t[0] is None or t[0] > last_ts]
    else:
        delta = turns[-MAX_TURNS:]

    # Roll-forward cap: keep the OLDEST turns that fit in DELTA_CAP_CHARS and
    # DEFER the newer overflow to the next flush. The high-water marker advances
    # only over what we KEEP, so the deferred turns are > the marker and get
    # captured next time — nothing is lost (vs the old "keep newest, drop oldest"
    # which stranded the oldest behind the marker forever). PreCompact always has
    # a next flush (the session continues, and SessionEnd captures the tail).
    kept, total, deferred = [], 0, 0
    for i, (ts, text) in enumerate(delta):
        if kept and total + len(text) > DELTA_CAP_CHARS:
            deferred = len(delta) - i
            break
        kept.append((ts, text))
        total += len(text)

    high_water = None
    for ts, _ in kept:
        if ts and (high_water is None or ts > high_water):
            high_water = ts
    high_water_iso = high_water.isoformat() if high_water else ""

    context = "\n".join(text for _, text in kept)
    if deferred:
        logging.info(
            "Capture capped at %d chars: kept %d turn(s), DEFERRED %d to the next flush",
            DELTA_CAP_CHARS, len(kept), deferred,
        )

    return context, len(kept), high_water_iso, deferred


def main() -> None:
    # Read hook input from stdin
    try:
        raw_input = sys.stdin.read()
        try:
            hook_input: dict = json.loads(raw_input)
        except json.JSONDecodeError:
            fixed_input = re.sub(r'(?<!\\)\\(?!["\\])', r'\\\\', raw_input)
            hook_input = json.loads(fixed_input)
    except (json.JSONDecodeError, ValueError, EOFError) as e:
        logging.error("Failed to parse stdin: %s", e)
        return

    session_id = hook_input.get("session_id", "unknown")
    transcript_path_str = hook_input.get("transcript_path", "")
    cwd = hook_input.get("cwd", "")

    logging.info("PreCompact fired: session=%s cwd=%s", session_id, cwd)

    # Opt-in gate: only capture sessions whose cwd is listed in scripts/capture-roots.
    if not should_capture(cwd):
        logging.info("SKIP: cwd not opted-in for capture: %s", cwd)
        return

    # transcript_path can be empty (known Claude Code bug #13668)
    if not transcript_path_str or not isinstance(transcript_path_str, str):
        logging.info("SKIP: no transcript path")
        return

    transcript_path = Path(transcript_path_str)
    if not transcript_path.exists():
        logging.info("SKIP: transcript missing: %s", transcript_path_str)
        return

    # Extract conversation context in the hook (delta since last save)
    try:
        context, turn_count, high_water_iso, deferred = extract_conversation_context(transcript_path, session_id)
    except Exception as e:
        logging.error("Context extraction failed: %s", e)
        return

    if not context.strip():
        logging.info("SKIP: empty context")
        return

    if turn_count < MIN_TURNS_TO_FLUSH:
        logging.info("SKIP: only %d turns (min %d)", turn_count, MIN_TURNS_TO_FLUSH)
        return

    # Write context to a temp file for the background process
    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
    context_file = STATE_DIR / f"flush-context-{session_id}-{timestamp}.md"
    context_file.write_text(context, encoding="utf-8")

    # Spawn flush.py as a background process
    flush_script = SCRIPTS_DIR / "flush.py"

    cmd = [
        "uv",
        "run",
        "--directory",
        str(ROOT),
        "python",
        str(flush_script),
        str(context_file),
        session_id,
        high_water_iso or "none",
        str(deferred),
    ]

    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
        )
        logging.info("Spawned flush.py for session %s (%d turns, %d chars)", session_id, turn_count, len(context))
    except Exception as e:
        logging.error("Failed to spawn flush.py: %s", e)


if __name__ == "__main__":
    main()
