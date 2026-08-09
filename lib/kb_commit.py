"""Auto-commit for the knowledge base (commit strategy, 2026-06-03).

The pipeline is the writer, so the pipeline commits: every successful write
(compile / verify-attest / batch-ingest) ends with ONE atomic commit of the
repo's tracked state, message derived from what ran. Local-only by design —
no remote, no push. Manual edits ride along in the next pipeline commit.

Never fatal: a commit failure must not fail the pipeline step that called it.

Usage (programmatic):   from kb_commit import kb_commit; kb_commit("compile: …")
Usage (manual):         uv run python scripts/kb_commit.py "message"
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args],
                          capture_output=True, text=True, timeout=60)


def kb_commit(message: str) -> bool:
    """Stage everything (respecting .gitignore) and commit. Returns True if a
    commit was created, False on no-changes or any failure (never raises)."""
    try:
        if not (ROOT / ".git").exists():
            return False
        _git("add", "-A")
        if _git("diff", "--cached", "--quiet").returncode == 0:
            return False  # nothing staged
        r = _git("commit", "-m", message)
        return r.returncode == 0
    except Exception:
        return False


if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "kb: manual checkpoint"
    print("committed" if kb_commit(msg) else "no changes (or commit failed)")
