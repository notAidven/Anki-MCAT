// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Swift value type + decoder for the engine's `anki.decks.DeckTreeNode`
// (proto/anki/decks.proto), fetched via DeckTree(now=<unix secs>) so the backend
// populates the per-deck card counters. The four ReadyMCAT format tiles read
// their due/total counts straight off this tree — the same honest, child-
// excluding counters the desktop home hub uses (see readymcat/tools/home_launcher.py).

import Foundation

struct DeckNode {
    let deckId: Int64
    let name: String
    let totalInDeck: Int
    let newUncapped: Int
    let reviewUncapped: Int
    let intradayLearning: Int
    let interdayLearningUncapped: Int
    let children: [DeckNode]

    /// Genuinely available-to-study count for THIS deck, excluding children and
    /// ignoring daily caps — exactly `deck_launch_stats` in home_launcher.py.
    var due: Int {
        newUncapped + reviewUncapped + intradayLearning + interdayLearningUncapped
    }

    /// Depth-first search for a deck by its fully-qualified name. DeckTreeNode's
    /// `name` is the LEAF component (e.g. "Multiple Choice"), so we rebuild the
    /// "Parent::Child" path as we descend and match against that.
    func find(name target: String) -> DeckNode? {
        find(target: target, prefix: "")
    }

    private func find(target: String, prefix: String) -> DeckNode? {
        let full: String
        if name.isEmpty { full = "" }                       // root (did 0)
        else if name.contains("::") { full = name }          // already a full path
        else if prefix.isEmpty { full = name }               // top-level deck
        else { full = prefix + "::" + name }
        if full == target { return self }
        for child in children {
            if let hit = child.find(target: target, prefix: full) { return hit }
        }
        return nil
    }

    // DeckTreeNode: 1 deck_id · 2 name · 3 children (repeated) · 9 intraday_learning
    //   10 interday_learning_uncapped · 11 new_uncapped · 12 review_uncapped ·
    //   13 total_in_deck
    static func decode(_ b: [UInt8]) -> DeckNode {
        DeckNode(
            deckId: Int64(bitPattern: Proto.firstVarint(b, 1) ?? 0),
            name: Proto.string(b, 2),
            totalInDeck: Proto.uint(b, 13),
            newUncapped: Proto.uint(b, 11),
            reviewUncapped: Proto.uint(b, 12),
            intradayLearning: Proto.uint(b, 9),
            interdayLearningUncapped: Proto.uint(b, 10),
            children: Proto.allBytes(b, 3).map(DeckNode.decode)
        )
    }
}
