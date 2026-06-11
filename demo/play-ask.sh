#!/usr/bin/env bash
# Canned, time-paced playback of a real `devlore ask --dev` answer (shapes faithful
# to the actual tool; timing compressed). Rendered by demo/receipts.tape.
B=$'\033[1m'; G=$'\033[32m'; C=$'\033[36m'; Y=$'\033[33m'; D=$'\033[2m'; R=$'\033[0m'
s() { sleep "$1"; }

echo "${D}reading knowledge/index.md → selecting articles → synthesizing…${R}"; s 1.6
echo
echo "${B}The retry path has three known footguns,${R} all discovered the hard way:"
s 0.9
echo
echo "1. ${B}Idempotency keys must include a body-content hash${R} — a static key caches"
echo "   FAILED attempts for ~24h, silently blocking corrected retries"
echo "   (${C}[[concepts/webhook-idempotency-discipline]]${R})."; s 1.1
echo
echo "2. ${B}The backoff window is wall-clock, not monotonic${R} — laptops sleeping mid-retry"
echo "   double-fire on wake; the dedup guard exists for exactly this"
echo "   (${C}[[concepts/retry-backoff-semantics]]${R})."; s 1.1
echo
echo "3. ${B}Provider timeouts ≠ failures${R} — treating a 504 as terminal caused the"
echo "   duplicate-charge incident; 504s re-queue, 4xx dead-letter"
echo "   (${C}[[concepts/provider-timeout-policy]]${R}, superseded the 2026-03 design)."; s 1.6
echo
echo "## Code pointers (resolved live — experimental)"; s 0.5
echo
echo "- ${C}makeIdempotencyKey${R} → ${G}src/webhooks/retry.ts:142${R} — body-hash included ✓"; s 0.5
echo "- ${C}RETRY_BACKOFF_MS${R} → ${G}src/webhooks/retry.ts:31${R}"; s 0.5
echo "- ${C}classifyProviderError${R} → ${G}src/webhooks/errors.ts:77${R} — 504 → requeue branch"; s 0.9
echo
echo "${Y}⚠ Caution:${R} ${C}[[concepts/retry-backoff-semantics]]${R} is ${Y}needs-reverification${R} —"
echo "${D}src/webhooks/retry.ts changed after that article's vintage. Claims verified against${R}"
echo "${D}the CURRENT tree above; run \`devlore verify\` for the full gate.${R}"
s 2.4
