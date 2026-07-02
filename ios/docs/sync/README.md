# ReadyMCAT two-way sync (Anki's own protocol)

Review on the phone → it shows on the desktop after a sync, and the reverse —
with **no lost or double-counted reviews**, plus offline review that syncs when
the connection returns. This is built **entirely on Anki's own collection-sync
protocol and self-hostable sync server** (`rslib/src/sync/**`), not a custom
sync. Reusing Anki's protocol is what guarantees correctness: every review is a
`revlog` row keyed by its epoch-millisecond id and reconciled by USN, so the
server can never lose or duplicate one.

## Architecture

```
 iOS app (Simulator)                     "desktop" (pylib)                self-hosted server
 ┌───────────────────┐                   ┌───────────────────┐           ┌────────────────────┐
 │ SwiftUI Sync tab   │                   │ anki.collection    │           │ anki-sync-server    │
 │ SyncManager        │                   │  .sync_login       │           │ (rslib/sync)        │
 │  → AnkiEngine      │                   │  .sync_collection  │           │  /sync/*  /msync/*  │
 │  → rsios FFI       │  http (loopback)  │  .full_upload_or_  │  http     │  SYNC_USER1=user:pw │
 │  → rslib Backend   │◀─────────────────▶│   download         │◀─────────▶│  per-user .anki2    │
 │  BackendSyncService│   service 1        │ (BackendSyncSvc)   │           │                    │
 └───────────────────┘                   └───────────────────┘           └────────────────────┘
        SAME rslib sync client on both ends ───────────────┘
```

- **iOS**: `SyncManager` drives `BackendSyncService` (service index **1**) through
  the existing `rsios` C-ABI FFI (`AnkiEngine.command(service, method, bytes)`):
  `SyncLogin` (3) → `SyncCollection` (5) → `FullUploadOrDownload` (6) when the
  server asks for a full sync. No engine logic is re-implemented in Swift.
- **Desktop**: `ios/scripts/desktop-sync.py` is a headless client using the same
  `anki.collection.Collection` API the Qt app uses, against a throwaway
  collection. (The Qt GUI itself can point at the same server via
  Preferences → Syncing → self-hosted URL, or the `SYNC_ENDPOINT` env var.)
- **Server**: Anki's standalone `anki-sync-server` (crate `anki-sync-server`,
  `rslib/sync`), configured purely with `SYNC_*` env vars.

### Why no TLS was needed on iOS

The sync backend commands are always compiled into `rslib` (only
`SetCustomCertificate` is behind the `rustls` feature). The sync HTTP client is
`reqwest` with **no TLS backend** in the iOS build — that is fine because we sync
to an **`http://` localhost endpoint**. `reqwest` uses raw TCP sockets (not
`URLSession`), so iOS App Transport Security does not apply, and the iOS
Simulator shares the host network stack, so `http://127.0.0.1:<port>/` reaches
the Mac's server directly. The `rsios` build is therefore unchanged. (For a
real device / HTTPS you would enable `rsios`'s `rustls` feature and use an
`https://` endpoint — the feature is already wired.)

## Running it

### 1. Start the self-hosted server (Mac, localhost)

```bash
# defaults: 127.0.0.1:27701, user rmcat:rmcat, base out/sync-verify/server-base
ios/scripts/sync-server.sh
# or customise:
SYNC_HOST=127.0.0.1 SYNC_PORT=27701 SYNC_BASE=/tmp/rmcat-server \
  SYNC_USER1=me:secret ios/scripts/sync-server.sh
```

### 2. Sync the phone

- **In the app**: open the **Sync** tab → enter the server URL
  (`http://127.0.0.1:27701/`), username, password → **Log in** → **Sync now**.
  The app also syncs automatically on launch and when brought to the foreground
  once configured.
- **Headless** (used by the verifier), via `SIMCTL_CHILD_*` env at launch:
  `READYMCAT_SYNC_ACTION` (`sync` | `review` | `review_sync` | `full_upload` |
  `full_download`), `READYMCAT_SYNC_ENDPOINT`, `READYMCAT_SYNC_USER`,
  `READYMCAT_SYNC_PASS`, `READYMCAT_SYNC_REVIEW=<n>`. The result is written to
  `Documents/sync_result.json`.

### 3. Sync the desktop (headless)

```bash
PYTHONPATH=out/pylib out/pyenv/bin/python ios/scripts/desktop-sync.py \
  --base /tmp/rmcat-desktop --endpoint http://127.0.0.1:27701/ \
  --user rmcat --password rmcat --action sync
```

## Verification (the Friday proof)

`ios/scripts/verify-sync.sh` runs the whole thing automatically and asserts the
revlog id sets match on both ends:

```bash
ios/scripts/verify-sync.sh "iPhone 17 Pro"
```

It performs: phone **full upload** → desktop **full download** (shared lineage,
revlog 0) → phone reviews 5 & syncs, desktop pulls (both == 5) → desktop reviews
3 & syncs, phone pulls (both == 8) → phone reviews 4 **offline** (a sync attempt
fails gracefully without data loss), then reconnects & syncs, desktop pulls
(both == 12). Final check: the phone and desktop `revlog` id lists are
**identical, 12 rows, 12 unique**.

### Captured evidence (in this folder)

- `verify-run.log` — full transcript ending in `==== SYNC ROUND-TRIP VERIFIED ====`.
- `phone-revlog-ids.txt` / `desktop-revlog-ids.txt` — identical id lists (the
  no-loss / no-double-count proof).
- `server-ios-requests.log` — server-side log lines showing the iOS client
  (`client="…,ios"`) hitting `/sync/hostKey`, `/sync/meta`, `/sync/upload`,
  `/sync/start`, `/sync/applyChanges`, `/sync/chunk`, `/sync/finish`.
- `phone-dashboard-3scores.png` — the three honest scores (Memory / Performance
  / Readiness) still render with ranges + the give-up ("needs evidence") rule,
  now reflecting the synced review count.
- `phone-sync-tab.png` — the in-app Sync UI.

## Caveats / remaining gaps

- **Media sync** is intentionally left off in the collection sync
  (`sync_media: false`) for these tests. The plumbing exists (`SyncMedia`,
  service 1 / method 0, and the server's `/msync/*` routes), but media round-trip
  is not part of the verified proof. The ReadyMCAT bank is text, so reviews are
  unaffected.
- **Conflict handling**: a normal incremental sync auto-reconciles. A *full*
  sync only occurs when a side has no cards (forced upload/download) or both
  diverged independently (`FULL_SYNC`); the app resolves the ambiguous case with
  the "Keep this device's cards on conflict" toggle (default: upload). Two
  independently-modified collections cannot be *merged* — that is Anki's model,
  not a ReadyMCAT limitation.
- **Credentials** are stored in `UserDefaults` (fine for a self-hosted dev
  server); a production build should move the password to the Keychain.
- Verified against the **iOS Simulator** using host loopback. A physical device
  needs the Mac's LAN IP (+ Local Network permission) and, for public servers,
  HTTPS (enable the `rustls` feature in `rsios`).
