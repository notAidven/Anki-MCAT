#!/usr/bin/env bash
# End-to-end smoke test for the ReadyMCAT OpenAI proxy against a running
# `wrangler dev` (start it in another terminal first: `npm run dev`).
#
# Proves, in order:
#   1) 401 when the Bearer app token is missing/wrong  (abuse gate works)
#   2) 400 when the structured input is invalid        (validation works)
#   3) 200 + a real ladder from OpenAI through the Worker (the happy path)
#
# It reads APP_TOKEN from ./.dev.vars (never printed) and NEVER prints the
# OpenAI key. Override the target with BASE_URL=... and the token with
# APP_TOKEN=... in the environment.
#
#   npm run smoke
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

BASE_URL="${BASE_URL:-http://127.0.0.1:8787}"
ROUTE="$BASE_URL/v1/ladder"

# Pull APP_TOKEN from .dev.vars unless already in the environment.
if [ -z "${APP_TOKEN:-}" ] && [ -f .dev.vars ]; then
  APP_TOKEN="$(grep -E '^APP_TOKEN=' .dev.vars | head -n1 | cut -d= -f2- | tr -d '"'"'"'' )"
fi
if [ -z "${APP_TOKEN:-}" ]; then
  echo "!! APP_TOKEN not set and not found in .dev.vars" >&2
  exit 1
fi

pass() { printf '  \033[32mPASS\033[0m %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAILED=1; }
FAILED=0

# A realistic structured payload (the shape the iOS client sends).
read -r -d '' PAYLOAD <<'JSON' || true
{
  "question": "What is the net ATP yield of glycolysis?",
  "answer": "Glycolysis invests 2 ATP in the investment phase at hexokinase and phosphofructokinase, then produces 4 ATP and 2 NADH in the payoff phase, for a net yield of 2 ATP and 2 NADH.",
  "source": "Lippincott Biochemistry — Glycolysis",
  "topic": "Biochemistry"
}
JSON

echo ">> target: $ROUTE"

echo ">> [1/3] 401 without a token"
CODE=$(curl -sS -o /dev/null -w '%{http_code}' -X POST "$ROUTE" \
  -H 'Content-Type: application/json' --data "$PAYLOAD")
[ "$CODE" = "401" ] && pass "missing token -> 401" || fail "missing token -> got $CODE (want 401)"

echo ">> [2/3] 400 on invalid input (no question)"
CODE=$(curl -sS -o /dev/null -w '%{http_code}' -X POST "$ROUTE" \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $APP_TOKEN" \
  --data '{"answer":"missing the question field"}')
[ "$CODE" = "400" ] && pass "invalid input -> 400" || fail "invalid input -> got $CODE (want 400)"

echo ">> [3/3] 200 + a real ladder (live OpenAI through the Worker)"
BODY=$(mktemp)
CODE=$(curl -sS -o "$BODY" -w '%{http_code}' -X POST "$ROUTE" \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $APP_TOKEN" \
  --data "$PAYLOAD")
if [ "$CODE" = "200" ]; then
  pass "happy path -> 200"
  echo "   --- ladder content (raw completion the iOS parser receives) ---"
  # Pretty-print the .content field if jq is available, else show the body.
  if command -v jq >/dev/null 2>&1; then
    jq -r '.content' "$BODY" | sed 's/^/   /'
  else
    sed 's/^/   /' "$BODY"
  fi
else
  fail "happy path -> got $CODE (want 200)"
  echo "   response:"; sed 's/^/   /' "$BODY"
fi
rm -f "$BODY"

echo
if [ "$FAILED" = "0" ]; then
  echo "SMOKE OK — auth, validation, and the live OpenAI leg all passed."
else
  echo "SMOKE FAILED — see above."
  exit 1
fi
