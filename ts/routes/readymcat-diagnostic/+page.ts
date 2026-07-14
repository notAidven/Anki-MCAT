// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import { getDiagnosticQuiz } from "@generated/backend";

import type { PageLoad } from "./$types";

export const load = (async ({ url }) => {
    // The Qt layer passes the bundled diagnostic_quiz.json path; otherwise the
    // backend looks next to the collection. `mode` is short (default) | extended.
    const quizPath = url.searchParams.get("quiz") ?? "";
    const mode = url.searchParams.get("mode") ?? "short";
    try {
        const quiz = await getDiagnosticQuiz({ quizPath, mode });
        return { quiz, error: null as string | null };
    } catch (err) {
        return { quiz: null, error: String(err) };
    }
}) satisfies PageLoad;
