#!/bin/bash

# Run topic agents for an iteration.
# Orchestrates: build context → discover agents → parallel LLM calls → extract results.
#
# Usage:
#   ./v84-docs/scripts/agents/run.sh <iteration> [skill] [agent1,agent2,...]
#
# skill:  draft (default) — all active topics
#         patch — only agents with corrections
#
# Provider / model / API URL come from env: LLM_PROVIDER, LLM_MODEL,
# LLM_API_URL. Missing vars are filled in by detect-llm.sh.
#
# Output:
#   plan/{n}/raw/{role}:{topic}.md  — post-marker LLM body
#   plan/{n}/{role}/{topic}.md      — clean entries only
#
# Environment knobs:
#   LLM_API_KEY, MAX_PARALLEL (30), MAX_TOKENS (50000), DELAY (0)

set -euo pipefail

ITERATION="${1:?Usage: agents/run.sh <iteration> [skill] [only]}"
SKILL="${2:-draft}"
ONLY="${3:-}"
MAX_PARALLEL="${MAX_PARALLEL:-30}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
CONTEXT_DIR="${REPO_ROOT}/v84-docs/context"
PLAN_DIR="${REPO_ROOT}/v84-docs/plan/${ITERATION}"
RAW_DIR="${PLAN_DIR}/raw"

eval "$(bash "${SCRIPT_DIR}/../detect-llm.sh")"

mkdir -p "$PLAN_DIR" "$RAW_DIR"

echo "v84 Agent Runner"
echo "Iteration: ${ITERATION}"
echo "LLM:       ${LLM_PROVIDER} @ ${LLM_API_URL} → ${LLM_MODEL}"
echo "Parallel:  ${MAX_PARALLEL}"
echo ""

# Draft starts fresh
if [ "$SKILL" = "draft" ]; then
  for d in "${PLAN_DIR}"/*/; do
    [ -d "$d" ] && rm -rf "$d"
  done
  mkdir -p "$RAW_DIR"
  echo "Cleared: ${PLAN_DIR}/"
fi

# Build context
bash "${SCRIPT_DIR}/../build-context.sh" "$ITERATION"

# Collect agents
agents=()
if [ "$SKILL" = "patch" ]; then
  if [ ! -f "${PLAN_DIR}/corrections.md" ]; then
    echo "No corrections.md found — nothing to patch"
    exit 0
  fi
  while IFS= read -r line; do
    if [[ "$line" =~ ^##\ \[([^\]]+)\] ]]; then
      tag="${BASH_REMATCH[1]}"
      found=false
      for existing in "${agents[@]+"${agents[@]}"}"; do
        [ "$existing" = "$tag" ] && found=true && break
      done
      $found || agents+=("$tag")
    fi
  done < "${PLAN_DIR}/corrections.md"
elif [ -n "$ONLY" ]; then
  IFS=',' read -ra agents <<< "$ONLY"
else
  for role_dir in "${CONTEXT_DIR}"/*/; do
    [ -d "$role_dir" ] || continue
    local_role=$(basename "$role_dir")
    [ "$local_role" = "architect" ] && continue
    [ "$local_role" = "executor" ] && continue
    for topic_dir in "${role_dir}"/*/; do
      [ -d "$topic_dir" ] || continue
      [ -f "${topic_dir}/identity.md" ] || continue
      agents+=("${local_role}:$(basename "$topic_dir")")
    done
  done
fi

echo "Launching ${#agents[@]} agents..."
echo ""

# Parallel execution — track PIDs to detect failures
DELAY="${DELAY:-0}"
declare -A pids
running=0
for agent_tag in "${agents[@]}"; do
  role="${agent_tag%%:*}"
  topic="${agent_tag#*:}"
  bash "${SCRIPT_DIR}/call.sh" "$role" "$topic" "$ITERATION" "$SKILL" &
  pids[$!]="$agent_tag"
  running=$((running+1))

  if [ "$DELAY" -gt 0 ] 2>/dev/null; then
    sleep "$DELAY"
  fi

  if [ "$running" -ge "$MAX_PARALLEL" ]; then
    wait -n 2>/dev/null || wait
    running=$((running-1))
  fi
done

# Wait for all, collect failures
failed=()
for pid in "${!pids[@]}"; do
  if ! wait "$pid"; then
    failed+=("${pids[$pid]}")
  fi
done

echo ""
if [ ${#failed[@]} -gt 0 ]; then
  echo "FAILED: ${failed[*]}"
  echo "  Raw:   ${RAW_DIR}/"
  exit 1
else
  echo "All agents complete (${SKILL})."
  echo "  Raw:   ${RAW_DIR}/"
  echo "  Clean: ${PLAN_DIR}/{role}/{topic}.md"
fi

echo ""

# Patch cleanup
if [ "$SKILL" = "patch" ]; then
  [ -f "${PLAN_DIR}/corrections.md" ] && rm "${PLAN_DIR}/corrections.md" && echo "Deleted: corrections.md"
fi
