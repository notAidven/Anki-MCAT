#!/usr/bin/env bash
# End-to-end proof of two-way sync between the ReadyMCAT iOS app (Simulator) and
# the "desktop" (headless pylib client), through a self-hosted Anki sync server —
# all on Anki's OWN protocol. It asserts NO review is lost or double-counted by
# comparing the revlog id sets on both sides after each round trip.
#
# Flow:
#   0. clean slate + start server (empty)                 (server = loopback)
#   1. phone  sync   -> full upload   (server gets the bank)
#   2. desktop sync  -> full download (shared lineage; revlog 0 both sides)
#   3. phone   reviews 5, syncs; desktop syncs            -> both revlog == 5
#   4. desktop reviews 3, syncs; phone syncs              -> both revlog == 8
#   5. phone reviews 4 OFFLINE (unreachable endpoint), a sync attempt fails
#      gracefully, then a real sync uploads them; desktop syncs -> both == 12
#   The phone/desktop revlog id lists must be identical at the end.
#
# Usage: ios/scripts/verify-sync.sh ["iPhone 17 Pro"]
set -euo pipefail

export PATH="$HOME/.cargo/bin:$PATH"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$ROOT/out/rust}"

DEVICE="${1:-iPhone 17 Pro}"
BUNDLE_ID="com.readymcat.ios"
HOST=127.0.0.1
PORT="${SYNC_PORT:-27701}"
USER=rmcat
PASS=rmcat
ENDPOINT="http://$HOST:$PORT/"
BAD_ENDPOINT="http://$HOST:59999/"

WORK="$ROOT/out/sync-verify"
SERVER_BASE="$WORK/server-base"
DESKTOP_BASE="$WORK/desktop-base"
EVID="$WORK/evidence"
PY="$ROOT/out/pyenv/bin/python"
export PYTHONPATH="$ROOT/out/pylib"

RED=$'\e[31m'; GRN=$'\e[32m'; YEL=$'\e[33m'; NC=$'\e[0m'
fail() { echo "${RED}FAIL:${NC} $*" >&2; exit 1; }
ok()   { echo "${GRN}OK:${NC} $*"; }
info() { echo "${YEL}>>${NC} $*"; }

# ---- 0. clean slate + server ------------------------------------------------
info "cleaning $WORK"
rm -rf "$SERVER_BASE" "$DESKTOP_BASE"
mkdir -p "$SERVER_BASE" "$DESKTOP_BASE" "$EVID"

SERVER_BIN="$ROOT/out/rust/release/anki-sync-server"
[ -x "$SERVER_BIN" ] || { info "building anki-sync-server"; cargo build -p anki-sync-server --release; }

info "starting sync server on $ENDPOINT"
SYNC_HOST="$HOST" SYNC_PORT="$PORT" SYNC_BASE="$SERVER_BASE" SYNC_USER1="$USER:$PASS" \
  RUST_LOG=anki=info "$SERVER_BIN" > "$EVID/server.log" 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do
  curl -sf -o /dev/null "http://$HOST:$PORT/health" && break || sleep 0.3
done
curl -sf -o /dev/null "http://$HOST:$PORT/health" || fail "server did not come up"
ok "server healthy (pid $SERVER_PID)"

# ---- build + install app (data wiped once for a clean run) -------------------
info "building + installing iOS app on '$DEVICE'"
TARGET="aarch64-apple-ios-sim"; export IPHONEOS_DEPLOYMENT_TARGET=16.0
LIBDIR="$CARGO_TARGET_DIR/$TARGET/debug"
[ -f "$LIBDIR/librsios.a" ] || cargo build -p rsios --target "$TARGET"
SDK="$(xcrun --sdk iphonesimulator --show-sdk-path)"
APP="$ROOT/build/sim/ReadyMCAT.app"; rm -rf "$APP"; mkdir -p "$APP"
xcrun -sdk iphonesimulator swiftc -target arm64-apple-ios16.0-simulator -sdk "$SDK" \
  -I "$ROOT/rsios/include" "$ROOT"/ios/ReadyMCAT/*.swift -L "$LIBDIR" -lrsios \
  -framework SwiftUI -framework WebKit -framework UIKit -framework Foundation \
  -framework CoreFoundation -lobjc -liconv -o "$APP/ReadyMCAT"
cp "$ROOT/ios/ReadyMCAT/Info.plist" "$APP/Info.plist"
for f in collection.anki2 taxonomy.json diagnostic_quiz.json subquestions.json; do
  cp "$ROOT/ios/ReadyMCAT/Resources/$f" "$APP/$f"
done
xcrun simctl boot "$DEVICE" 2>/dev/null || true
xcrun simctl bootstatus "$DEVICE" -b >/dev/null 2>&1 || true
xcrun simctl uninstall "$DEVICE" "$BUNDLE_ID" 2>/dev/null || true
xcrun simctl install "$DEVICE" "$APP"
CONTAINER="$(xcrun simctl get_app_container "$DEVICE" "$BUNDLE_ID" data)"
PHONE_COL="$CONTAINER/Documents/collection.anki2"
RESULT="$CONTAINER/Documents/sync_result.json"

# ---- helpers ----------------------------------------------------------------
# phone <action> [reviewN] [endpoint]
phone() {
  local action="$1" reviewN="${2:-0}" ep="${3:-$ENDPOINT}"
  rm -f "$RESULT"; local t0; t0=$(date +%s)
  SIMCTL_CHILD_READYMCAT_SYNC_ACTION="$action" \
  SIMCTL_CHILD_READYMCAT_SYNC_REVIEW="$reviewN" \
  SIMCTL_CHILD_READYMCAT_SYNC_ENDPOINT="$ep" \
  SIMCTL_CHILD_READYMCAT_SYNC_USER="$USER" \
  SIMCTL_CHILD_READYMCAT_SYNC_PASS="$PASS" \
    xcrun simctl launch "$DEVICE" "$BUNDLE_ID" >/dev/null
  local i
  for i in $(seq 1 90); do
    [ -f "$RESULT" ] && [ "$(stat -f %m "$RESULT")" -ge "$t0" ] && break
    sleep 1
  done
  cat "$RESULT"; echo
  xcrun simctl terminate "$DEVICE" "$BUNDLE_ID" 2>/dev/null || true
}
phone_revlog() { sqlite3 "$PHONE_COL" 'select count() from revlog'; }
# desktop <action> [reviewN]
desktop() {
  "$PY" "$ROOT/ios/scripts/desktop-sync.py" --base "$DESKTOP_BASE" \
    --endpoint "$ENDPOINT" --user "$USER" --password "$PASS" \
    --action "$1" ${2:+--review "$2"}
}
desk_revlog() { "$PY" -c "import json,sys; print(json.loads(sys.argv[1])['revlog_count'])" "$1"; }

# ---- 1. phone full upload ---------------------------------------------------
info "1) phone first sync (expect full upload)"
phone sync | grep -q '"ok":true' || fail "phone full upload failed"
ok "phone uploaded the bank"

# ---- 2. desktop full download ----------------------------------------------
info "2) desktop first sync (expect full download)"
D=$(desktop sync); echo "$D"
[ "$(desk_revlog "$D")" -eq 0 ] || fail "desktop baseline revlog should be 0"
ok "desktop downloaded bank; revlog baseline 0"

# ---- 3. phone -> desktop ----------------------------------------------------
info "3) phone reviews 5, syncs up; desktop syncs down"
phone review_sync 5 | grep -q '"reviewed":5' || fail "phone review_sync 5 failed"
[ "$(phone_revlog)" -eq 5 ] || fail "phone revlog should be 5"
D=$(desktop sync); echo "$D"
[ "$(desk_revlog "$D")" -eq 5 ] || fail "desktop should have pulled 5"
ok "phone->desktop: 5 reviews landed"

# ---- 4. desktop -> phone ----------------------------------------------------
info "4) desktop reviews 3, syncs up; phone syncs down"
D=$(desktop review_sync 3); echo "$D"
[ "$(desk_revlog "$D")" -eq 8 ] || fail "desktop revlog should be 8"
phone sync | grep -q '"ok":true' || fail "phone sync (pull 3) failed"
[ "$(phone_revlog)" -eq 8 ] || fail "phone revlog should be 8"
ok "desktop->phone: 3 reviews landed"

# ---- 5. offline review then reconnect --------------------------------------
info "5) phone reviews 4 OFFLINE, sync fails gracefully, then reconnects"
phone review 4 "$BAD_ENDPOINT" | grep -q '"reviewed":4' || fail "offline review failed"
[ "$(phone_revlog)" -eq 12 ] || fail "phone revlog should be 12 after offline review"
phone sync 0 "$BAD_ENDPOINT" | grep -q '"ok":false' || fail "offline sync should fail gracefully"
[ "$(phone_revlog)" -eq 12 ] || fail "offline sync must not lose reviews"
phone sync | grep -q '"ok":true' || fail "reconnect sync failed"
D=$(desktop sync); echo "$D"
[ "$(desk_revlog "$D")" -eq 12 ] || fail "desktop should have pulled 12"
ok "offline reviews synced after reconnect"

# ---- final: revlog id sets must be identical --------------------------------
sqlite3 "$PHONE_COL" 'select id from revlog order by id' > "$EVID/phone-revlog-ids.txt"
sqlite3 "$DESKTOP_BASE/collection.anki2" 'select id from revlog order by id' > "$EVID/desktop-revlog-ids.txt"
cp "$PHONE_COL" "$EVID/phone-collection.anki2"
cp "$DESKTOP_BASE/collection.anki2" "$EVID/desktop-collection.anki2"
if diff -q "$EVID/phone-revlog-ids.txt" "$EVID/desktop-revlog-ids.txt" >/dev/null; then
  N=$(wc -l < "$EVID/phone-revlog-ids.txt" | tr -d ' ')
  U=$(sort -u "$EVID/phone-revlog-ids.txt" | wc -l | tr -d ' ')
  ok "revlog id sets IDENTICAL on phone & desktop: $N rows, $U unique (no loss, no double-count)"
  echo "${GRN}==== SYNC ROUND-TRIP VERIFIED ====${NC}"
else
  fail "revlog id sets differ between phone and desktop"
fi
