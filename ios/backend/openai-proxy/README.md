# ReadyMCAT OpenAI proxy (Cloudflare Worker)

A tiny serverless proxy that keeps the **OpenAI API key off the iOS device**.

The iOS app used to call `api.openai.com` directly with a key stored in the
device Keychain — a documented mobile tradeoff (any key shipped in an app can be
extracted from a jailbroken/instrumented device). This Worker removes that
tradeoff: the phone POSTs a **structured card payload** to the Worker; the Worker
holds the OpenAI key as a **server-side secret**, builds the teach-on-miss prompt
itself, calls OpenAI, and returns the completion. **No OpenAI key ever ships on
the phone.**

```
iOS app  ──HTTPS──►  Cloudflare Worker  ──HTTPS──►  OpenAI
   │  { question, answer, source }          │  builds prompt server-side
   │  Authorization: Bearer <APP_TOKEN>     │  Authorization: Bearer <OPENAI_API_KEY>
   ◄── { content: "[{question,options,correctIndex,explanation}...]" } ──┘  (key never leaves the server)
```

The prompt, model, and params are a faithful port of the shared desktop source of
truth `readymcat/tools/ladder_gen.py` and its iOS port
`ios/ReadyMCAT/LadderGen.swift` (same system message, same 2–4 rung rule,
`gpt-4o-mini` @ temperature `0.4`, `response_format: {type:"text"}`), so behavior
is unchanged.

## Contract decision: the Worker returns RAW completion text

The Worker deliberately does **not** parse or validate the ladder. It returns the
raw model completion as `{ "content": "…" }` — exactly the `String` the iOS
`ChatFn` already expected. The iOS client keeps running the byte-identical parser
and the **three guardrails** (schema / answer-leak / grounding) on that text,
because the grounding gate needs the card's own material and the whole
retrieve-before-reveal flow lives on-device. This keeps the iOS change minimal
and keeps "what ships == what the eval scored."

## Endpoint contract

### `POST /v1/ladder`

**Auth (required).** `Authorization: Bearer <APP_TOKEN>`. Missing/wrong → `401`.

> The app token is a **low-value** secret. Its only job is to stop strangers from
> spending your OpenAI budget; it is trivially rotated server-side. The
> **high-value** OpenAI key stays on the server and is never exposed to clients.

**Request body (JSON).** The app sends the already-composed card context (the iOS
client folds MCQ options into `question`, and the correct answer + explanation
into `answer`):

| Field      | Type     | Required | Notes                                                                        |
| ---------- | -------- | -------- | ---------------------------------------------------------------------------- |
| `question` | string   | yes      | The missed question (stem + options, as the student saw it).                 |
| `answer`   | string   | no       | Correct answer / explanation (used for reference; not leaked).               |
| `source`   | string   | no       | Cited source material (grounding).                                           |
| `choices`  | string[] | no       | Accepted for forward-compat/observability; **not** injected into the prompt. |
| `topic`    | string   | no       | Accepted for forward-compat/observability; **not** injected into the prompt. |

Fields are capped (8 KB each, 16 KB combined) → `400` if exceeded.

**Response `200`.**

```json
{ "content": "[{\"q\": \"…\", \"a\": \"…\"}, …]", "model": "gpt-4o-mini" }
```

`content` is the raw assistant completion (the iOS parser handles code fences /
stray prose). `model` echoes the server-side model for observability.

**Errors** (all clean JSON `{ "error": "…" }`, never leaking the key):

| Status | When                                                                  |
| ------ | --------------------------------------------------------------------- |
| `400`  | Invalid JSON, missing/empty `question`, wrong types, oversized input. |
| `401`  | Missing or wrong `Authorization: Bearer` app token.                   |
| `404`  | Any path other than `/v1/ladder` (or `/health`).                      |
| `405`  | Non-`POST` method on `/v1/ladder`.                                    |
| `500`  | Proxy misconfigured (a secret is unset).                              |
| `502`  | OpenAI/network failure, non-2xx upstream, or bad shape.               |

### `GET /health`

Liveness probe → `{ "ok": true, "service": "readymcat-openai-proxy", "route": "/v1/ladder" }`.

## Configuration

Non-secret settings live in `wrangler.jsonc` (`vars`) and are safe to commit:

| Var               | Default                     | Meaning                                                                              |
| ----------------- | --------------------------- | ------------------------------------------------------------------------------------ |
| `MODEL`           | `gpt-4o-mini`               | OpenAI model (pinned server-side so a leaked token can't select an expensive model). |
| `TEMPERATURE`     | `0.4`                       | Sampling temperature.                                                                |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Upstream base URL.                                                                   |

Secrets are **never** in config — set with `wrangler secret put` (prod) or the
gitignored `.dev.vars` (local): `OPENAI_API_KEY`, `APP_TOKEN`.

## Local development (no Cloudflare account needed)

Uses `npx wrangler` (no global install required).

```bash
cd ios/backend/openai-proxy

# 1. Local secrets (gitignored). Paste the same OpenAI key the desktop uses
#    (repo root anki/.env.local -> OPENAI_API_KEY) and pick any dev app token.
cp .dev.vars.example .dev.vars
$EDITOR .dev.vars

# 2. Install dev deps (wrangler, typescript).
npm install

# 3. Run the Worker locally (default http://127.0.0.1:8787).
npm run dev

# 4. In another terminal: prove auth (401), validation (400), and a live
#    OpenAI ladder (200) end-to-end.
npm run smoke
```

`npm run smoke` reads `APP_TOKEN` from `.dev.vars` (never printed, never commits
the OpenAI key) and exercises all three cases. Example happy-path call (token
redacted):

```bash
curl -sS -X POST http://127.0.0.1:8787/v1/ladder \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <APP_TOKEN>' \
  --data '{
    "question": "What is the net ATP yield of glycolysis?",
    "answer": "Glycolysis invests 2 ATP then produces 4 ATP and 2 NADH, for a net of 2 ATP.",
    "source": "Lippincott Biochemistry — Glycolysis"
  }'
```

Verified response (content abbreviated):

```json
{
    "content": "[{\"q\": \"What are the two main phases of glycolysis?\", \"a\": \"The investment phase and the payoff phase.\"}, … ]",
    "model": "gpt-4o-mini"
}
```

Other scripts: `npm run typecheck` (`tsc --noEmit`), `npm run cf-typegen`
(`wrangler types`), `npx wrangler deploy --dry-run` (validate the bundle).

## Production deploy (run on YOUR Cloudflare account)

```bash
cd ios/backend/openai-proxy
npm install

# 1. Deploy the Worker (creates https://readymcat-openai-proxy.<subdomain>.workers.dev).
npx wrangler deploy

# 2. Set the two secrets (interactive prompt — the value is never echoed).
npx wrangler secret put OPENAI_API_KEY   # paste your real OpenAI key
npx wrangler secret put APP_TOKEN        # paste a fresh random token, e.g. `openssl rand -hex 32`

# 3. (optional) Re-deploy or check:
npx wrangler deploy
npx wrangler tail        # live logs
```

Then point the iOS app at it: **Settings → AI ladder proxy**

- **Base URL** → your `https://readymcat-openai-proxy.<subdomain>.workers.dev`
- **App token** → the same value you set for `APP_TOKEN`
- Toggle **Generate ladders with AI** on, then **Save**.

That's it — the phone now generates ladders through your Worker with no OpenAI
key on the device.

## Security notes & hardening follow-ups

- **The OpenAI key stays server-side.** It is only ever read from
  `env.OPENAI_API_KEY` (a Worker secret) — never from the request, never returned.
- **The app token is low-value.** It only gates who may call the proxy. Rotate it
  freely (`wrangler secret put APP_TOKEN` + update Settings); leaking it costs
  nothing but potential abuse of your OpenAI budget, not the key itself.
- **Hardening (not yet implemented):**
  - **Rate-limiting** — add the Workers Rate Limiting binding (or a KV/DO counter)
    keyed by app token / IP to cap spend.
  - **Cloudflare Access / mTLS / WAF** in front of the Worker for stronger gating.
  - **App Attest / DeviceCheck** (Apple's App Check equivalent) to assert the caller
    is a genuine, unmodified build of the app before minting/accepting a token.

## iOS App Transport Security (ATS) note

Production `*.workers.dev` is HTTPS, so it works out of the box. For **local**
testing the Simulator must reach `http://127.0.0.1:8787` (cleartext). iOS allows
localhost by default in most cases; if a local run is blocked by ATS, add an
`NSAppTransportSecurity` → `NSAllowsLocalNetworking` exception to
`ios/ReadyMCAT/Info.plist` for dev builds only (never ship a cleartext exception
for a public host). On the Simulator, `127.0.0.1` maps to the host Mac, so
`wrangler dev` running on your Mac is reachable.

For a no-typing Simulator run, DEBUG builds seed the proxy config from launch env
vars (see `ios/README.md`): `READYMCAT_PROXY_URL` and `READYMCAT_APP_TOKEN`.
