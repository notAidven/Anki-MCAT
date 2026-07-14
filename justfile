set windows-shell := ["pwsh", "-NoLogo", "-NoProfileLoadTime", "-Command"]

mod release

# Show available commands
default:
    @just --list

# Build the project
build:
    {{ ninja }} pylib qt

# Build and run Anki in development mode
run *args:
    {{ run_script }} {{ args }}

# Build and run Anki in optimized (release) mode
run-optimized *args:
    {{ if os() == "windows" { "$env:RELEASE='1'; .\\run.bat" } else { "RELEASE=1 ./run" } }} {{ args }}

# Watch web sources and rebuild/reload Anki's web stack on change (macOS/Linux)
web-watch:
    ./tools/web-watch

# Rebuild and reload Anki's web stack without restarting (macOS/Linux)
rebuild-web:
    ./tools/rebuild-web

# Build wheels (needed for some platforms)
wheels:
    {{ ninja }} wheels

# Build and run all checks (lint + test) - lets ninja handle dependencies
check:
    {{ ninja }} pylib qt check

# ReadyMCAT: one-command §10 speed benchmark on a synthetic 50k-card deck —
# p50/p95/worst for queue build, button press, next card, dashboard load +
# refresh, and cold start; a full-upload + incremental collection sync; and peak
# RSS vs a stated memory ceiling. Writes tools/mcat_bench/bench-results.{json,md}.
bench *args:
    {{ if os() == "windows" { "$env:CARGO_TARGET_DIR='out/rust'; cargo run --release -p mcat_bench --" } else { "CARGO_TARGET_DIR=out/rust cargo run --release -p mcat_bench --" } }} {{ args }}

# ReadyMCAT: run the teach-on-miss ladder-generation eval harness over the
# held-out golden set (needs OPENAI_API_KEY). Pass --stub to run fully offline.
eval *args:
    {{ uv }} run python readymcat/eval/run_eval.py {{ args }}

# ReadyMCAT: literal leakage / training-data scan (spec 7e) — flags any held-out
# eval item (golden_set + paraphrase_set) that is an exact or near-duplicate of
# an authored bank question. Writes readymcat/eval/leakage_scan.json; exits
# non-zero if anything is flagged. Pure stdlib, offline.
leakage-scan *args:
    {{ uv }} run python readymcat/eval/leakage_scan.py {{ args }}

# ReadyMCAT: calibrate the MEMORY (FSRS) model — writes a reliability chart
# (calibration.png) + a Brier/log-loss score (calibration.json) on held-out
# reviews. Synthetic by default; pass --collection PATH to score real reviews.
calibrate *args:
    PYTHONPATH=out/pylib out/pyenv/bin/python readymcat/eval/calibrate_memory.py {{ args }}

# ReadyMCAT: held-out PERFORMANCE check — paraphrase accuracy on unseen
# exam-style items, demonstrating performance is a signal distinct from memory.
perf-heldout *args:
    PYTHONPATH=out/pylib out/pyenv/bin/python readymcat/eval/performance_heldout.py {{ args }}

# ReadyMCAT: study-feature ablation — teach-on-miss ON vs OFF vs plain-Anki at
# equal study time, reporting re-retrieval/accuracy honestly (incl. null results).
ablation *args:
    {{ uv }} run --with matplotlib python readymcat/eval/ablation.py {{ args }}

# ReadyMCAT: crash / durability test — SIGKILL the engine mid-review N times on a
# THROWAWAY profile and confirm no corruption / no lost reviews (never touches a
# real profile). Writes readymcat/eval/crash_durability.json.
crash-test *args:
    PYTHONPATH=out/pylib out/pyenv/bin/python readymcat/eval/crash_durability.py {{ args }}

# ReadyMCAT: same-card sync-CONFLICT proof — two headless clients review the same
# card offline, then sync; verifies winner-by-timestamp + loser's revlog preserved.
sync-conflict *args:
    bash ios/scripts/verify-sync-conflict.sh {{ args }}

# ReadyMCAT: seed SYNTHETIC demo data so the honest dashboard + topic-mastery
# rings render fully populated (Memory / Performance / Readiness) for a UI
# preview. The data is FAKE and clearly labelled (tag:ReadyMCAT_SYNTHETIC_DEMO).
# Target a profile with --anki-base BASE [--profile "User 1"], or a --collection
# PATH; pass --reseed to rebuild existing demo data. Close the desktop app first
# so the collection is not open elsewhere. Example:
#   just seed-demo --anki-base "$HOME/Library/Application Support/Anki2" --reseed
seed-demo *args:
    PYTHONPATH=out/pylib out/pyenv/bin/python readymcat/tools/seed_demo_dashboard.py {{ args }}

# ReadyMCAT: remove ALL SYNTHETIC demo data (notes, cards AND the synthetic
# reviews) from a profile, leaving a clean real-data-only collection. Same
# --anki-base/--profile or --collection target as seed-demo. Close the app first.
clear-demo *args:
    PYTHONPATH=out/pylib out/pyenv/bin/python readymcat/tools/seed_demo_dashboard.py --clear-demo {{ args }}

# Run all tests (Rust, Python, TypeScript). Pass --coverage to enforce coverage, and --html to include HTML reports.
[arg("coverage", long="coverage", value="--coverage")]
[arg("html", long="html", value="--html")]
test coverage='' html='':
    just {{ if coverage == "--coverage" { "coverage " + html } else { "_test" } }}

# Run coverage for all test stacks. Pass --html to also generate HTML reports.
[arg("html", long="html", value="--html")]
coverage html='':
    just _coverage-rust {{ html }}
    just _coverage-py {{ html }}
    just _coverage-ts {{ html }}

# Run Rust tests. Pass --coverage to enforce Rust coverage, and --html to include an HTML report.
[arg("coverage", long="coverage", value="--coverage")]
[arg("html", long="html", value="--html")]
test-rust coverage='' html='':
    just {{ if coverage == "--coverage" { "_coverage-rust " + html } else { "_test-rust" } }}

# Run Python tests (pylib + qt). Pass --coverage to enforce coverage, and --html to include HTML reports.
[arg("coverage", long="coverage", value="--coverage")]
[arg("html", long="html", value="--html")]
test-py coverage='' html='':
    just {{ if coverage == "--coverage" { "_coverage-py " + html } else { "_test-py" } }}

# Run TypeScript/Svelte Vitest tests. Pass --coverage to enforce coverage, and --html to include an HTML report.
[arg("coverage", long="coverage", value="--coverage")]
[arg("html", long="html", value="--html")]
test-ts coverage='' html='':
    just {{ if coverage == "--coverage" { "_coverage-ts " + html } else { "_test-ts" } }}

# Run Playwright end-to-end tests. Pass --ui to open the interactive UI.
[arg("ui", long="ui", value="--ui")]
test-e2e ui='': _install-playwright-browsers
    {{ ninja }} pyenv ts:generated pylib qt
    {{ playwright_env }} {{ yarn }} test:e2e {{ ui }}

[private]
_test:
    {{ ninja }} check:rust_test check:pytest check:vitest

[private]
_test-rust:
    {{ ninja }} check:rust_test

[private]
_test-py:
    {{ ninja }} check:pytest

[private]
_test-ts:
    {{ ninja }} check:vitest

[private]
_coverage-rust html='':
    {{ if os_family() == "windows" { "tools\\coverage\\coverage-rust" } else { "tools/coverage/coverage-rust" } }} {{ html }}

[private]
_coverage-py html='':
    {{ ninja }} pylib qt
    just _coverage-py-pylib {{ html }}
    just _coverage-py-qt {{ html }}

[private]
_coverage-py-pylib html='':
    {{ if os_family() == "windows" { "tools\\coverage\\coverage-py" } else { "tools/coverage/coverage-py" } }} pylib {{ html }}

[private]
_coverage-py-qt html='':
    {{ if os_family() == "windows" { "tools\\coverage\\coverage-py" } else { "tools/coverage/coverage-py" } }} qt {{ html }}

[private]
_coverage-ts html='':
    {{ ninja }} node_modules ts:generated
    {{ if os_family() == "windows" { "tools\\coverage\\coverage-ts" } else { "tools/coverage/coverage-ts" } }} {{ html }}

[private]
_install-playwright-browsers:
    {{ ninja }} node_modules
    {{ playwright_env }} {{ yarn }} playwright install chromium

# Check formatting (fast, no build needed)
fmt:
    {{ ninja }} check:format

# Fix formatting
fix-fmt:
    {{ ninja }} format

# Run linting and type checking (requires build outputs)
lint:
    {{ ninja }} \
        check:clippy \
        check:mypy \
        check:ruff \
        check:eslint \
        check:svelte \
        check:typescript

# Fix auto-fixable lint issues (ruff + eslint)
fix-lint:
    {{ ninja }} fix:ruff fix:eslint

# Run minilints (copyright, contributors, licenses)
minilints:
    {{ ninja }} check:minilints

# Fix minilints (update licenses.json)
fix-minilints:
    {{ ninja }} fix:minilints

# Sync translation files
ftl-sync:
    {{ ninja }} ftl-sync

# Deprecate translation strings
ftl-deprecate:
    {{ ninja }} ftl-deprecate

# Build documentation site
docs:
    {{ uv }} run --group docs sphinx-build -b html docs out/docs/html
    @echo "Docs built at out/docs/html/index.html"

# Build and serve documentation site
docs-serve:
    {{ uv }} run --group docs sphinx-autobuild docs out/docs/html --host 127.0.0.1 --port 8000

# Build Rust API docs
docs-rust:
    cargo doc --open

# Dispatch CI workflow on a given branch or tag
ci branch:
    gh workflow run ci.yml --ref {{ branch }}

# Run Complexipy in regression-only mode
complexipy-diff:
    {{ ninja }} check:complexipy-diff

# Remove build outputs from out/ (pass keep-env to keep node_modules/pyenv); macOS/Linux
clean *args:
    ./tools/clean {{ args }}

# Helpers to get the right commands for the platform

ninja := if os() == "windows" { "tools\\ninja" } else { "./ninja" }
run_script := if os() == "windows" { ".\\run.bat" } else { "./run" }
playwright_env := if os() == "windows" { "set PLAYWRIGHT_BROWSERS_PATH=out\\playwright-browsers&&" } else { "PLAYWRIGHT_BROWSERS_PATH=out/playwright-browsers" }
yarn := if os() == "windows" { "out\\extracted\\node\\yarn.cmd" } else { "out/extracted/node/bin/yarn" }
uv := env("UV_BINARY", if os() == "windows" { "out\\extracted\\uv\\uv" } else { "out/extracted/uv/uv" })
export UV_PROJECT_ENVIRONMENT := if os() == "windows" { "out\\pyenv" } else { "out/pyenv" }
