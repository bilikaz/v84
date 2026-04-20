#!/bin/bash

# Run one agent: build prompt, call LLM, save raw, extract clean.
#
# Usage: ./call.sh <role> <topic> <iteration> <skill>
#
# Provider / model / API URL come from env (set by agents/run.sh via
# detect-llm.sh → llm-api.sh reads them directly).
#
# Reads from context/{role}/{topic}/ and writes to plan/{n}/raw/ and plan/{n}/{role}/

set -euo pipefail

ROLE="${1:?Usage: call.sh <role> <topic> <iteration> <skill>}"
TOPIC="${2:?}"
ITERATION="${3:?}"
SKILL="${4:?}"
MAX_TOKENS="${MAX_TOKENS:-50000}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
CONTEXT_DIR="${REPO_ROOT}/v84-docs/context"
PLAN_DIR="${REPO_ROOT}/v84-docs/plan/${ITERATION}"
RAW_DIR="${PLAN_DIR}/raw"
SKILLS_DIR="${REPO_ROOT}/v84-docs/agents/shared/skills"

source "${SCRIPT_DIR}/../llm-api.sh"

AGENT_TAG="${ROLE}:${TOPIC}"
TOPIC_DIR="${CONTEXT_DIR}/${ROLE}/${TOPIC}"
SKILL_FILE="${SKILLS_DIR}/${SKILL}-inline.md"
ROLE_OUT_DIR="${PLAN_DIR}/${ROLE}"
OUTPUT_FILE="${ROLE_OUT_DIR}/${TOPIC}.md"
RAW_FILE="${RAW_DIR}/${AGENT_TAG}.md"

if [ ! -d "$TOPIC_DIR" ]; then
  echo "SKIP ${AGENT_TAG} — no context dir"
  exit 0
fi

mkdir -p "$ROLE_OUT_DIR" "$RAW_DIR"

# Source paths
IDENTITY="${TOPIC_DIR}/identity.md"
CORRECTIONS="${TOPIC_DIR}/corrections.md"
CONV_SHARED="${REPO_ROOT}/v84-docs/structure/conventions.md"
CONV_ROLE="${REPO_ROOT}/v84-docs/structure/conventions/${ROLE}.md"
TREE="${REPO_ROOT}/v84-docs/trees/${ROLE}.tree"
PACKAGES="${CONTEXT_DIR}/${ROLE}/packages.md"
HISTORY="${REPO_ROOT}/v84-docs/final/${ROLE}/${TOPIC}.md"
PLAN_FILE="${REPO_ROOT}/v84-docs/plan/${ITERATION}.md"

# System message
system="=== YOU ARE ===
$(cat "$IDENTITY")

=== YOUR SKILL ===
$(cat "$SKILL_FILE")

=== CONVENTIONS ===
$(cat "$CONV_SHARED")
$(cat "$CONV_ROLE")"

# User message sections
sections=()
sections+=("=== SOURCE TREE ===
$(cat "$TREE")")
sections+=("=== INSTALLED PACKAGES ===
$(cat "$PACKAGES")")
sections+=("=== TOPIC HISTORY ===
$([ -s "$HISTORY" ] && cat "$HISTORY" || echo "(empty — first iteration for this topic)")")
sections+=("=== PLAN ===
$(cat "$PLAN_FILE")")

# Patch: include current draft + corrections
if [ "$SKILL" = "patch" ]; then
  sections+=("=== YOUR CURRENT DRAFT ===
$(cat "$OUTPUT_FILE")")
  sections+=("=== CORRECTIONS (for you) ===
Fix these issues in your draft.

$(cat "$CORRECTIONS")")
fi

# Call LLM
response=$(call_llm_with_marker "$system" "${AGENT_TAG}-${SKILL}" "${sections[@]}")

# Save raw
printf '%s\n' "$response" > "$RAW_FILE"

# Extract clean
bash "${SCRIPT_DIR}/parse.sh" "$RAW_FILE" "$OUTPUT_FILE"
