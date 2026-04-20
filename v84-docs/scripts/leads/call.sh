#!/bin/bash

# Build lead prompt for one role, call LLM, save raw, parse.
#
# Usage: ./call.sh <role> <iteration>
#
# Provider / model / API URL come from env (set by leads/run.sh via
# detect-llm.sh → llm-api.sh reads them directly).

set -euo pipefail

ROLE="${1:?Usage: call.sh <role> <iteration>}"
ITERATION="${2:?}"
MAX_TOKENS="${MAX_TOKENS:-16000}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
CONTEXT_DIR="${REPO_ROOT}/v84-docs/context"
PLAN_DIR="${REPO_ROOT}/v84-docs/plan/${ITERATION}"
RAW_DIR="${PLAN_DIR}/raw"
STRUCTURE="${REPO_ROOT}/v84-docs/structure"
SKILLS_DIR="${REPO_ROOT}/v84-docs/agents/shared/skills"

source "${SCRIPT_DIR}/../llm-api.sh"

ROLE_PLAN_DIR="${PLAN_DIR}/${ROLE}"
RAW_FILE="${RAW_DIR}/${ROLE}:lead.md"
OUTPUT_FILE="${ROLE_PLAN_DIR}/lead.md"

mkdir -p "$RAW_DIR" "$ROLE_PLAN_DIR"

# Collect all drafts for this role
drafts=""
has_content=false
for f in "${ROLE_PLAN_DIR}"/*.md; do
  [ -f "$f" ] || continue
  [ -s "$f" ] || continue
  topic=$(basename "$f" .md)
  [ "$topic" = "lead" ] && continue
  has_content=true
  drafts="${drafts}
=== DRAFT [${ROLE}:${topic}] ===
$(cat "$f")
"
done

if [ "$has_content" = false ]; then
  echo "SKIP  ${ROLE} — no drafts"
  exit 0
fi

topics_file="${CONTEXT_DIR}/${ROLE}/topics.md"
conv_shared="${STRUCTURE}/conventions.md"
conv_role="${STRUCTURE}/conventions/${ROLE}.md"
skill_file="${SKILLS_DIR}/lead-review-inline.md"
plan_file="${REPO_ROOT}/v84-docs/plan/${ITERATION}.md"

system="=== YOUR SKILL ===
$(cat "$skill_file")

=== CONVENTIONS (shared) ===
$(cat "$conv_shared")

=== CONVENTIONS (${ROLE}) ===
$([ -f "$conv_role" ] && cat "$conv_role" || echo "(none)")

=== TOPIC SCOPES (${ROLE}) ===
$(cat "$topics_file")"

# Filter past corrections down to just this role's prior corrections so the
# lead can stay consistent across rounds (don't re-raise the same thing, don't
# flip-flop from round to round).
history_file="${PLAN_DIR}/logs/corrections-full.md"
role_history=""
if [ -s "$history_file" ]; then
  role_history=$(awk -v role="${ROLE}:" '
    /^# Round / { current_round = $0; in_role = 0; next }
    /^## \[/ {
      if ($0 ~ "^## \\[" role) { in_role = 1; printed_round = 0 }
      else { in_role = 0 }
      if (in_role && !printed_round && current_round != "") {
        print current_round
        print ""
        printed_round = 1
      }
    }
    in_role { print }
  ' "$history_file")
fi

user_msg="${drafts}

=== PLAN ===
$(cat "$plan_file")

=== YOUR ROLE'S PAST CORRECTIONS (this iteration, round by round) ===
$([ -n "$role_history" ] && echo "$role_history" || echo "(none yet — this is round 1 or your role hasn't been corrected)")"

response=$(call_llm_with_marker "$system" "${ROLE}-lead" "$user_msg")

# Save raw
printf '%s\n' "$response" > "$RAW_FILE"

# Parse
bash "${SCRIPT_DIR}/parse.sh" "$RAW_FILE" "$OUTPUT_FILE"
