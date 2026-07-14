# Packaged, signed iOS build (TestFlight or sideload)

The Simulator build (`ios/scripts/run-sim.sh`) needs no signing. A build that
runs on a **real device / clean device** needs _your_ Apple account — signing is
tied to an Apple Developer identity and cannot be done for you. Everything up to
signing is already wired; the steps below are what only you can finish.

Grading note: the rubric caps at **50% if either app doesn't run on a clean
device**, so this + the clean-device recording matter.

## 0. Prerequisites (yours)

- A Mac with Xcode.
- An **Apple ID**. Free is enough for a 7-day **sideload** to your own device;
  a paid **Apple Developer Program** account ($99/yr) is needed for TestFlight
  and for ad-hoc distribution to other testers.
- Your device connected (or a tester's device UDID for ad-hoc).

## 1. Build the Rust core + bundle the deck (already scripted)

```bash
cd anki
PROTOC="$PWD/out/extracted/protoc/bin/protoc" PROTOC_BINARY="$PROTOC" \
  bash ios/scripts/build-rust.sh        # → RsiosFFI.xcframework
bash ios/scripts/build-collection.sh    # → bundles the 1,075-card bank + JSON
```

## 2. Open the project + set signing (the part only you can do)

```bash
open ios/ReadyMCAT.xcodeproj
```

In Xcode → target **ReadyMCAT** → **Signing & Capabilities**:

1. Check **Automatically manage signing**.
2. Set **Team** to your Apple ID / Developer team.
3. Set a **unique Bundle Identifier** (the sim build uses `com.readymcat.ios`;
   change to e.g. `com.<you>.readymcat` so it's unique to your team).
4. Pick your device (not a simulator) as the run destination.

## 3a. Sideload to your own device (free account, fastest)

- Press **Run** (▶) with your device selected. Xcode builds, signs, installs.
- On the device: **Settings → General → VPN & Device Management → trust** your
  developer certificate, then launch **ReadyMCAT**.
- (Free-account apps expire after 7 days — fine for the demo recording.)

## 3b. TestFlight (paid account, shareable)

1. **Product → Archive**.
2. In the Organizer: **Distribute App → App Store Connect → Upload**.
3. In App Store Connect, add the build to **TestFlight**, then install via the
   TestFlight app on the clean device.

## 4. Point the app at your AI proxy (optional, for AI ladders)

In the app: **Settings → AI ladder proxy** → Base URL
`https://readymcat-openai-proxy.evan-cabrera.workers.dev` + your App Token →
toggle **Generate ladders with AI** on. (Everything else works with AI off.)

## 5. Record the clean-device proof

Screen-record: installing (sideload trust screen or TestFlight), first launch
auto-loading the bank, one review, and the Dashboard's three scores. Save it as
`ios/docs/clean-device-install.mov` (referenced by `readymcat/PROOF-SUNDAY.md`).
