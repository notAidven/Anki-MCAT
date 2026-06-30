#!/usr/bin/env bash
# Build the rsios static library for the iOS Simulator and package it as an
# .xcframework consumed by the Xcode project.
#
# Env:
#   TARGET   (default aarch64-apple-ios-sim)   rustup target
#   PROFILE  (default debug)                   debug|release
#   IPHONEOS_DEPLOYMENT_TARGET (default 16.0)  keep Rust + C objects aligned
set -euo pipefail

export PATH="$HOME/.cargo/bin:$PATH"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TARGET="${TARGET:-aarch64-apple-ios-sim}"
PROFILE="${PROFILE:-debug}"
export IPHONEOS_DEPLOYMENT_TARGET="${IPHONEOS_DEPLOYMENT_TARGET:-16.0}"

PROFILE_FLAG=""
[ "$PROFILE" = "release" ] && PROFILE_FLAG="--release"

echo ">> cargo build -p rsios --target $TARGET $PROFILE_FLAG (min iOS $IPHONEOS_DEPLOYMENT_TARGET)"
cargo build -p rsios --target "$TARGET" $PROFILE_FLAG

TARGET_DIR="${CARGO_TARGET_DIR:-$ROOT/target}"
LIB="$TARGET_DIR/$TARGET/$PROFILE/librsios.a"
[ -f "$LIB" ] || { echo "missing $LIB" >&2; exit 1; }
echo ">> staticlib: $LIB ($(du -h "$LIB" | cut -f1))"

XCF="$ROOT/ios/Frameworks/RsiosFFI.xcframework"
rm -rf "$XCF"
xcodebuild -create-xcframework \
  -library "$LIB" \
  -headers "$ROOT/rsios/include" \
  -output "$XCF"
echo ">> wrote $XCF"
