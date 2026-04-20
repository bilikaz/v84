#!/bin/bash

# Run the architect agent — plan or review.
#
# Usage:
#   ./v84-docs/scripts/architect/run.sh plan   <iteration> "<user request>"
#   ./v84-docs/scripts/architect/run.sh review <iteration>
#
# Provider / model / API URL come from env: LLM_PROVIDER, LLM_MODEL,
# LLM_API_URL. Missing vars are filled in by detect-llm.sh.
#
# Output (plan):
#   plan/{n}/raw/architect:plan.md    — post-marker LLM body
#   plan/{n}.md                       — cleaned plan body
#   plan/{n}/                         — empty working dir
#   context/**/*                      — regenerated for the new iteration
#
# Output (review):
#   plan/{n}/raw/architect:review.md  — post-marker LLM body
#   plan/{n}/corrections-verdict.md   — architect's KEEP/DROP + cross-role (intermediate)
#   plan/{n}/corrections.md           — final merged corrections
#   plan/{n}/decisions.md             — appended new decisions
#   plan/{n}/approved.md              — if nothing to correct

set -euo pipefail

SKILL="${1:?Usage: architect/run.sh <skill> <iteration> [user_request]}"
ITERATION="${2:?}"
USER_INPUT="${3:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

eval "$(bash "${SCRIPT_DIR}/../detect-llm.sh")"

# plan needs plan/{n}/ to exist before call.sh writes the raw transcript into raw/
if [ "$SKILL" = "plan" ]; then
  mkdir -p "${REPO_ROOT}/v84-docs/plan/${ITERATION}/raw"
fi

# 1. Call LLM, save raw
bash "${SCRIPT_DIR}/call.sh" "$SKILL" "$ITERATION" "$USER_INPUT"

# 2. Parse raw → final artefact for the skill
case "$SKILL" in
  plan)
    bash "${SCRIPT_DIR}/plan-parse.sh" "$ITERATION"
    # Rebuild context for the new iteration so downstream agents can run
    bash "${SCRIPT_DIR}/../build-context.sh" "$ITERATION"
    ;;
  review)
    bash "${SCRIPT_DIR}/review-parse.sh" "$ITERATION"
    ;;
  *)
    echo "Unknown skill: ${SKILL}" >&2
    exit 1
    ;;
esac
