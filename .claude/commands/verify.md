---
description: Verify the knowledge wiki against code — Tier-1 symbol gate + Tier-2 staleness
argument-hint: "[--article <slug>] [--tier3] [--no-tier2] [--json]"
allowed-tools: Bash(__DEVLORE_HOME__/scripts/devlore:*), Read
---

Run the PR D verification ladder over the compiled knowledge base. **Tier-1** extracts
each article's distinctive backtick identifiers and checks them against a full-repo symbol
index, then deterministically triages every ABSENT token (fuzzy rename, source-daily grep,
rejected-value read) — no LLM. **Tier-2** reuses the staleness scan to flag articles whose
cited code changed since their knowledge vintage. The script auto-emits a hand-off prompt
for the flagged set. Add `--tier3` to run the adversarial Sonnet refute pass on genuine
true-misses (costs money; off by default), `--article <slug>` to check one article.

Optional arguments: $ARGUMENTS

Do this:

1. Run (the per-KB launcher routes to the right KB and injects `DEVLORE_KB_ROOT`; pass any flags through verbatim):

   `__DEVLORE_HOME__/scripts/devlore verify $ARGUMENTS`

2. Report concisely: the Tier-1 confirmed ratio, the benign breakdown (RENAME /
   CORRECT-NEGATIVE), and the **true-misses** (CONVO-SOURCED / COMPILE-FABRICATED) with their
   articles. Note the Tier-2 stale-risk count. Do not dump article bodies.

3. The script prints a **HAND-OFF PROMPT** for the flagged set — the residue the machine
   can't resolve without the in-flight, uncommitted truth this session holds. If anything is
   flagged, work that prompt: for each item verify the code-level claim against the **current
   working tree** (Grep/Read across the KB's linked code roots — the symlinked repos listed
   in `scripts/code-roots`), then correct the article (state
   only the new truth, per the supersession rules) or confirm it. COMPILE-FABRICATED tokens
   are the highest-priority — a symbol absent from both code and the source daily is a likely
   hallucination.
