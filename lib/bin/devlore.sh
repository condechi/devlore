#!/usr/bin/env bash
# devlore.sh — Obsidian-plugin shim (v0.9.27+). Was <kb>/scripts/devlore.sh.
# Routes a docs ingest + compile through the single global launcher.
exec "${HOME}/.devlore/bin/devlore" docs "$@"
