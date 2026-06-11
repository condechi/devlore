#!/usr/bin/env bash
# Canned, time-paced playback of a real `devlore add .` run (output shapes are
# faithful to the actual tool; timing compressed for the demo GIF). Rendered by
# demo/hero.tape — see demo/README.md.
B=$'\033[1m'; G=$'\033[32m'; C=$'\033[36m'; Y=$'\033[33m'; D=$'\033[2m'; R=$'\033[0m'
s() { sleep "$1"; }

echo "Adding /Users/dev/code/acme-billing to the knowledge base at /Users/dev/devlore"
echo; s 0.6
echo "  ${G}✓${R} symlink: acme-billing → /Users/dev/code/acme-billing"; s 0.35
echo "  ${G}✓${R} capture opt-in (sessions in this codebase flow into the KB)"; s 0.35
echo "  ${G}✓${R} code root registered (staleness + symbol verification will scan it)"; s 0.35
echo "  ${G}✓${R} Claude Code hooks in acme-billing/.claude/settings.local.json: registered SessionStart, PreCompact, SessionEnd"
s 1.0
echo
echo "Looking for ${B}PAST${R} Claude Code conversations to distill…"; s 1.2
echo
echo "PLAN — 14 conversation(s), oldest first:"
echo
echo "sid        date        project          size chunks model    est. \$"
s 0.3
rows=(
"a3f81c20   2026-04-02  acme-billing     0.4M      2 sonnet     6.40"
"7c29be11   2026-04-09  acme-billing     1.1M      5 sonnet     7.00"
"f0d4a955   2026-04-15  acme-billing     0.2M      1 haiku      6.03"
"2b8e67dd   2026-04-23  acme-billing     0.8M      4 sonnet     6.80"
"91c5f3a8   2026-05-02  acme-billing     1.6M      7 sonnet     7.40"
)
for r in "${rows[@]}"; do echo "$r"; s 0.18; done
echo "${D}…and 9 more${R}"; s 0.6
echo
echo "Estimated total: \$19.80  ${D}(compile-dominated; a CEILING — parts are cheaper while the wiki is small)${R}"
s 1.6
printf "Run the backfill now? [Y/n] "; s 1.4; echo "y"; s 0.5
echo
echo "[1/14] a3f81c20 (2026-04-02, sonnet, 2 chunk(s))"; s 0.3
echo "    distill chunk 1/2 (sonnet)…"; s 0.5
echo "    distill chunk 2/2 (sonnet)…"; s 0.5
echo "  compiling (2 entries, 9,214 chars)…"; s 0.7
echo "  ${G}✓${R} a3f81c20  ingested   \$1.92   ${D}→ 4 articles created${R}"; s 0.4
echo "${D}[2/14] … [14/14]  (12 ingested, 2 empty — nothing worth saving)${R}"; s 1.2
echo
echo "  Stamped 31 article(s) with valid_as_of/code_baseline."; s 0.35
echo "  Rebuilt index.md from frontmatter (31 articles)."; s 0.35
echo "  Committed."; s 0.9
echo
echo "════════════════════════════════════════════════════════════"
echo "  Knowledge base: ${B}31 article(s)${R}  ${G}(+31 from this run)${R}"
echo "  Catalog:        knowledge/index.md   ${D}(9 subsystems)${R}"
echo "  History:        knowledge/log.md + git log (auto-committed)"
echo "════════════════════════════════════════════════════════════"
s 2.2
