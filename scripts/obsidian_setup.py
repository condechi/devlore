"""devlore obsidian — add or refresh the OPTIONAL Obsidian layer in this KB.

Installs the devlore side-panel plugin + vault config into ``<KB>/.obsidian`` so you
can open the knowledge base as an Obsidian vault and drive ingest / compile / ask /
verify / status from the command palette, ribbon, and right-click menu. Idempotent —
safe to re-run to pull the latest plugin.

Why this exists: ``init_kb --with-obsidian`` only drops the layer in at install time.
A KB that opted *out* (the default) had no way to add it later — and its own
``.obsidian`` directory holds no plugin bytes to copy from. This command sources the
plugin from the local distribution cache (``~/.devlore/dist``, fetched the same way
``devlore update`` does), so even a never-opted-in KB can add the layer now.

Also the single source of truth for the install step: ``init_kb`` imports
``install_obsidian_layer`` rather than open-coding the copy + placeholder rewrite.

Usage:
    devlore obsidian                          # add/refresh into this KB
    python3 obsidian_setup.py --kb <kb-path>  # target another KB
    python3 obsidian_setup.py --from <path>   # source from a local dist/clone
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# Split literal: this file is itself materialized through init_kb's placeholder
# rewrite, which replaces an intact ``__DEVLORE_HOME__`` with the KB path. An
# un-split literal here would be corrupted on install, leaving the constant unable
# to resolve future placeholders (same in-band-sentinel class as update_kb.py).
PLACEHOLDER = "__DEVLORE" + "_HOME__"
DEFAULT_CACHE = Path.home() / ".devlore" / "dist"
REPO = "https://github.com/condechi/devlore.git"

# Vault config written for a fresh layer (only if the vault has none yet, so an
# existing user-customized app.json is never clobbered).
APP_JSON = {"defaultViewMode": "preview", "userIgnoreFilters": ["/node_modules/", ".venv/"]}


def _rewrite(text: str, source_root: Path, kb: Path) -> str:
    """Point a copied plugin file at the destination KB: resolve the dist
    placeholder AND any absolute source path (when sourcing from another KB)."""
    return text.replace(PLACEHOLDER, str(kb)).replace(str(source_root), str(kb))


def install_obsidian_layer(kb: Path, source_root: Path, *, dry: bool = False) -> int:
    """Copy every plugin under ``source_root/.obsidian/plugins`` into ``kb``,
    rewriting placeholders/paths in each .js, and seed app.json if absent.
    Returns the number of files written. Raises if the source has no plugins."""
    plugins_src = source_root / ".obsidian" / "plugins"
    plugs = [p for p in plugins_src.iterdir() if p.is_dir()] if plugins_src.is_dir() else []
    if not plugs:
        raise FileNotFoundError(
            f"no Obsidian plugin found under {plugins_src} — pass --from <dist/clone> "
            "or run `devlore update` first to populate the distribution cache.")
    n = 0
    for plug_src in plugs:
        plug_dst = kb / ".obsidian" / "plugins" / plug_src.name
        for f in sorted(plug_src.iterdir()):
            if not f.is_file():
                continue
            if not dry:
                plug_dst.mkdir(parents=True, exist_ok=True)
                try:
                    (plug_dst / f.name).write_text(
                        _rewrite(f.read_text(encoding="utf-8"), source_root, kb),
                        encoding="utf-8")
                    (plug_dst / f.name).chmod(f.stat().st_mode)
                except UnicodeDecodeError:  # binary (none expected, but be safe)
                    shutil.copy2(f, plug_dst / f.name)
            n += 1
    app = kb / ".obsidian" / "app.json"
    if not app.exists() and not dry:
        app.parent.mkdir(parents=True, exist_ok=True)
        app.write_text(json.dumps(APP_JSON, indent=2), encoding="utf-8")
    return n


def activation_steps(kb: Path) -> str:
    """One-time steps to turn the (now-installed) plugin on inside Obsidian. New
    devlore users must do this by hand — Obsidian disables third-party plugins
    until the vault author explicitly trusts and enables them."""
    return (
        "Activate it in Obsidian (one-time, required for a new vault):\n"
        f"  1. Open the KB as a vault:  Obsidian → Open folder as vault → {kb}\n"
        "  2. Settings → Community plugins → turn off Restricted mode (Trust author)\n"
        "  3. Under 'Installed plugins', toggle 'devlore' on\n"
        "  4. You now get a 🧠 status-bar item, ribbon buttons, and command-palette\n"
        "     actions (search 'devlore'): ingest, compile, ask, verify, status.\n"
        "The plugin only ever runs devlore's own scripts in this KB — never arbitrary\n"
        "commands (it is not a general command runner).")


def _best_effort_dist() -> Path | None:
    """Refresh/clone the distribution cache, tolerating offline. Unlike
    update_kb's hard-fail fetch, a failure here is soft: the caller can fall back
    to the KB's own bytes (refresh-in-place) when the network is unavailable."""
    if (DEFAULT_CACHE / ".git").exists():
        f = subprocess.run(["git", "-C", str(DEFAULT_CACHE), "fetch", "-q", "origin"],
                           capture_output=True, text=True)
        if f.returncode == 0:
            subprocess.run(["git", "-C", str(DEFAULT_CACHE), "reset", "-q", "--hard",
                            "origin/main"], capture_output=True, text=True)
        return DEFAULT_CACHE if (DEFAULT_CACHE / ".obsidian" / "plugins").is_dir() else None
    DEFAULT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["git", "clone", "-q", "--depth", "1", REPO, str(DEFAULT_CACHE)],
                       capture_output=True, text=True)
    return DEFAULT_CACHE if r.returncode == 0 \
        and (DEFAULT_CACHE / ".obsidian" / "plugins").is_dir() else None


def _resolve_source(kb: Path, from_arg: str | None) -> Path:
    """Where to copy the plugin bytes from: an explicit --from, else the latest
    distribution cache, else (offline) this KB's own already-installed layer."""
    if from_arg:
        return Path(from_arg).expanduser().resolve()
    dist = _best_effort_dist()
    if dist:
        return dist
    if (kb / ".obsidian" / "plugins").is_dir():
        print("  ⚠ distribution cache unavailable (offline?) — refreshing from this "
              "KB's existing plugin bytes instead")
        return kb
    sys.exit("error: could not reach the distribution to fetch the plugin, and this "
             "KB has none to refresh. Connect to a network, or pass --from <dist/clone>.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Add/refresh the optional Obsidian layer in a devlore KB.")
    ap.add_argument("--kb", help="KB to install into (default: the KB this script lives in).")
    ap.add_argument("--from", dest="src", help="Source dist/clone for the plugin "
                    "(default: the distribution cache, git-fetched).")
    ap.add_argument("--dry-run", action="store_true", help="Show what would happen; write nothing.")
    args = ap.parse_args()

    kb = Path(args.kb).expanduser().resolve() if args.kb \
        else Path(__file__).resolve().parent.parent
    if not (kb / "knowledge").is_dir() or not (kb / "scripts").is_dir():
        sys.exit(f"error: {kb} does not look like a devlore KB (missing knowledge/ or scripts/)")

    source = _resolve_source(kb, args.src)
    existed = (kb / ".obsidian" / "plugins").is_dir()
    n = install_obsidian_layer(kb, source, dry=args.dry_run)
    verb = "would install" if args.dry_run else ("refreshed" if existed else "installed")
    print(f"  ✓ Obsidian layer {verb}: {n} plugin file(s) → {kb}/.obsidian  (source: {source})")
    print()
    print(activation_steps(kb))


if __name__ == "__main__":
    main()
