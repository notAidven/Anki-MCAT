#!/usr/bin/env bash
# Build the full ReadyMCAT question bank into a bundled iOS collection.
#
# This provisions all four content types (MCQ + Free Response + Passage + CARS,
# ~1,075 cards) into a fresh .anki2 using the SAME host tooling the desktop uses
# (readymcat/tools/build_question_bank.py --collection), then post-processes it
# so it is a good on-device study experience:
#   * raises the per-deck new/review daily limits (so the reviewers actually have
#     cards to serve on a fresh phone),
#   * selects the points-at-stake review order (order 13; taxonomy.json is
#     bundled beside the collection so the engine can rank).
#
# The deck layout is left EXACTLY as build_question_bank.py builds it — the
# canonical layout the desktop uses and the phone receives over sync: MCQ in the
# top-level `ReadyMCAT` deck, `ReadyMCAT::Free Response`, `ReadyMCAT::Passages`,
# and `ReadyMCAT::Passages::CARS`. (An earlier build relocated MCQ/CARS into
# their own leaf decks so tiles mapped 1:1; that diverged from the synced bank
# and made the MCQ/CARS tiles read NOT LOADED after a sync. The iOS app now
# isolates MCQ/Passage study with a filtered deck instead — see AppModel
# .studyDeckId — so no relocation is needed and bundled == synced.)
#
# The result + taxonomy.json + diagnostic_quiz.json + subquestions.json are copied
# into ios/ReadyMCAT/Resources/, from where the app copies them to Documents on
# first launch.
#
# Env:
#   ANKI_PYTHON   python that can `import anki` (default: the repo's out/pyenv)
#   ANKI_PYLIB    dir to add to PYTHONPATH so the generated anki modules resolve
#                 (default: <repo>/out/pylib)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ANKI_PYTHON="${ANKI_PYTHON:-$ROOT/out/pyenv/bin/python}"
ANKI_PYLIB="${ANKI_PYLIB:-$ROOT/out/pylib}"
RES="$ROOT/ios/ReadyMCAT/Resources"
WORK="$ROOT/ios/build-collection"
COL="$WORK/collection.anki2"

if [ ! -x "$ANKI_PYTHON" ]; then
  echo "!! ANKI_PYTHON ($ANKI_PYTHON) not found. Point it at a python that can 'import anki'." >&2
  echo "   e.g. ANKI_PYTHON=/path/to/anki/out/pyenv/bin/python ANKI_PYLIB=/path/to/anki/out/pylib $0" >&2
  exit 1
fi

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/rmcat-pycache"
export PYTHONPATH="$ANKI_PYLIB${PYTHONPATH:+:$PYTHONPATH}"

echo ">> provisioning full bank into $COL"
rm -rf "$WORK"; mkdir -p "$WORK"
"$ANKI_PYTHON" readymcat/tools/build_question_bank.py --collection "$COL" >/dev/null

echo ">> post-processing (limits, review order — canonical layout preserved)"
"$ANKI_PYTHON" - "$COL" <<'PY'
import sys
from anki.collection import Collection

col = Collection(sys.argv[1])

# generous daily limits + points-at-stake review order on every config, so the
# reviewers actually have cards to serve on a fresh phone and rank by points.
# The deck layout is deliberately left as build_question_bank.py built it (the
# canonical layout the phone receives over sync); MCQ/Passage study isolation is
# handled in-app by a filtered deck, not by relocating cards here.
for conf in col.decks.all_config():
    conf["new"]["perDay"] = 2000
    conf["rev"]["perDay"] = 2000
    conf["reviewOrder"] = 13  # REVIEW_CARD_ORDER_POINTS_AT_STAKE
    col.decks.save(conf)

col.close()

# reopen to report the final layout
col = Collection(sys.argv[1])
print("final decks:")
for d in col.decks.all_names_and_ids(skip_empty_default=True):
    n = len(col.find_cards(f'deck:"{d.name}"'))
    print(f"  {d.name}: {n}")
col.close()
PY

echo ">> copying bundle into $RES"
mkdir -p "$RES"
cp "$COL" "$RES/collection.anki2"
cp "$ROOT/taxonomy.json" "$RES/taxonomy.json"
cp "$ROOT/readymcat/diagnostic/diagnostic_quiz.json" "$RES/diagnostic_quiz.json"
cp "$ROOT/subquestions.json" "$RES/subquestions.json"
echo ">> done:"
ls -la "$RES"
