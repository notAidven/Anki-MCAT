#!/usr/bin/env bash
# Same-card offline sync-CONFLICT proof (sibling to verify-sync.sh).
#
# verify-sync.sh proves the two-way, DIFFERENT-card round trip end-to-end with
# the real iOS Simulator (no loss / no double-count). This script proves the
# remaining conflict case the rubric asks for: BOTH devices review the SAME card
# offline, then sync, and the merge follows the documented rule —
#
#   "the later review by timestamp wins, while the loser's review-log entry is
#    preserved so history is never silently dropped."
#
# The same-card MERGE is done by Anki's shared Rust sync engine (the identical
# code the desktop and iOS apps drive), so this drives it with two headless
# clients through a real self-hosted anki-sync-server — controllable and exact
# (one targeted card, ordered timestamps). No custom sync logic anywhere.
#
# Usage: ios/scripts/verify-sync-conflict.sh
set -euo pipefail

export PATH="$HOME/.cargo/bin:$PATH"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$ROOT/out/rust}"

HOST=127.0.0.1
PORT="${SYNC_CONFLICT_PORT:-27702}"
# The ReadyMCAT sync account both devices log in with (see verify-sync.sh).
USER="${SYNC_USER:-readymcat@example.invalid}"
PASS="${SYNC_PASS:-local-demo-${RANDOM}-${RANDOM}}"
ENDPOINT="http://$HOST:$PORT/"

WORK="$ROOT/out/sync-verify/conflict"
SERVER_BASE="$WORK/server-base"
A_BASE="$WORK/device-a"
B_BASE="$WORK/device-b"
EVID_DIR="$ROOT/ios/docs/sync"
EVID_JSON="$EVID_DIR/conflict-evidence.json"
RUN_LOG="$EVID_DIR/conflict-run.log"
BANK="$ROOT/ios/ReadyMCAT/Resources/collection.anki2"
PY="$ROOT/out/pyenv/bin/python"
export PYTHONPATH="$ROOT/out/pylib"

RED=$'\e[31m'; GRN=$'\e[32m'; YEL=$'\e[33m'; NC=$'\e[0m'
fail() { echo "${RED}FAIL:${NC} $*" >&2; exit 1; }
ok()   { echo "${GRN}OK:${NC} $*"; }
info() { echo "${YEL}>>${NC} $*"; }

[ -f "$BANK" ] || fail "bundled bank missing: $BANK (run ios/scripts/build-collection.sh)"

info "cleaning $WORK"
rm -rf "$SERVER_BASE" "$A_BASE" "$B_BASE"
mkdir -p "$SERVER_BASE" "$A_BASE" "$B_BASE" "$EVID_DIR"

SERVER_BIN="$ROOT/out/rust/release/anki-sync-server"
if [ ! -x "$SERVER_BIN" ]; then
  info "building anki-sync-server (release)"
  cargo build -p anki-sync-server --release
fi

info "starting sync server on $ENDPOINT"
SYNC_HOST="$HOST" SYNC_PORT="$PORT" SYNC_BASE="$SERVER_BASE" SYNC_USER1="$USER:$PASS" \
  RUST_LOG=anki=info "$SERVER_BIN" > "$WORK/server.log" 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do
  curl -sf -o /dev/null "http://$HOST:$PORT/health" && break || sleep 0.3
done
curl -sf -o /dev/null "http://$HOST:$PORT/health" || fail "server did not come up"
ok "server healthy (pid $SERVER_PID)"

info "running same-card conflict scenario (two headless clients)"
set +e
"$PY" "$ROOT/ios/scripts/sync_conflict.py" \
  --endpoint "$ENDPOINT" --user "$USER" --password "$PASS" \
  --a-base "$A_BASE" --b-base "$B_BASE" --bank "$BANK" \
  --evidence "$EVID_JSON" | tee "$RUN_LOG"
RC=${PIPESTATUS[0]}
set -e

echo
if [ "$RC" -eq 0 ]; then
  ok "same-card conflict merged per the winner-by-timestamp rule; loser's revlog preserved"
  echo "${GRN}==== SAME-CARD SYNC CONFLICT VERIFIED ====${NC}" | tee -a "$RUN_LOG"
  echo "evidence: $EVID_JSON"
else
  fail "same-card conflict check failed (see $RUN_LOG / $EVID_JSON)"
fi
