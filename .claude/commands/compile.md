---
description: Manually compile pending daily logs into the knowledge wiki
argument-hint: "[--all]"
allowed-tools: Bash(uv run --directory __DEVLORE_HOME__ python:*), Read
---

Run a manual compile of the knowledge base. Daily logs accumulate from conversation
flushes and `/devlore` doc ingests; this turns any pending/changed ones into wiki
articles (applying supersession). Pass `--all` to force-recompile every daily.

Optional arguments: $ARGUMENTS

Do this:

1. Run:

   `uv run --directory __DEVLORE_HOME__ python __DEVLORE_HOME__/scripts/compile.py $ARGUMENTS`

   - If it prints **"Another compile is already running"**, a background compile is
     active — tell the user and stop (it will finish on its own).
   - If it prints **"Nothing to compile"**, tell the user the wiki is already up to date.

2. Otherwise report concisely: which wiki articles were **created** / **updated** and
   any **supersede** entries (read the tail of
   `__DEVLORE_HOME__/knowledge/log.md`). Do not dump article bodies.
