#!/bin/bash

# Promote approved entries from plan/{n}/ drafts into final/ stable docs.
# Run after executor finishes writing code and marks tasks done.
#
# Usage: ./v84-docs/scripts/executor/finish.sh <iteration> [--commit]
#
# For each plan/{n}/{role}/{topic}.md:
#   - Appends new entries to final/{role}/{topic}.md under iteration header
#   - Marks replaced entries (per `replaces:` references) with status line
# Also appends plan to final/plan.md.
#
# If --commit is passed, runs `git add . && git commit` at the end.
#
# This is the ONLY script that writes to final/.

set -euo pipefail

ITERATION="${1:?Usage: executor/finish.sh <iteration> [--commit]}"
COMMIT="${2:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
PLAN_DIR="${REPO_ROOT}/v84-docs/plan/${ITERATION}"
PLAN_FILE="${PLAN_DIR}.md"
FINAL_DIR="${REPO_ROOT}/v84-docs/final"

if [ ! -d "$PLAN_DIR" ]; then
  echo "Error: plan directory ${PLAN_DIR} does not exist" >&2
  exit 1
fi

promoted=0
replaced=0

for role_dir in "${PLAN_DIR}"/*/; do
  [ -d "$role_dir" ] || continue
  role=$(basename "$role_dir")
  case "$role" in
    raw|logs) continue ;;
  esac

  mkdir -p "${FINAL_DIR}/${role}"

  for file in "$role_dir"*.md; do
    [ -f "$file" ] || continue
    [ -s "$file" ] || continue
    topic=$(basename "$file" .md)
    [ "$topic" = "lead" ] && continue

    final_file="${FINAL_DIR}/${role}/${topic}.md"
    [ -f "$final_file" ] || touch "$final_file"

    # Handle replaces: references — mark old entries in final/
    replaces_refs=$(grep -oP '(?<=replaces: )\S+' "$file" 2>/dev/null || true)
    if [ -n "$replaces_refs" ]; then
      for ref in $replaces_refs; do
        ref_tag=$(echo "$ref" | sed 's/#.*//')
        ref_num=$(echo "$ref" | grep -oP '#\K.*' || echo "all")
        replacing_tag=$(grep -B1 "replaces: ${ref}" "$file" | head -1 | grep -oP '\[v84-[^\]]*\]' || echo "[v84-${ITERATION}]")

        if [ "$ref_num" = "all" ]; then
          sed -i "/^\[${ref_tag//\[/\\[}\]/a\\  status: replaced by ${replacing_tag} (iteration ${ITERATION})" "$final_file" 2>/dev/null || true
        else
          if grep -q "^\[${ref_tag//./\\.}\]#${ref_num}" "$final_file" 2>/dev/null; then
            sed -i "/^\[${ref_tag//\[/\\[}\]#${ref_num}/a\\  status: replaced by ${replacing_tag} (iteration ${ITERATION})" "$final_file" 2>/dev/null || true
            replaced=$((replaced + 1))
          fi
        fi
      done
    fi

    # Append new entries (skip status: removed)
    {
      echo ""
      echo "# --- iteration ${ITERATION} ---"
      current_entry=""
      is_removed=false

      while IFS= read -r line || [ -n "$line" ]; do
        if [[ "$line" =~ ^\[v84-[0-9] ]]; then
          if [ -n "$current_entry" ] && ! $is_removed; then
            echo "$current_entry"
            promoted=$((promoted + 1))
          fi
          current_entry="$line"
          is_removed=false
        elif [ -n "$current_entry" ]; then
          if [[ "$line" =~ ^[[:space:]]+status:[[:space:]]+removed ]]; then
            is_removed=true
          fi
          current_entry="${current_entry}
${line}"
        fi
      done < "$file"

      if [ -n "$current_entry" ] && ! $is_removed; then
        echo "$current_entry"
        promoted=$((promoted + 1))
      fi
    } >> "$final_file"

    echo "Promoted: ${role}/${topic}"
  done
done

# Append plan to final/plan.md
PLAN_HISTORY="${FINAL_DIR}/plan.md"
if [ -f "$PLAN_FILE" ]; then
  {
    echo ""
    echo "# --- iteration ${ITERATION} ---"
    cat "$PLAN_FILE"
  } >> "$PLAN_HISTORY"
  echo "Plan appended to: ${PLAN_HISTORY}"
fi

# Regenerate trees from tagged source code
if [ -f "${SCRIPT_DIR}/../generate-trees.sh" ]; then
  bash "${SCRIPT_DIR}/../generate-trees.sh" || true
fi

echo ""
echo "Done. Promoted ${promoted} entries, marked ${replaced} as replaced."
echo "Final: ${FINAL_DIR}/"

# Optional git commit
if [ "$COMMIT" = "--commit" ]; then
  cd "$REPO_ROOT"
  git add .
  git commit -m "v84-${ITERATION}: promoted ${promoted} entries" || true
  echo "Committed."
fi
