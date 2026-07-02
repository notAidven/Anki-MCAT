#!/usr/bin/env bash
# Build the ReadyMCAT iOS app (via swiftc, no .xcodeproj needed), install it on
# an iOS Simulator, and launch it. This is the reproducible verification path.
#
# Usage:
#   ios/scripts/run-sim.sh ["iPhone 17"]      # interactive (open Simulator.app)
#   AUTORUN=1 ios/scripts/run-sim.sh          # headless auto-review + result
set -euo pipefail

export PATH="$HOME/.cargo/bin:$PATH"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

DEVICE="${1:-iPhone 17}"
BUNDLE_ID="com.readymcat.ios"
TARGET="aarch64-apple-ios-sim"
PROFILE="debug"
export IPHONEOS_DEPLOYMENT_TARGET="${IPHONEOS_DEPLOYMENT_TARGET:-16.0}"
TARGET_DIR="${CARGO_TARGET_DIR:-$ROOT/target}"
LIBDIR="$TARGET_DIR/$TARGET/$PROFILE"

if [ ! -f "$LIBDIR/librsios.a" ]; then
  echo ">> building rust lib for $TARGET"
  cargo build -p rsios --target "$TARGET"
fi

SDK="$(xcrun --sdk iphonesimulator --show-sdk-path)"
APP="$ROOT/build/sim/ReadyMCAT.app"
rm -rf "$APP"; mkdir -p "$APP"

echo ">> compiling Swift app"
xcrun -sdk iphonesimulator swiftc \
  -target "arm64-apple-ios${IPHONEOS_DEPLOYMENT_TARGET}-simulator" \
  -sdk "$SDK" \
  -I "$ROOT/rsios/include" \
  "$ROOT"/ios/ReadyMCAT/*.swift \
  -L "$LIBDIR" -lrsios \
  -framework SwiftUI -framework WebKit -framework UIKit -framework Foundation \
  -framework CoreFoundation -lobjc -liconv \
  -o "$APP/ReadyMCAT"

cp "$ROOT/ios/ReadyMCAT/Info.plist" "$APP/Info.plist"
# Bundle the full ReadyMCAT bank + its companion JSON (taxonomy for the
# points-at-stake dashboard, diagnostic bank, teach-on-miss sub-questions).
RES="$ROOT/ios/ReadyMCAT/Resources"
for f in collection.anki2 taxonomy.json diagnostic_quiz.json subquestions.json; do
  if [ -f "$RES/$f" ]; then
    cp "$RES/$f" "$APP/$f"
  else
    echo "!! missing $RES/$f — run ios/scripts/build-collection.sh first" >&2
    exit 1
  fi
done
# Optional SYNTHETIC demo collection (for previewing a populated dashboard via
# READYMCAT_COLLECTION=demo); bundled only when present.
[ -f "$RES/collection-demo.anki2" ] && cp "$RES/collection-demo.anki2" "$APP/collection-demo.anki2"

echo ">> booting '$DEVICE'"
xcrun simctl boot "$DEVICE" 2>/dev/null || true
xcrun simctl bootstatus "$DEVICE" -b >/dev/null 2>&1 || true
xcrun simctl uninstall "$DEVICE" "$BUNDLE_ID" 2>/dev/null || true
xcrun simctl install "$DEVICE" "$APP"

if [ "${AUTORUN:-0}" = "1" ]; then
  echo ">> launching headless auto-review"
  SIMCTL_CHILD_READYMCAT_AUTORUN=1 xcrun simctl launch "$DEVICE" "$BUNDLE_ID"
  sleep 4
  CONTAINER="$(xcrun simctl get_app_container "$DEVICE" "$BUNDLE_ID" data)"
  echo ">> review_result.json: $(cat "$CONTAINER/Documents/review_result.json" 2>/dev/null || echo '(missing)')"
else
  echo ">> launching interactively (run 'open -a Simulator' to view)"
  xcrun simctl launch "$DEVICE" "$BUNDLE_ID"
fi
