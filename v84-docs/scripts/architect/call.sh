#!/bin/bash

# Build architect prompt, call LLM, save raw response.
#
# Usage:
#   ./call.sh plan   <iteration> "<user request>"
#   ./call.sh review <iteration>

set -euo pipefail

SKILL="${1:?Usage: call.sh <skill> <iteration> [user_request]}"
ITERATION="${2:?}"
USER_INPUT="${3:-}"
MAX_TOKENS="${MAX_TOKENS:-50000}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
CONTEXT_DIR="${REPO_ROOT}/v84-docs/context"
PLAN_DIR="${REPO_ROOT}/v84-docs/plan/${ITERATION}"
RAW_DIR="${PLAN_DIR}/raw"
STRUCTURE="${REPO_ROOT}/v84-docs/structure"
AGENTS_DIR="${REPO_ROOT}/v84-docs/agents"
FINAL="${REPO_ROOT}/v84-docs/final"

source "${SCRIPT_DIR}/../llm-api.sh"

mkdir -p "$RAW_DIR"

# Build system message. The skill file is fully self-contained (identity,
# format, rules), so we don't prepend a separate agent.md — it was pure
# noise tokens. Skill + roles + shared conventions are enough.
skill_file="${AGENTS_DIR}/architect/skills/${SKILL}-inline.md"
roles_file="${STRUCTURE}/roles.md"
conv_shared="${STRUCTURE}/conventions.md"

system="=== YOUR SKILL ===
$(cat "$skill_file")

=== ROLES & TOPIC SCOPES ===
$(cat "$roles_file")

=== CONVENTIONS (shared) ===
$(cat "$conv_shared")"

# Build user sections
sections=()

sections+=("=== INSTALLED PACKAGES ===
$(cat "${CONTEXT_DIR}/architect/packages.md" 2>/dev/null || echo "(not generated)")")

plan_history="${FINAL}/plan.md"
sections+=("=== PLAN HISTORY ===
$([ -f "$plan_history" ] && cat "$plan_history" || echo "(no iterations completed yet)")")

case "$SKILL" in
  plan)
    if [ -z "$USER_INPUT" ]; then
      echo "ERROR: plan skill requires a user request as the 5th argument" >&2
      exit 1
    fi
    sections+=("=== USER REQUEST ===
${USER_INPUT}")
    ;;
  review)
    decisions_file="${PLAN_DIR}/decisions.md"
    sections+=("=== DECISIONS (settled — do NOT revisit) ===
$([ -f "$decisions_file" ] && cat "$decisions_file" || echo "(none yet)")")

    # Past verdicts from this iteration — full KEEP/DROP/cross-role history.
    # Lets the architect stay consistent across rounds:
    #   - KEEPs already got applied; don't re-raise the same fix as cross-role.
    #   - DROPs were explicitly rejected; don't re-raise them as cross-role now.
    #   - Cross-role corrections already got applied; verify against current
    #     DRAFTS before re-emitting.
    history_file="${PLAN_DIR}/logs/verdicts-full.md"
    sections+=("=== YOUR PAST VERDICTS (this iteration, round by round) ===
$([ -s "$history_file" ] && cat "$history_file" || echo "(none yet — this is round 1)")")

    plan_file="${REPO_ROOT}/v84-docs/plan/${ITERATION}.md"
    sections+=("=== PLAN ===
$(cat "$plan_file")")

    # Drafts from all roles
    drafts=""
    for role_dir in "${PLAN_DIR}"/*/; do
      [ -d "$role_dir" ] || continue
      role=$(basename "$role_dir")
      [ "$role" = "raw" ] && continue
      [ "$role" = "logs" ] && continue
      for f in "${role_dir}"/*.md; do
        [ -f "$f" ] || continue
        [ -s "$f" ] || continue
        topic=$(basename "$f" .md)
        [ "$topic" = "lead" ] && continue
        drafts="${drafts}
=== DRAFT [${role}:${topic}] ===
$(cat "$f")
"
      done
    done
    sections+=("$drafts")

    # Lead corrections — emit a section per role so the architect can tell
    # "all leads clean" from "leads didn't run". Clean leads have their lead.md
    # removed by leads/parse.sh, so a missing file means "reported CLEAN this
    # round" and we say so explicitly.
    leads=""
    for role_dir in "${PLAN_DIR}"/*/; do
      [ -d "$role_dir" ] || continue
      role=$(basename "$role_dir")
      [ "$role" = "raw" ] && continue
      [ "$role" = "logs" ] && continue
      lead_file="${role_dir}/lead.md"
      if [ -f "$lead_file" ] && [ -s "$lead_file" ]; then
        leads="${leads}
=== LEAD CORRECTIONS [${role}] ===
$(cat "$lead_file")
"
      else
        leads="${leads}
=== LEAD CORRECTIONS [${role}] ===
CLEAN — this lead reported no corrections this round.
"
      fi
    done
    sections+=("$leads")
    ;;
  *)
    echo "Unknown skill: ${SKILL}" >&2
    exit 1
    ;;
esac

echo "Architect: ${SKILL} for iteration ${ITERATION}"

response=$(call_llm_with_marker "$system" "architect-${SKILL}" "${sections[@]}")

# Save raw response
printf '%s\n' "$response" > "${RAW_DIR}/architect:${SKILL}.md"
echo "Raw saved: ${RAW_DIR}/architect:${SKILL}.md"
