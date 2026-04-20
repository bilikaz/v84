#!/bin/bash

# Append round results to cycle logs.
#
# Usage: ./log.sh <iteration> <round>
#
# Output:
#   plan/{n}/logs/corrections-full.md — final corrections appended each round
#                                        (KEEPs + cross-role, i.e. what agents patched)
#   plan/{n}/logs/verdicts-full.md    — full architect verdict per round
#                                        (KEEP + DROP + cross-role), so next round's
#                                        architect can see its own prior rejections
#   plan/{n}/logs/corrections.md      — corrections + original entry text per entry
#   plan/{n}/logs/progress.md         — per-round tally: topic entries, lead
#                                        corrections, architect KEEP/DROP, cross-role

set -euo pipefail

ITERATION="${1:?Usage: log.sh <iteration> <round>}"
ROUND="${2:?Usage: log.sh <iteration> <round>}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
PLAN_DIR="${REPO_ROOT}/v84-docs/plan/${ITERATION}"
LOG_DIR="${PLAN_DIR}/logs"
CORRECTIONS="${PLAN_DIR}/corrections.md"

[ -f "$CORRECTIONS" ] || exit 0

mkdir -p "$LOG_DIR"

count=$(awk '/^(fix|remove|missing)/{c++} END{print c+0}' "$CORRECTIONS")
timestamp=$(date '+%Y-%m-%d %H:%M:%S')

# Full log — final corrections appended
{
  echo "# Round $ROUND — ${timestamp}"
  echo ""
  cat "$CORRECTIONS"
  echo ""
  echo "---"
  echo ""
} >> "${LOG_DIR}/corrections-full.md"

# Verdict log — KEEP/DROP/cross-role exactly as the architect wrote them, so
# future architect rounds can see what they already rejected (DROPs) and not
# re-raise them as new findings.
VERDICT_FILE="${PLAN_DIR}/corrections-verdict.md"
if [ -f "$VERDICT_FILE" ]; then
  {
    echo "# Round $ROUND — ${timestamp}"
    echo ""
    cat "$VERDICT_FILE"
    echo ""
    echo "---"
    echo ""
  } >> "${LOG_DIR}/verdicts-full.md"
fi

# Detailed log — corrections paired with original entries
{
  echo "# Round $ROUND — ${timestamp}"
  echo ""

  current_tag=""
  while IFS= read -r line; do
    if [[ "$line" =~ ^##\ \[([^\]]+)\] ]]; then
      current_tag="${BASH_REMATCH[1]}"
      echo "## [${current_tag}]"
      echo ""
      continue
    fi

    [[ -z "$line" ]] && continue

    role="${current_tag%%:*}"
    topic="${current_tag#*:}"
    draft_file="${PLAN_DIR}/${role}/${topic}.md"

    if [[ "$line" =~ ^(fix|remove)\ ?\[([^\]]+)\]#([0-9]+): ]]; then
      action="${BASH_REMATCH[1]}"
      vtag="${BASH_REMATCH[2]}"
      num="${BASH_REMATCH[3]}"

      echo "### ${action} [${vtag}]#${num}"
      echo ""

      if [ -f "$draft_file" ]; then
        entry=$(awk -v tag="[${vtag}]#${num} " '
          index($0, tag) { found=1; print; next }
          found && /^  / { print; next }
          found { exit }
        ' "$draft_file")
        if [ -n "$entry" ]; then
          echo '```'
          echo "$entry"
          echo '```'
        else
          echo "(entry not found in ${role}/${topic}.md)"
        fi
      else
        echo "(draft not found: ${role}/${topic}.md)"
      fi

      echo "**→** ${line}"
      echo ""

    elif [[ "$line" =~ ^missing: ]]; then
      echo "### missing (new entry)"
      echo "**→** ${line}"
      echo ""
    fi
  done < "$CORRECTIONS"

  echo "---"
  echo ""
} >> "${LOG_DIR}/corrections.md"

# Progress log — compact tally per round (toon format, ~ separator per convention)
{
  echo "# Round $ROUND — ${timestamp}"
  echo ""

  # Topic entries — count [v84-…]#N lines in each plan/{n}/{role}/{topic}.md
  echo "## Topic entries written"
  echo ""
  echo "topic ~ entries"
  total_entries=0
  for role_dir in "${PLAN_DIR}"/*/; do
    [ -d "$role_dir" ] || continue
    local_role=$(basename "$role_dir")
    [ "$local_role" = "raw" ] && continue
    [ "$local_role" = "logs" ] && continue
    for f in "${role_dir}"/*.md; do
      [ -f "$f" ] || continue
      topic=$(basename "$f" .md)
      [ "$topic" = "lead" ] && continue
      [ -s "$f" ] || continue
      n=$(awk '/^\[v84-/{c++} END{print c+0}' "$f")
      echo "${local_role}:${topic} ~ ${n}"
      total_entries=$((total_entries + n))
    done
  done
  echo "TOTAL ~ ${total_entries}"
  echo ""

  # Lead corrections — count fix/remove/missing in each plan/{n}/{role}/lead.md
  echo "## Lead corrections"
  echo ""
  echo "role ~ fix ~ remove ~ missing ~ total"
  total_lead=0
  for role_dir in "${PLAN_DIR}"/*/; do
    [ -d "$role_dir" ] || continue
    local_role=$(basename "$role_dir")
    [ "$local_role" = "raw" ] && continue
    [ "$local_role" = "logs" ] && continue
    lead_file="${role_dir}/lead.md"
    if [ -f "$lead_file" ] && [ -s "$lead_file" ]; then
      # awk returns 0 cleanly on no-match; grep -c exits 1 which breaks under set -e.
      fx=$(awk '/^fix /{c++} END{print c+0}' "$lead_file")
      rm=$(awk '/^remove /{c++} END{print c+0}' "$lead_file")
      ms=$(awk '/^missing/{c++} END{print c+0}' "$lead_file")
      tot=$((fx + rm + ms))
      echo "${local_role} ~ ${fx} ~ ${rm} ~ ${ms} ~ ${tot}"
      total_lead=$((total_lead + tot))
    else
      echo "${local_role} ~ 0 ~ 0 ~ 0 ~ 0"
    fi
  done
  echo "TOTAL ~ ~ ~ ~ ${total_lead}"
  echo ""

  # Architect verdict — from corrections-verdict.md (written before corrections.md)
  echo "## Architect verdict"
  echo ""
  verdict_file="${PLAN_DIR}/corrections-verdict.md"
  if [ -f "$verdict_file" ]; then
    keep_count=$(awk '/^KEEP /{c++} END{print c+0}' "$verdict_file")
    drop_count=$(awk '/^DROP /{c++} END{print c+0}' "$verdict_file")
    # Cross-role corrections = lines starting with fix/remove/missing appearing
    # AFTER the '### CROSS-ROLE CORRECTIONS' header (if present).
    cross_count=$(awk '
      /^### CROSS-ROLE CORRECTIONS/ { in_section=1; next }
      /^### / { in_section=0 }
      in_section && /^(fix|remove|missing)/ { c++ }
      END { print c+0 }
    ' "$verdict_file")
    echo "signal ~ count"
    echo "KEEP (lead corrections accepted) ~ ${keep_count}"
    echo "DROP (lead corrections rejected) ~ ${drop_count}"
    echo "CROSS-ROLE (new, added by architect) ~ ${cross_count}"
    echo "FINAL (merged into corrections.md) ~ ${count}"
  else
    echo "(no corrections-verdict.md — architect likely emitted APPROVED)"
  fi
  echo ""
  echo "---"
  echo ""
} >> "${LOG_DIR}/progress.md"

echo "Logged round $ROUND (${count} corrections)"
