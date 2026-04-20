#!/bin/bash

# Parse architect's raw review response into final corrections.md.
#
# Steps:
#   1. Strip thinking block (<think>...</think>)
#   2. Extract content after ====== MY RESPONSE ======
#   3. Split off ### DECISIONS → append to decisions.md, strip from verdict
#   4. Apply DROP verdicts to lead corrections
#   5. Append cross-role corrections
#   6. Write final plan/{n}/corrections.md
#
# Usage: ./parse.sh <iteration>
#
# Re-runnable: if the LLM call succeeded but parse failed,
# run this on the saved raw file without calling the LLM again.

set -euo pipefail

ITERATION="${1:?Usage: parse.sh <iteration>}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
PLAN_DIR="${REPO_ROOT}/v84-docs/plan/${ITERATION}"
RAW_FILE="${PLAN_DIR}/raw/architect:review.md"
VERDICT_FILE="${PLAN_DIR}/corrections-verdict.md"
CORRECTIONS_FILE="${PLAN_DIR}/corrections.md"
DECISIONS_FILE="${PLAN_DIR}/decisions.md"
APPROVED_FILE="${PLAN_DIR}/approved.md"

if [ ! -f "$RAW_FILE" ]; then
  echo "ERROR: raw file not found: ${RAW_FILE}"
  exit 1
fi

# The raw file already contains the post-marker, think-stripped body —
# call_llm_with_marker in llm-api.sh does that before the response is written
# to disk. Parse only filters blank lines here.
clean=$(sed '/^[[:space:]]*$/d' "$RAW_FILE")

# Capture whether the architect explicitly said APPROVED anywhere in the
# response. Used below as one of two required signals to exit the cycle —
# the other is zero merged corrections. Requiring BOTH prevents a silent
# approval on a failed / empty LLM call.
approved_keyword=false
if grep -qE '(^|[[:space:]])APPROVED([[:space:]]|$)' <<< "$clean"; then
  approved_keyword=true
fi

# Fast path — the clean body contains nothing but APPROVED (classic happy case).
if [[ "$clean" =~ ^[[:space:]]*APPROVED[[:space:]]*$ ]]; then
  echo "APPROVED" > "$APPROVED_FILE"
  echo "APPROVED — no corrections needed"
  exit 0
fi

# Save verdict (KEEP/DROP + cross-role)
echo "$clean" > "$VERDICT_FILE"

# Extract decisions → append to decisions.md, strip from verdict
if grep -q '^### DECISIONS' "$VERDICT_FILE"; then
  sed -n '/^### DECISIONS/,$ p' "$VERDICT_FILE" | tail -n +2 >> "$DECISIONS_FILE"
  echo "" >> "$DECISIONS_FILE"
  sed -i '/^### DECISIONS/,$ d' "$VERDICT_FILE"
  echo "Decisions extracted to: ${DECISIONS_FILE}"
fi

# Build final corrections.md:
# 1. Start with all lead corrections
# 2. Remove any the architect DROPped
# 3. Append cross-role corrections
{
  # Collect DROP patterns from verdict
  declare -a drop_patterns=()
  while IFS= read -r line; do
    if [[ "$line" =~ ^DROP\ \[([^\]]+)\]\ (fix|remove|missing)\ ?(.*) ]]; then
      drop_patterns+=("${BASH_REMATCH[1]}|${BASH_REMATCH[2]}|${BASH_REMATCH[3]}")
    fi
  done < "$VERDICT_FILE"

  # Output lead corrections, skipping DROPped ones
  # Buffer per-header so empty sections (all corrections dropped) are omitted
  for role_dir in "${PLAN_DIR}"/*/; do
    [ -d "$role_dir" ] || continue
    role=$(basename "$role_dir")
    [ "$role" = "raw" ] && continue
    [ "$role" = "logs" ] && continue
    lead_file="${role_dir}/lead.md"
    [ -f "$lead_file" ] && [ -s "$lead_file" ] || continue

    current_tag=""
    buffer=""
    has_content=false

    flush() {
      if [ -n "$current_tag" ] && [ "$has_content" = true ]; then
        echo "## [${current_tag}]"
        printf '%s' "$buffer"
      fi
    }

    while IFS= read -r line; do
      if [[ "$line" =~ ^##\ \[([^\]]+)\] ]]; then
        flush
        current_tag="${BASH_REMATCH[1]}"
        buffer=""
        has_content=false
      elif [ -n "$current_tag" ] && [[ "$line" =~ ^(fix|remove|missing) ]]; then
        dropped=false
        for dp in "${drop_patterns[@]+"${drop_patterns[@]}"}"; do
          dp_tag="${dp%%|*}"
          rest="${dp#*|}"
          dp_action="${rest%%|*}"
          if [ "$dp_tag" = "$current_tag" ] && [[ "$line" == ${dp_action}* ]]; then
            dropped=true
            break
          fi
        done
        if ! $dropped; then
          buffer+="${line}
"
          has_content=true
        fi
      fi
    done < "$lead_file"

    flush
  done

  # Append cross-role corrections
  if grep -q '^### CROSS-ROLE CORRECTIONS' "$VERDICT_FILE"; then
    sed -n '/^### CROSS-ROLE CORRECTIONS/,$ p' "$VERDICT_FILE" | tail -n +2 | sed '/^### /,$ d' | sed '/^[[:space:]]*$/d'
  fi

} > "$CORRECTIONS_FILE"

kept_count=$(grep -cE '^(fix|remove|missing)' "$CORRECTIONS_FILE" 2>/dev/null || echo 0)
dropped_count=${#drop_patterns[@]}
echo "Corrections: ${kept_count} kept, ${dropped_count} dropped"
echo "Written to: ${CORRECTIONS_FILE}"

# Dual-signal approval: BOTH the architect said APPROVED AND the merged
# corrections file is empty. Either signal alone is not enough — the architect
# might forget the keyword while issuing a real fix, and a failed LLM call
# might produce an empty corrections.md without ever saying APPROVED.
if [ "$approved_keyword" = true ] && [ "$kept_count" = "0" ]; then
  echo "APPROVED" > "$APPROVED_FILE"
  echo "APPROVED — architect keyword + zero merged corrections"
fi
