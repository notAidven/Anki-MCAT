// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

// Shape of the ``readymcatHomeStatus`` mediasrv JSON response (see
// ``qt/aqt/mediasrv.py::readymcat_home_status`` and
// ``readymcat/tools/home_launcher.py::summarize_home_status``). Plain JSON
// rather than a generated protobuf type since it's a small, Python-level
// aggregation endpoint, not a Rust backend service.

export interface DeckLaunchCounts {
    present: boolean;
    deckId: number | null;
    due: number;
    total: number;
}

export type DeckLaunchKey = "mcq" | "fr" | "passage" | "cars";

export interface HomeProgress {
    cardsStudied: number;
    streakDays: number;
    activeDaysThisWeek: number;
    reviewsLast7d: number;
    /** Fraction (0..1) of the last 7 days' reviews graded above "Again", or
     * null when there is no evidence in the window — never fabricated. */
    accuracy7d: number | null;
}

export interface HomeDiagnosticStatus {
    taken: boolean;
    /** Unix seconds, or null when not yet taken. */
    takenAt: number | null;
}

export interface HomeStatus {
    available: boolean;
    reason?: string;
    decks?: Record<DeckLaunchKey, DeckLaunchCounts>;
    progress?: HomeProgress;
    diagnostic?: HomeDiagnosticStatus;
}
