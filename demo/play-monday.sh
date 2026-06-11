#!/usr/bin/env bash
# Canned `devlore ask` beat for the hero GIF (see demo/hero.tape).
B=$'\033[1m'; C=$'\033[36m'; D=$'\033[2m'; R=$'\033[0m'
echo "${D}reading knowledge/index.md → 3 articles → synthesizing…${R}"; sleep 1.4
echo
echo "${B}Because the Friday settlement batch holds weekend failures${R} in a"
echo "deferred queue — Monday 06:00 drains it AND the regular retry fires."
echo "The double-retry was kept ${B}deliberately${R} after the 2026-04 incident"
echo "(${C}[[concepts/settlement-batch-timing]]${R}, ${C}[[concepts/retry-backoff-semantics]]${R})."
sleep 3.2
