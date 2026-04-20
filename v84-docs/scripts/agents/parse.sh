#!/bin/bash

# Extract clean output from a raw LLM response.
#
# The raw file already contains the post-marker, think-stripped body —
# call_llm_with_marker in llm-api.sh does that before the response is written
# to disk. Parse just filters blank lines and writes.
#
# Usage: ./parse.sh <raw_file> <output_file>
#
# Re-runnable: if the LLM call succeeded but extraction failed, rerun on the
# saved raw file without calling the LLM again.

set -euo pipefail

RAW_FILE="${1:?Usage: parse.sh <raw_file> <output_file>}"
OUTPUT_FILE="${2:?Usage: parse.sh <raw_file> <output_file>}"

if [ ! -f "$RAW_FILE" ]; then
  echo "ERROR: raw file not found: ${RAW_FILE}"
  exit 1
fi

NAME=$(basename "$RAW_FILE" .md)
clean=$(sed '/^[[:space:]]*$/d' "$RAW_FILE")

# Create output dir if needed
mkdir -p "$(dirname "$OUTPUT_FILE")"

if [ "$clean" = "(empty)" ] || [ -z "$clean" ] || [[ "$clean" == ERROR:* ]]; then
  printf "" > "$OUTPUT_FILE"
  echo "EMPTY ${NAME}"
else
  printf '%s\n' "$clean" > "$OUTPUT_FILE"
  entries=$(grep -c '^\[v84-' "$OUTPUT_FILE" 2>/dev/null || echo 0)
  echo "DONE  ${NAME} — ${entries} entries"
fi
