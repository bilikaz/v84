#!/bin/bash

# Run lead reviews — one per role, in parallel.
# Each lead reviews its department's drafts against conventions and topic scopes.
#
# Usage: ./v84-docs/scripts/leads/run.sh <iteration>
#
# Provider / model / API URL come from env: LLM_PROVIDER, LLM_MODEL,
# LLM_API_URL. Missing vars are filled in by detect-llm.sh.
#
# Output:
#   plan/{n}/raw/{role}:lead.md     — post-marker LLM body
#   plan/{n}/{role}/lead.md         — clean corrections only

set -euo pipefail

ITERATION="${1:?Usage: leads/run.sh <iteration>}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
CONTEXT_DIR="${REPO_ROOT}/v84-docs/context"

eval "$(bash "${SCRIPT_DIR}/../detect-llm.sh")"

# Discover roles from context dirs
roles=()
for d in "${CONTEXT_DIR}"/*/; do
  [ -d "$d" ] || continue
  name=$(basename "$d")
  [ "$name" = "architect" ] && continue
  [ "$name" = "executor" ] && continue
  roles+=("$name")
done

echo "Lead Review — iteration ${ITERATION}"
echo "Roles: ${roles[*]}"
echo "LLM:   ${LLM_PROVIDER} @ ${LLM_API_URL} → ${LLM_MODEL}"
echo ""

# Run leads in parallel, track failures
declare -A pids
for role in "${roles[@]}"; do
  bash "${SCRIPT_DIR}/call.sh" "$role" "$ITERATION" &
  pids[$!]="$role"
done

failed=()
for pid in "${!pids[@]}"; do
  if ! wait "$pid"; then
    failed+=("${pids[$pid]}")
  fi
done

echo ""
if [ ${#failed[@]} -gt 0 ]; then
  echo "FAILED leads: ${failed[*]}"
  exit 1
else
  echo "Lead reviews complete."
fi
