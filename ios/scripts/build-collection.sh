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
#     bundled beside the collection so the engine can rank),
#   * relocates each format into its own clean leaf sub-deck so the four Home
#     tiles map 1:1 to a deck (deck moves never touch the #ReadyMCAT::AAMC tags
#     the dashboard/points-at-stake resolve against, so the scores are unchanged).
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

echo ">> post-processing (limits, review order, deck layout)"
"$ANKI_PYTHON" - "$COL" <<'PY'
import sys
from anki.collection import Collection

# Tile -> leaf deck the iOS app studies. MCQ and CARS are relocated into their
# own leaf decks so every Home tile maps to exactly one deck with clean counts.
MCQ_SRC = "ReadyMCAT"                       # MCQ notes land in the parent
MCQ_DST = "ReadyMCAT::Multiple Choice"
CARS_SRC = "ReadyMCAT::Passages::CARS"
CARS_DST = "ReadyMCAT::CARS"
MCQ_NOTETYPE = "ReadyMCAT MCQ"

col = Collection(sys.argv[1])

# 1. generous daily limits + points-at-stake review order on every config
for conf in col.decks.all_config():
    conf["new"]["perDay"] = 2000
    conf["rev"]["perDay"] = 2000
    conf["reviewOrder"] = 13  # REVIEW_CARD_ORDER_POINTS_AT_STAKE
    col.decks.save(conf)

# 2. relocate MCQ cards out of the shared parent into their own leaf deck
mcq_dst = col.decks.id(MCQ_DST)
mcq_cards = col.find_cards(f'note:"{MCQ_NOTETYPE}"')
if mcq_cards:
    col.set_deck(mcq_cards, mcq_dst)

# 3. lift CARS up to a top-level sibling so "Passages" is science-only
cars_src = col.decks.id_for_name(CARS_SRC)
if cars_src:
    cars_dst = col.decks.id(CARS_DST)
    cars_cards = col.find_cards(f'deck:"{CARS_SRC}"')
    if cars_cards:
        col.set_deck(cars_cards, cars_dst)
    col.decks.remove([cars_src])

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
