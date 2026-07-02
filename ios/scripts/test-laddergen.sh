#!/usr/bin/env bash
# Compile + run the offline unit tests for the iOS ladder-generator guardrail
# port (LadderGen.swift) on the HOST — no Xcode, simulator, or engine needed.
#
# LadderGen.swift is deliberately Foundation-only (no SwiftUI/UIKit, no app
# types), so the ported prompt/parser/guardrails can be checked in isolation
# against the same cases as the desktop source of truth
# (pylib/tests/test_readymcat_ladder_gen.py).
#
#   ios/scripts/test-laddergen.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CORE="$ROOT/ios/ReadyMCAT/LadderGen.swift"
TESTS="$ROOT/ios/ReadyMCATTests/main.swift"
OUT="${TMPDIR:-/tmp}/laddergen-tests"

echo ">> compiling $CORE + $TESTS for the host"
xcrun swiftc -O "$CORE" "$TESTS" -o "$OUT"

echo ">> running"
"$OUT"
