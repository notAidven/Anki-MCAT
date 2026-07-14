// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// ReadyMCAT OpenAI proxy — a Cloudflare Worker that keeps the OpenAI key OFF the
// phone. The iOS app used to call api.openai.com directly with an on-device key
// (a documented mobile tradeoff). Now the app POSTs a STRUCTURED card payload to
// this Worker; the Worker holds the OpenAI key as a server-side secret, BUILDS
// the teach-on-miss prompt itself (so a leaked client can't drive arbitrary
// prompts), calls OpenAI, and returns the raw completion text.
//
// The prompt/model/params here are a faithful port of the shared desktop source
// of truth `readymcat/tools/ladder_gen.py` and its iOS port
// `ios/ReadyMCAT/LadderGen.swift` (same system message asking for a short ladder
// of guiding MULTIPLE-CHOICE questions, same 2-4 rung rule, same gpt-4o-mini @
// temperature 0.4, same `response_format: {type:"text"}`). The Worker
// deliberately does NOT parse/validate the ladder: the iOS client keeps running
// the byte-identical MCQ parser + three guardrails (schema / answer-leak /
// grounding) on the returned text, because the grounding gate needs the card's
// own material and the whole retrieve-before-reveal flow lives on-device. So the
// contract is intentionally thin: `{ content: <raw assistant text> }`, exactly
// what the Swift `ChatFn` already expects.

// --- prompt constants (mirror ladder_gen.py / LadderGen.swift) ---------------

const MIN_RUNGS = 2;
const MAX_RUNGS = 4;
const MIN_OPTIONS = 3;
const MAX_OPTIONS = 4;
const DEFAULT_MODEL = "gpt-4o-mini";
const DEFAULT_TEMPERATURE = 0.4;
const DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1";

/** Upstream request timeout (ms). Mirrors LadderGen.defaultTimeoutSecs (30s). */
const OPENAI_TIMEOUT_MS = 30_000;

/** Reject oversized inputs before we ever spend an OpenAI call on them. */
const MAX_FIELD_CHARS = 8_000;
const MAX_TOTAL_CHARS = 16_000;

const ROUTE = "/v1/ladder";

// --- request/response shapes -------------------------------------------------

/**
 * The STRUCTURED payload the iOS client sends. It is NOT an OpenAI request body:
 * the Worker builds the prompt from these fields. `question` is required;
 * everything else is optional. `choices`/`topic` are accepted for
 * forward-compatibility and observability but are NOT injected into the prompt —
 * the shared source of truth builds the prompt from question/answer/source only
 * (the iOS client already folds MCQ options into `question`), and we keep it
 * byte-identical so what ships is what the eval harness scored.
 */
interface LadderRequest {
    question: string;
    answer?: string;
    source?: string;
    choices?: string[];
    topic?: string;
}

interface ChatMessage {
    role: "system" | "user";
    content: string;
}

// --- small helpers -----------------------------------------------------------

const CORS_HEADERS: Record<string, string> = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Max-Age": "86400",
};

function jsonResponse(body: unknown, status = 200): Response {
    return new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json; charset=utf-8", ...CORS_HEADERS },
    });
}

function errorResponse(message: string, status: number): Response {
    return jsonResponse({ error: message }, status);
}

/** Constant-time-ish string compare for the low-value app token. */
function tokensMatch(provided: string, expected: string): boolean {
    const a = new TextEncoder().encode(provided);
    const b = new TextEncoder().encode(expected);
    // timingSafeEqual requires equal lengths; a length mismatch is an obvious
    // non-match. (The app token is low-value; length is not a meaningful secret.)
    if (a.byteLength !== b.byteLength) { return false; }
    return crypto.subtle.timingSafeEqual(a, b);
}

/** Extract "Bearer <token>" from the Authorization header. */
function bearerToken(request: Request): string | null {
    const header = request.headers.get("Authorization") ?? "";
    const match = /^Bearer\s+(.+)$/i.exec(header.trim());
    return match ? match[1].trim() : null;
}

// --- prompt (faithful port of ladder_gen.build_messages) ---------------------

function buildMessages(req: LadderRequest): ChatMessage[] {
    const question = (req.question ?? "").trim();
    const answer = (req.answer ?? "").trim();
    const source = (req.source ?? "").trim();

    const system = "You are a tutor for the MCAT. A student just answered a question "
        + "WRONG. Do NOT reveal the answer outright. Instead, write a short "
        + "ladder of guiding MULTIPLE-CHOICE questions that make the student "
        + "WORK IT OUT by choosing (active retrieval, not passive reading).\n\n"
        + "Hard rules:\n"
        + `- Output ${MIN_RUNGS}-${MAX_RUNGS} rungs, ordered from foundational to `
        + "the step just before the answer; the LAST rung should lead the student "
        + "to recall the final answer themselves.\n"
        + "- Each rung is one multiple-choice question with a short stem "
        + `('question'), ${MIN_OPTIONS}-${MAX_OPTIONS} answer 'options', a `
        + "'correctIndex' (0-based index of the correct option), and a one-line "
        + "'explanation' of why that option is correct.\n"
        + "- The FIRST rung must NOT state or give away the final answer; it "
        + "establishes a prerequisite idea.\n"
        + "- Distractors must be plausible but clearly WRONG given the material; "
        + "options must be distinct.\n"
        + "- Every stem, option, correct answer and explanation must be grounded "
        + "ONLY in the provided material — do not introduce facts that are not "
        + "supported by it.\n"
        + "Return ONLY a JSON array: [{\"question\": \"...\", \"options\": [\"...\", "
        + "\"...\", \"...\"], \"correctIndex\": 0, \"explanation\": \"...\"}, ...] with no "
        + "prose, no markdown, no code fences.";

    const parts: string[] = [`QUESTION THE STUDENT MISSED:\n${question}`];
    if (answer) {
        parts.push(
            "\nCORRECT ANSWER / EXPLANATION (for your reference only, "
                + `do NOT reveal it directly):\n${answer}`,
        );
    }
    if (source) {
        parts.push(`\nCITED SOURCE MATERIAL:\n${source}`);
    }
    parts.push(
        `\nWrite the ${MIN_RUNGS}-${MAX_RUNGS} guiding multiple-choice questions now as the `
            + "JSON array described.",
    );

    return [
        { role: "system", content: system },
        { role: "user", content: parts.join("\n") },
    ];
}

// --- OpenAI call (faithful port of ladder_gen.openai_chat) -------------------

/** Raised for any upstream transport/API/shape problem → surfaced as a 502. */
class UpstreamError extends Error {}

async function callOpenAI(
    messages: ChatMessage[],
    env: Env,
): Promise<string> {
    const apiKey = env.OPENAI_API_KEY;
    const model = env.MODEL || DEFAULT_MODEL;
    const temperature = Number.parseFloat(env.TEMPERATURE) || DEFAULT_TEMPERATURE;
    const baseURL = (env.OPENAI_BASE_URL || DEFAULT_OPENAI_BASE_URL).replace(/\/+$/, "");

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), OPENAI_TIMEOUT_MS);

    let upstream: Response;
    try {
        upstream = await fetch(`${baseURL}/chat/completions`, {
            method: "POST",
            headers: {
                Authorization: `Bearer ${apiKey}`,
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                model,
                messages,
                temperature,
                response_format: { type: "text" },
            }),
            signal: controller.signal,
        });
    } catch (err) {
        const reason = err instanceof Error ? err.message : String(err);
        throw new UpstreamError(`OpenAI request failed: ${reason}`);
    } finally {
        clearTimeout(timeout);
    }

    if (!upstream.ok) {
        // Truncate the upstream body; OpenAI errors never echo the key, but we keep
        // it short and generic so nothing sensitive can leak into client logs.
        const detail = (await upstream.text()).slice(0, 300);
        throw new UpstreamError(`OpenAI HTTP ${upstream.status}: ${detail}`);
    }

    let payload: unknown;
    try {
        payload = await upstream.json();
    } catch {
        throw new UpstreamError("OpenAI returned non-JSON");
    }

    const content = (payload as { choices?: { message?: { content?: unknown } }[] })
        ?.choices?.[0]?.message?.content;
    if (typeof content !== "string") {
        throw new UpstreamError("unexpected OpenAI response shape");
    }
    return content;
}

// --- input validation --------------------------------------------------------

function parseLadderRequest(raw: unknown): LadderRequest | { error: string } {
    if (typeof raw !== "object" || raw === null) {
        return { error: "body must be a JSON object" };
    }
    const obj = raw as Record<string, unknown>;

    const question = obj.question;
    if (typeof question !== "string" || question.trim().length === 0) {
        return { error: "`question` is required and must be a non-empty string" };
    }

    const optionalString = (v: unknown, name: string): string | { error: string } => {
        if (v === undefined || v === null) { return ""; }
        if (typeof v !== "string") { return { error: `\`${name}\` must be a string` }; }
        return v;
    };

    const answer = optionalString(obj.answer, "answer");
    if (typeof answer === "object") { return answer; }
    const source = optionalString(obj.source, "source");
    if (typeof source === "object") { return source; }
    const topic = optionalString(obj.topic, "topic");
    if (typeof topic === "object") { return topic; }

    let choices: string[] | undefined;
    if (obj.choices !== undefined && obj.choices !== null) {
        if (!Array.isArray(obj.choices) || obj.choices.some((c) => typeof c !== "string")) {
            return { error: "`choices` must be an array of strings" };
        }
        choices = obj.choices as string[];
    }

    if (
        question.length > MAX_FIELD_CHARS
        || answer.length > MAX_FIELD_CHARS
        || source.length > MAX_FIELD_CHARS
    ) {
        return { error: `each field must be at most ${MAX_FIELD_CHARS} characters` };
    }
    if (question.length + answer.length + source.length > MAX_TOTAL_CHARS) {
        return { error: `combined input must be at most ${MAX_TOTAL_CHARS} characters` };
    }

    return { question, answer, source, topic: topic || undefined, choices };
}

// --- request handling --------------------------------------------------------

async function handleLadder(request: Request, env: Env): Promise<Response> {
    // Server misconfiguration → 500 (but never echo which secret is missing in a
    // way that helps an attacker; the message is generic).
    if (!env.OPENAI_API_KEY || !env.APP_TOKEN) {
        console.error("proxy misconfigured: OPENAI_API_KEY and/or APP_TOKEN unset");
        return errorResponse("proxy is not configured", 500);
    }

    // Abuse gate: the low-value app token. Its ONLY job is to stop a stranger from
    // spending your OpenAI budget — the high-value OpenAI key stays server-side.
    const provided = bearerToken(request);
    if (!provided || !tokensMatch(provided, env.APP_TOKEN)) {
        return errorResponse("unauthorized", 401);
    }

    let raw: unknown;
    try {
        raw = await request.json();
    } catch {
        return errorResponse("invalid JSON body", 400);
    }

    const parsed = parseLadderRequest(raw);
    if ("error" in parsed) {
        return errorResponse(parsed.error, 400);
    }

    const messages = buildMessages(parsed);
    try {
        const content = await callOpenAI(messages, env);
        return jsonResponse({ content, model: env.MODEL || DEFAULT_MODEL });
    } catch (err) {
        const reason = err instanceof Error ? err.message : String(err);
        console.error("upstream error:", reason);
        return errorResponse("upstream generation failed", 502);
    }
}

export default {
    async fetch(request: Request, env: Env): Promise<Response> {
        const url = new URL(request.url);

        if (request.method === "OPTIONS") {
            return new Response(null, { status: 204, headers: CORS_HEADERS });
        }

        // Lightweight liveness probe (handy for `wrangler dev` sanity checks).
        if (request.method === "GET" && (url.pathname === "/" || url.pathname === "/health")) {
            return jsonResponse({ ok: true, service: "readymcat-openai-proxy", route: ROUTE });
        }

        if (url.pathname !== ROUTE) {
            return errorResponse("not found", 404);
        }
        if (request.method !== "POST") {
            return new Response(JSON.stringify({ error: "method not allowed" }), {
                status: 405,
                headers: { "Content-Type": "application/json; charset=utf-8", Allow: "POST", ...CORS_HEADERS },
            });
        }

        return handleLadder(request, env);
    },
} satisfies ExportedHandler<Env>;
