"""Shared JSONL transcript parsing for assistant session stores.

devlore consumes Claude Code transcripts and Codex transcripts. The two formats
carry the same useful signal (user/assistant text turns) with different JSON
shapes, so keep the normalizer in one place and have hooks/backfill share it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class TranscriptTurn:
    role: str
    text: str
    timestamp: datetime | None
    timestamp_iso: str


def parse_iso(ts: str | None) -> datetime | None:
    """Parse an ISO timestamp to naive local time, or None if unavailable."""
    if not ts or not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
    except Exception:
        return None


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            block_type = block.get("type")
            if block_type in {"text", "input_text", "output_text"}:
                parts.append(str(block.get("text", "")))
    return "\n".join(p for p in parts if p)


def _looks_like_codex_runtime_context(role: str, text: str) -> bool:
    """Skip synthetic Codex messages that are not user-authored conversation."""
    stripped = text.strip()
    if role == "user" and stripped.startswith("<environment_context>"):
        return True
    return False


def _claude_turn(entry: dict[str, Any]) -> TranscriptTurn | None:
    msg = entry.get("message", {})
    if isinstance(msg, dict):
        role = msg.get("role", "")
        content = msg.get("content", "")
    else:
        role = entry.get("role", "")
        content = entry.get("content", "")
    if role not in {"user", "assistant"}:
        return None
    text = _text_from_content(content).strip()
    if not text or _looks_like_codex_runtime_context(role, text):
        return None
    ts = entry.get("timestamp")
    return TranscriptTurn(role=role, text=text, timestamp=parse_iso(ts), timestamp_iso=ts or "")


def _codex_turn(entry: dict[str, Any]) -> TranscriptTurn | None:
    if entry.get("type") != "response_item":
        return None
    payload = entry.get("payload")
    if not isinstance(payload, dict) or payload.get("type") != "message":
        return None
    role = payload.get("role", "")
    if role not in {"user", "assistant"}:
        return None
    text = _text_from_content(payload.get("content", "")).strip()
    if not text or _looks_like_codex_runtime_context(role, text):
        return None
    ts = entry.get("timestamp")
    return TranscriptTurn(role=role, text=text, timestamp=parse_iso(ts), timestamp_iso=ts or "")


def iter_transcript_turns(transcript_path: Path) -> Iterable[TranscriptTurn]:
    """Yield normalized user/assistant text turns from Claude or Codex JSONL."""
    with open(transcript_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            turn = _codex_turn(entry) or _claude_turn(entry)
            if turn:
                yield turn


def transcript_metadata(transcript_path: Path) -> dict[str, Any]:
    """Return the first Codex session_meta payload, or an empty dict."""
    try:
        with open(transcript_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") == "session_meta" and isinstance(entry.get("payload"), dict):
                    return entry["payload"]
    except OSError:
        pass
    return {}


_CODEX_ROLLOUT_RE = re.compile(r"rollout-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-(.+)$")


def transcript_session_id(transcript_path: Path) -> str:
    """Stable session id for marker files, preferring Codex session metadata."""
    meta = transcript_metadata(transcript_path)
    sid = meta.get("id")
    if isinstance(sid, str) and sid:
        return sid
    match = _CODEX_ROLLOUT_RE.match(transcript_path.stem)
    if match:
        return match.group(1)
    return transcript_path.stem


def transcript_dialogue(transcript_path: Path) -> tuple[str, str, str]:
    """Return (dialogue, first_date, last_iso) for user/assistant text turns."""
    turns: list[str] = []
    first_ts = last_ts = ""
    for turn in iter_transcript_turns(transcript_path):
        if turn.timestamp_iso:
            first_ts = first_ts or turn.timestamp_iso
            last_ts = turn.timestamp_iso
        label = "User" if turn.role == "user" else "Assistant"
        turns.append(f"**{label}:** {turn.text}\n")
    if not first_ts:
        meta_ts = transcript_metadata(transcript_path).get("timestamp", "")
        if isinstance(meta_ts, str):
            first_ts = last_ts = meta_ts
    first_date = first_ts[:10] if first_ts else ""
    return "\n".join(turns), first_date, last_ts
