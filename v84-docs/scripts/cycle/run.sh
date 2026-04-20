#!/bin/bash

# Run draft/patch → lead → architect cycles until APPROVED or max rounds.
#
# Usage: ./v84-docs/scripts/cycle/run.sh <iteration> [max_rounds]
#
# Provider / model / API URL come from env: LLM_PROVIDER, LLM_MODEL,
# LLM_API_URL. Missing vars are filled in by detect-llm.sh.
#
# Flow per round:
#   1a. Patch (if corrections.md from previous round)       — mid-cycle
#   1b. Draft (if no corrections.md and no approved.md)     — first-run after plan
#   2.  Lead review (per role, parallel)
#   3.  Architect review (validates leads + cross-role)
#   4.  Log round results
#   5.  Stop if APPROVED, else loop
#
# Running after `scripts/architect/run.sh plan {n}` is enough — the first round
# will perform the initial draft, subsequent rounds will patch from corrections.

set -euo pipefail

ITERATION="${1:?Usage: cycle/run.sh <iteration> [max_rounds]}"
MAX_ROUNDS="${2:-10}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
PLAN_DIR="${REPO_ROOT}/v84-docs/plan/${ITERATION}"

eval "$(bash "${SCRIPT_DIR}/../detect-llm.sh")"

echo "LLM: ${LLM_PROVIDER} @ ${LLM_API_URL} → ${LLM_MODEL}"

for ((i=1; i<=MAX_ROUNDS; i++)); do
  echo ""
  echo "=========================================="
  echo "  ROUND $i / $MAX_ROUNDS"
  echo "=========================================="

  # 1. Patch (mid-cycle) OR initial draft (first round after plan).
  # `-s` requires the file exists AND is non-empty — empty corrections.md
  # (left over from a prior APPROVED round) shouldn't trigger a pointless patch.
  if [[ -s "${PLAN_DIR}/corrections.md" ]]; then
    echo ""
    echo "--- Patching ---"
    bash "${SCRIPT_DIR}/../agents/run.sh" "$ITERATION" patch
  elif [[ ! -f "${PLAN_DIR}/approved.md" ]]; then
    echo ""
    echo "--- Drafting (initial) ---"
    bash "${SCRIPT_DIR}/../agents/run.sh" "$ITERATION" draft
  fi

  # 2. Lead review
  echo ""
  echo "--- Lead Review ---"
  bash "${SCRIPT_DIR}/../leads/run.sh" "$ITERATION"

  # 3. Architect review
  echo ""
  echo "--- Architect Review ---"
  bash "${SCRIPT_DIR}/../architect/run.sh" review "$ITERATION"

  # 4. Check result
  if [[ -f "${PLAN_DIR}/approved.md" ]]; then
    echo ""
    echo "=========================================="
    echo "  APPROVED after $i round(s)"
    echo "=========================================="
    exit 0
  fi

  # 5. Log round
  bash "${SCRIPT_DIR}/log.sh" "$ITERATION" "$i"

  echo "Corrections found, continuing..."
done

echo ""
echo "=========================================="
echo "  NOT APPROVED after $MAX_ROUNDS rounds"
echo "=========================================="
exit 1
