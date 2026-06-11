"""
SessionEnd hook - captures conversation transcript for memory extraction.

When a Claude Code session ends, this hook reads the transcript path from
stdin, extracts conversation context, and spawns flush.py as a background
process to extract knowledge into the daily log.

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

# Recursion guard: if we were spawned by flush.py (which calls Agent SDK,
# which runs Claude Code, which would fire this hook again), exit immediately.
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

ROOT = Path(__file__).resolve().parent.parent
DAILY_DIR = ROOT / "daily"
SCRIPTS_DIR = ROOT / "scripts"
STATE_DIR = SCRIPTS_DIR

logging.basicConfig(
    filename=str(SCRIPTS_DIR / "flush.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [hook] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_LIMITS = get_limits()       # from scripts/capture-config (editable, no code change)
MAX_TURNS = _LIMITS["max_turns"]        # fallback tail when no save marker yet
MIN_TURNS_TO_FLUSH = 1                   # SessionEnd captures the full delta (no char cap)


def parse_iso(ts):
    """Parse a transcript ISO timestamp -> naive local datetime (or None)."""
    if not ts or not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
    except Exception:
        return None


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
    Returns (context, turn_count, high_water_iso, deferred=0).

    SessionEnd is the LAST chance to capture, so unlike PreCompact it does NOT
    apply the per-flush char cap — flush.py chunks the full delta (bounded by
    MAX_CHUNKS). Nothing is deferred from a session's final flush."""
    last_ts = load_last_ts(session_id)
    turns: list[tuple] = []  # (timestamp_or_None, text)

    with open(transcript_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg = entry.get("message", {})
            if isinstance(msg, dict):
                role = msg.get("role", "")
                content = msg.get("content", "")
            else:
                role = entry.get("role", "")
                content = entry.get("content", "")

            if role not in ("user", "assistant"):
                continue

            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        text_parts.append(block)
                content = "\n".join(text_parts)

            if isinstance(content, str) and content.strip():
                label = "User" if role == "user" else "Assistant"
                turns.append((parse_iso(entry.get("timestamp")), f"**{label}:** {content.strip()}\n"))

    truncated = 0
    if last_ts is not None:
        # Include turns newer than the last save; a turn with no timestamp is
        # kept (conservative — better a rare re-capture than a silent loss).
        delta = [t for t in turns if t[0] is None or t[0] > last_ts]
    else:
        # FIRST flush of this session: only the most recent window is captured,
        # and the marker this flush writes will hide the EARLIER turns from the
        # batch backfill. Report the truncation so flush.py leaves a visible
        # recovery breadcrumb in the daily (devlore smoke finding #8 — a
        # session-end flush raced the backfill and silently hid a huge history).
        delta = turns[-MAX_TURNS:]
        truncated = max(0, len(turns) - MAX_TURNS)

    high_water = None
    for ts, _ in delta:
        if ts and (high_water is None or ts > high_water):
            high_water = ts
    high_water_iso = high_water.isoformat() if high_water else ""

    # No per-flush char cap at session end: capture the full delta (flush.py
    # chunks it, bounded by MAX_CHUNKS) so the final flush loses nothing.
    context = "\n".join(text for _, text in delta)

    return context, len(delta), high_water_iso, truncated


def main() -> None:
    # Read hook input from stdin
    # Claude Code on Windows may pass paths with unescaped backslashes
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
    source = hook_input.get("source", "unknown")
    transcript_path_str = hook_input.get("transcript_path", "")
    cwd = hook_input.get("cwd", "")

    logging.info("SessionEnd fired: session=%s source=%s cwd=%s", session_id, source, cwd)

    # Opt-in gate: only capture sessions whose cwd is listed in scripts/capture-roots.
    if not should_capture(cwd):
        logging.info("SKIP: cwd not opted-in for capture: %s", cwd)
        return

    if not transcript_path_str or not isinstance(transcript_path_str, str):
        logging.info("SKIP: no transcript path")
        return

    transcript_path = Path(transcript_path_str)
    if not transcript_path.exists():
        logging.info("SKIP: transcript missing: %s", transcript_path_str)
        return

    # Extract conversation context in the hook (delta since last save)
    try:
        context, turn_count, high_water_iso, truncated = extract_conversation_context(transcript_path, session_id)
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
    context_file = STATE_DIR / f"session-flush-{session_id}-{timestamp}.md"
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
        "0",                 # deferred (PreCompact cap-deferral; none at session end)
        str(truncated),      # first-flush truncation — earlier turns hidden from backfill
    ]

    # On Windows, use CREATE_NO_WINDOW to avoid flash console window.
    # Do NOT use DETACHED_PROCESS — it breaks the Agent SDK's subprocess I/O.
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
