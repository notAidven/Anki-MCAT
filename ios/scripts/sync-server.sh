#!/usr/bin/env bash
# Build (if needed) and run a self-hosted Anki sync server on localhost, using
# Anki's OWN standalone server (rslib/sync -> `anki-sync-server`). Both the
# desktop pylib client and the iOS Simulator reach it over the host loopback.
#
# Env (all optional):
#   SYNC_HOST   default 127.0.0.1   (loopback; the Simulator shares the host stack)
#   SYNC_PORT   default 27701
#   SYNC_BASE   default out/sync-verify/server-base   (per-user collections live here)
#   SYNC_USER1  required username:password pair, hashed at boot. Use a
#               throwaway local value and never reuse a real account password.
#
# The server stores each user's collection + media under $SYNC_BASE/<user>/.
set -euo pipefail

export PATH="$HOME/.cargo/bin:$PATH"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

export SYNC_HOST="${SYNC_HOST:-127.0.0.1}"
export SYNC_PORT="${SYNC_PORT:-27701}"
export SYNC_BASE="${SYNC_BASE:-$ROOT/out/sync-verify/server-base}"
: "${SYNC_USER1:?Set SYNC_USER1 to a throwaway username:password pair}"
export SYNC_USER1
export RUST_LOG="${RUST_LOG:-anki=info}"

BIN="$ROOT/out/rust/release/anki-sync-server"
if [ ! -x "$BIN" ]; then
  echo ">> building anki-sync-server (release)"
  CARGO_TARGET_DIR="$ROOT/out/rust" cargo build -p anki-sync-server --release
fi

mkdir -p "$SYNC_BASE"
echo ">> anki-sync-server  http://$SYNC_HOST:$SYNC_PORT/  base=$SYNC_BASE  user=${SYNC_USER1%%:*}"
exec "$BIN"
