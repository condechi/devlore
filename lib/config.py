"""Path constants and configuration for the personal knowledge base."""

import shutil
from pathlib import Path
from datetime import datetime, timezone

# ── Paths ──────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
DAILY_DIR = ROOT_DIR / "daily"
KNOWLEDGE_DIR = ROOT_DIR / "knowledge"
CONCEPTS_DIR = KNOWLEDGE_DIR / "concepts"
CONNECTIONS_DIR = KNOWLEDGE_DIR / "connections"
QA_DIR = KNOWLEDGE_DIR / "qa"
MOCS_DIR = KNOWLEDGE_DIR / "mocs"
REPORTS_DIR = ROOT_DIR / "reports"
SCRIPTS_DIR = ROOT_DIR / "scripts"
HOOKS_DIR = ROOT_DIR / "hooks"
AGENTS_FILE = ROOT_DIR / "AGENTS.md"

INDEX_FILE = KNOWLEDGE_DIR / "index.md"
LOG_FILE = KNOWLEDGE_DIR / "log.md"
STATE_FILE = SCRIPTS_DIR / "state.json"

# ── Code roots (scripts/code-roots) ────────────────────────────────────
# The project code this KB documents: names of symlinks/dirs under the KB root.
# Replaces the per-script hardcoded {"crm": …, "metadata": …} maps so the
# machinery is replicable to other projects (devlore init writes this file).
CODE_ROOTS_FILE = SCRIPTS_DIR / "code-roots"


def code_repos() -> dict[str, Path]:
    """{name: absolute path} for each existing code root. Empty dict if the
    config is missing (a KB with no linked code — everything still works,
    staleness/verify just have nothing to scan)."""
    repos: dict[str, Path] = {}
    try:
        for line in CODE_ROOTS_FILE.read_text(encoding="utf-8").splitlines():
            name = line.strip()
            if not name or name.startswith("#"):
                continue
            p = ROOT_DIR / name
            if p.exists():
                repos[name] = p
    except OSError:
        pass
    return repos


# ── Timezone ───────────────────────────────────────────────────────────
TIMEZONE = "America/Mexico_City"


def now_iso() -> str:
    """Current time in ISO 8601 format."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today_iso() -> str:
    """Current date in ISO 8601 format."""
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")


# ── Agent SDK CLI resolution ───────────────────────────────────────────
# The Claude Agent SDK bundles its OWN `claude` CLI inside the installed wheel
# (`.../claude_agent_sdk/_bundled/claude`) and `_find_cli()` PREFERS it over the
# system install. That bundled binary lags the system CLI by many versions (it is
# frozen at SDK-build time) and is intermittently flaky in the SDK's streaming /
# control-protocol mode: it exits 1 immediately with "Fatal error in message
# reader: Command failed with exit code 1" and no stderr. The current system CLI
# does not have this problem. Pass the result as `ClaudeAgentOptions(cli_path=...)`
# in every SDK call (compile/flush/query) so the SDK uses the maintained system
# binary instead of its stale bundle. Returns None if no system CLI is found, in
# which case the caller omits cli_path and the SDK falls back to its own search.
def system_cli_path() -> str | None:
    """Absolute path to the system `claude` CLI, or None if not found."""
    found = shutil.which("claude")
    if found:
        return found
    fallback = Path.home() / ".local/bin/claude"
    return str(fallback) if fallback.exists() else None
