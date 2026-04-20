#!/bin/bash

# Parse a lead's raw response into clean corrections.
#
# The raw file already contains the post-marker, think-stripped body —
# call_llm_with_marker in llm-api.sh does that before the response is written
# to disk. Parse filters blank lines, checks for APPROVED, and writes the
# output file (empty for clean, populated for corrections).
#
# Usage: ./parse.sh <raw_file> <output_file>
#
# Re-runnable: if the LLM call succeeded but parse failed, rerun on the saved
# raw file without calling the LLM again.

set -euo pipefail

RAW_FILE="${1:?Usage: parse.sh <raw_file> <output_file>}"
OUTPUT_FILE="${2:?Usage: parse.sh <raw_file> <output_file>}"

if [ ! -f "$RAW_FILE" ]; then
  echo "ERROR: raw file not found: ${RAW_FILE}"
  exit 1
fi

NAME=$(basename "$RAW_FILE" .md)
clean=$(sed '/^[[:space:]]*$/d' "$RAW_FILE")

mkdir -p "$(dirname "$OUTPUT_FILE")"

if [ -z "$clean" ] || [[ "$clean" =~ ^[[:space:]]*APPROVED[[:space:]]*$ ]]; then
  # Remove any stale lead.md from previous round
  rm -f "$OUTPUT_FILE"
  echo "OK    ${NAME} — all drafts clean"
else
  printf '%s\n' "$clean" > "$OUTPUT_FILE"
  count=$(grep -cE '^(fix|remove|missing)' "$OUTPUT_FILE" 2>/dev/null || echo 0)
  echo "FOUND ${NAME} — ${count} corrections"
fi
