#!/bin/bash

# Parse architect's raw plan response into plan/{n}.md.
#
# The raw file already contains the post-marker, think-stripped body —
# call_llm_with_marker in llm-api.sh does that before the response is written
# to disk. Parse only drops code fences and trims blank lines, then writes.
#
# Steps:
#   1. Drop any code fences the model wrapped around the plan
#   2. Trim leading/trailing blank lines (keep interior blanks — plan format
#      uses them between [v84-*] blocks)
#   3. Write cleaned plan to plan/{n}.md
#   4. Ensure plan/{n}/ working directory exists
#
# Usage: ./plan-parse.sh <iteration>

set -euo pipefail

ITERATION="${1:?Usage: plan-parse.sh <iteration>}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
PLAN_DIR="${REPO_ROOT}/v84-docs/plan/${ITERATION}"
RAW_FILE="${PLAN_DIR}/raw/architect:plan.md"
PLAN_FILE="${REPO_ROOT}/v84-docs/plan/${ITERATION}.md"

if [ ! -f "$RAW_FILE" ]; then
  echo "ERROR: raw file not found: ${RAW_FILE}" >&2
  exit 1
fi

# Drop any code fences the model might wrap the plan in
clean=$(sed -E '/^```[a-zA-Z]*$/d; /^```$/d' "$RAW_FILE")

# Trim leading/trailing blank lines
clean=$(printf '%s\n' "$clean" | awk 'NF{found=1} found{print}' | tac | awk 'NF{found=1} found{print}' | tac)

if [ -z "$clean" ]; then
  echo "ERROR: parsed plan is empty — check ${RAW_FILE}" >&2
  exit 1
fi

printf '%s\n' "$clean" > "$PLAN_FILE"
mkdir -p "$PLAN_DIR"

line_count=$(wc -l < "$PLAN_FILE" | tr -d ' ')
echo "Plan written: ${PLAN_FILE} (${line_count} lines)"
echo "Working dir:  ${PLAN_DIR}"
