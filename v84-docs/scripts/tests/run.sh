#!/bin/bash

# One-shot test runner. Spins up the isolated test stack, runs every test
# suite (API integration, web unit, Playwright e2e), tears the stack down,
# and writes a single-page Markdown summary of what passed/failed.
#
# Every step logs its full output to `test-results/{step}.log` so failures
# can be diagnosed without re-running.
#
# Usage:
#   v84-docs/scripts/tests/run.sh                full cycle: up → api → web → e2e → down
#   v84-docs/scripts/tests/run.sh --up           just bring the stack up (leave it running)
#   v84-docs/scripts/tests/run.sh --down         just tear the stack down
#   v84-docs/scripts/tests/run.sh --test-api     re-run API tests against an already-up stack
#   v84-docs/scripts/tests/run.sh --test-web     re-run web unit tests
#   v84-docs/scripts/tests/run.sh --test-e2e     re-run Playwright e2e
#
# Flags compose — so `run.sh --up --test-api` will bring the stack up and run
# the API suite but leave the stack running, and `run.sh --test-e2e --down`
# re-runs e2e on a live stack and then tears it down.
#
# Every step logs its full output to test-results/{step}.log; the pass/fail
# table lives in test-results/summary.md. Exit code is 0 if every invoked
# step passed, 1 if any failed.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker/test/docker-compose.yml"
RESULTS="${REPO_ROOT}/test-results"
SUMMARY="${RESULTS}/summary.md"

DO_UP=false
DO_API=false
DO_WEB=false
DO_E2E=false
DO_DOWN=false
FULL_CYCLE=false

if [ $# -eq 0 ]; then
  # Default: full cycle.
  DO_UP=true
  DO_API=true
  DO_WEB=true
  DO_E2E=true
  DO_DOWN=true
  FULL_CYCLE=true
else
  for arg in "$@"; do
    case "$arg" in
      --up) DO_UP=true ;;
      --down) DO_DOWN=true ;;
      --test-api) DO_API=true ;;
      --test-web) DO_WEB=true ;;
      --test-e2e) DO_E2E=true ;;
      -h|--help)
        sed -n '3,18p' "$0"
        exit 0
        ;;
      *)
        echo "Unknown option: $arg" >&2
        echo "Run '$0 --help' for usage." >&2
        exit 2
        ;;
    esac
  done
fi

# Pre-create the host paths Playwright bind-mounts into before docker does.
# Otherwise docker creates them as root when the e2e container first starts
# and subsequent host-side reads need sudo.
mkdir -p "$RESULTS" "$RESULTS/e2e_tmp" "$RESULTS/e2e_report"

# On a full cycle invocation (no args), wipe stale *.log / *.md from the
# test-results root so the fresh run isn't contaminated by junk from a
# previous hung/failed session. Subfolders (e2e_tmp/, e2e_report/) are left
# alone — Playwright manages them itself. Partial invocations (--test-api
# etc.) keep prior logs so you can compare iterations while debugging.
if $FULL_CYCLE; then
  find "$RESULTS" -maxdepth 1 -type f \( -name '*.log' -o -name '*.md' \) -delete
fi
{
  echo "# Test run — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  echo "| Step | Result | Duration | Log |"
  echo "|---|---|---|---|"
} > "$SUMMARY"

FAILED=0

# run_step <label> <log-filename> <command...>
# Streams output to stdout and tee's it to the log file, captures the real
# exit status of the command (not tee), and appends a pass/fail row to
# summary.md. Increments FAILED when the step fails.
run_step() {
  local label="$1" logfile="$2"
  shift 2
  local start end dur rc
  start=$(date +%s)
  echo ""
  echo "=== ${label} ==="
  echo "    logs → ${RESULTS}/${logfile}"
  "$@" 2>&1 | tee "${RESULTS}/${logfile}"
  rc=${PIPESTATUS[0]}
  end=$(date +%s)
  dur=$((end - start))
  if [ "$rc" -eq 0 ]; then
    echo "| ${label} | PASS | ${dur}s | [\`${logfile}\`](${logfile}) |" >> "$SUMMARY"
  else
    echo "| ${label} | FAIL | ${dur}s | [\`${logfile}\`](${logfile}) |" >> "$SUMMARY"
    FAILED=$((FAILED + 1))
  fi
}

if $DO_UP; then
  # Deliberately NO --profile e2e here. The e2e service's default CMD is
  # `npx playwright test`, so enabling the profile on `up` would silently
  # run the whole e2e suite during stack startup, create junk users in the
  # DB, and collide with the real --test-e2e run later. The profile stays
  # scoped to the `run --rm e2e` call below, which is the only place we
  # actually want Playwright to fire.
  run_step "Stack up" "stack-up.log" \
    docker compose -f "$COMPOSE_FILE" up -d --build --wait
  # If up failed, skip the suites — they all need a live stack.
  if [ "$FAILED" -gt 0 ]; then
    echo "" >&2
    echo "Stack failed to come up — skipping remaining test steps." >&2
    DO_API=false
    DO_WEB=false
    DO_E2E=false
  fi
fi

if $DO_API; then
  run_step "API integration" "api.log" \
    docker compose -f "$COMPOSE_FILE" exec -T -w /app/apps/api api pnpm test
fi

if $DO_WEB; then
  run_step "Web unit" "web.log" \
    docker compose -f "$COMPOSE_FILE" exec -T web pnpm --filter @v84/web test
fi

if $DO_E2E; then
  run_step "Playwright e2e" "e2e.log" \
    docker compose -f "$COMPOSE_FILE" --profile e2e run --rm e2e
fi

if $DO_DOWN; then
  if [ "$FAILED" -gt 0 ]; then
    echo ""
    echo "Skipping teardown — earlier step(s) failed."
    echo "Stack left up so you can inspect state (Redis keys, DB rows, captured email)."
    echo "Tear it down manually once done: v84-docs/scripts/tests/run.sh --down"
  else
    run_step "Stack down" "stack-down.log" \
      docker compose -f "$COMPOSE_FILE" --profile e2e down -v
  fi
fi

echo ""
echo "================================================"
echo "Summary → ${SUMMARY}"
echo "================================================"
cat "$SUMMARY"

if [ "$FAILED" -gt 0 ]; then
  echo ""
  echo "FAILED — ${FAILED} step(s) did not pass."
  exit 1
fi

echo ""
echo "ALL PASSED."
