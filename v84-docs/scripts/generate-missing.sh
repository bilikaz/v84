#!/bin/bash

# Generate plan-vs-code coverage report.
# Parse `files:` entries in each plan's tasks.md, check which ones don't exist
# on disk, then list every [v84-*] tagged source file that no plan references.
#
# Usage:
#   ./v84-docs/scripts/generate-missing.sh            — all iterations
#     → v84-docs/plan/missing.md
#   ./v84-docs/scripts/generate-missing.sh <N>        — only iteration N
#     → v84-docs/plan/<N>/missing.md

set -euo pipefail

ITERATION="${1:-}"

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PLANS_DIR="${REPO_ROOT}/v84-docs/plan"

if [ -n "$ITERATION" ]; then
  if [ ! -f "${PLANS_DIR}/${ITERATION}/tasks.md" ]; then
    echo "ERROR: no tasks.md at plan/${ITERATION}/" >&2
    exit 1
  fi
  OUTPUT="${PLANS_DIR}/${ITERATION}/missing.md"
  PLANS_TO_SCAN=("${PLANS_DIR}/${ITERATION}/tasks.md")
else
  OUTPUT="${PLANS_DIR}/missing.md"
  PLANS_TO_SCAN=("${PLANS_DIR}"/*/tasks.md)
fi

# ── collect plan file lists ───────────────────────────────────────────────

# Extract all files listed in a plan's tasks.md. Splits comma-separated
# lists, trims whitespace, strips the trailing "(optional)" or comments.
# Placeholders like `{timestamp}-foo.ts` are left as-is so they surface as
# "missing" and can be reconciled manually.
plan_files() {
  local tasks="$1"
  # Accept both formats:
  #   files: a.ts, b.ts           (single-line, comma-separated)
  #   files: a.ts                 (multi-line continuation — extra paths on
  #          b.ts                  subsequent indented lines, no directive
  #          c.ts)                 prefix)
  awk '
    /^[[:space:]]*files:/ {
      line = $0
      sub(/^[[:space:]]*files:[[:space:]]*/, "", line)
      split_and_emit(line)
      collecting = 1
      next
    }
    collecting && /^[[:space:]]+[^[:space:]]/ && \
      !/^[[:space:]]*(task|depends|needs|expands|replaces):/ {
      line = $0
      sub(/^[[:space:]]+/, "", line); sub(/[[:space:]]+$/, "", line)
      split_and_emit(line)
      next
    }
    { collecting = 0 }
    function split_and_emit(s,    n, arr, i, p) {
      n = split(s, arr, /,/)
      for (i = 1; i <= n; i++) {
        p = arr[i]
        sub(/^[[:space:]]+/, "", p); sub(/[[:space:]]+$/, "", p)
        if (p != "") print p
      }
    }
  ' "$tasks" | sort -u
}

# ── collect tagged source files ───────────────────────────────────────────

tagged_files() {
  grep -rlP '(//|#|/\*|\{/\*|--) \[v84-\d' "$REPO_ROOT" \
    --include="*.ts" --include="*.tsx" \
    --include="*.js" --include="*.mjs" --include="*.cjs" \
    --include="*.mdx" \
    --include="*.css" --include="*.yml" --include="*.yaml" \
    --include="*.Dockerfile" --include="Dockerfile" \
    --include="*.example" \
    2>/dev/null \
    | grep -v node_modules \
    | grep -v '\.next' \
    | grep -v '/dist/' \
    | grep -v '/coverage/' \
    | grep -v '/v84-docs/' \
    | grep -v pnpm-lock \
    | sed "s|^${REPO_ROOT}/||" \
    | sort -u
}

# Same file-type filters as tagged_files(), scoped to the executor's target
# folders (apps/, docker/, e2e/, brand/) and inverted with -rL to list files
# WITHOUT any [v84-*] tag. Surfaces boilerplate and support files still waiting
# to be wired into the tagging system.
untagged_files() {
  local roots=()
  for dir in apps docker e2e brand; do
    [ -d "${REPO_ROOT}/${dir}" ] && roots+=("${REPO_ROOT}/${dir}")
  done
  [ ${#roots[@]} -eq 0 ] && return 0
  grep -rLP '(//|#|/\*|\{/\*|--) \[v84-\d' "${roots[@]}" \
    --include="*.ts" --include="*.tsx" \
    --include="*.js" --include="*.mjs" --include="*.cjs" \
    --include="*.mdx" \
    --include="*.css" --include="*.yml" --include="*.yaml" \
    --include="*.Dockerfile" --include="Dockerfile" \
    --include="*.example" \
    2>/dev/null \
    | grep -v node_modules \
    | grep -v '\.next' \
    | grep -v '/dist/' \
    | grep -v '/coverage/' \
    | sed "s|^${REPO_ROOT}/||" \
    | sort -u
}

# ── build report ──────────────────────────────────────────────────────────

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

tagged_files > "$TMPDIR/tagged.txt"
untagged_files > "$TMPDIR/untagged.txt"

# The "tagged-but-not-in-plan" section always checks across ALL iterations —
# otherwise a file tagged in iter-1 would falsely look "missing from plan" when
# we scope the report to iter-3. Missing-on-disk is scoped; this denominator
# is not.
: > "$TMPDIR/all-plan.txt"
for t in "${PLANS_DIR}"/*/tasks.md; do
  [ -f "$t" ] || continue
  plan_files "$t" >> "$TMPDIR/all-plan.txt"
done

{
  echo "# Plan-vs-code coverage"
  echo
  echo "_Generated on $(date -u +%Y-%m-%dT%H:%M:%SZ) by \`v84-docs/scripts/generate-missing.sh\`._"
  echo
  echo "Drift buckets between every \`plan/{N}/tasks.md\` and the current repo:"
  echo
  echo "1. **Exists but not tagged** (per iteration) — plan file is already on disk; the executor just needs to add its \`[v84-*][role:topic]\` tag."
  echo "2. **Missing on disk** (per iteration) — plan references a path that doesn't exist (typos, renames, placeholders, or invented paths)."
  echo "3. **Missing from plans** — \`[v84-*]\`-tagged source files that no plan references (implied / support files, or plan gaps)."
  echo "4. **Untagged source files** — files in the executor's target folders that carry no \`[v84-*]\` tag (everything still awaiting tagging)."
  echo

  for tasks in "${PLANS_TO_SCAN[@]}"; do
    [ -f "$tasks" ] || continue
    iter="$(basename "$(dirname "$tasks")")"

    plan_files "$tasks" > "$TMPDIR/plan-$iter.txt"

    echo "## Iteration $iter — files in plan but exist and are not tagged"
    echo
    echo "Boilerplate already on disk for these files — the executor just needs to add the \`[v84-*][role:topic]\` tag."
    echo
    exists_untagged_count=0
    while IFS= read -r file; do
      [ -z "$file" ] && continue
      if [ -e "${REPO_ROOT}/${file}" ] && grep -qxF "$file" "$TMPDIR/untagged.txt"; then
        echo "- \`${file}\`"
        exists_untagged_count=$((exists_untagged_count + 1))
      fi
    done < "$TMPDIR/plan-$iter.txt"

    if [ "$exists_untagged_count" -eq 0 ]; then
      echo "_No plan files in this bucket — every plan file is either tagged or missing._"
    fi
    echo

    echo "## Iteration $iter — files in plan and missing on disk"
    echo
    echo "Plan references a path that doesn't exist — typo, rename, placeholder, or an invented path the agents couldn't verify against the code."
    echo
    missing_count=0
    while IFS= read -r file; do
      [ -z "$file" ] && continue
      if [ ! -e "${REPO_ROOT}/${file}" ]; then
        echo "- \`${file}\`"
        missing_count=$((missing_count + 1))
      fi
    done < "$TMPDIR/plan-$iter.txt"

    if [ "$missing_count" -eq 0 ]; then
      echo "_All plan files exist on disk._"
    fi
    echo
  done

  sort -u "$TMPDIR/all-plan.txt" > "$TMPDIR/all-plan-unique.txt"

  echo "## Tagged files not referenced by any plan"
  echo
  echo "Source files carrying a \`[v84-*]\` tag that no plan's \`files:\` line names."
  echo "These are usually support wiring (sub-barrels, guard wrappers, helper services) or plan-coverage gaps."
  echo
  extra_count=0
  while IFS= read -r file; do
    [ -z "$file" ] && continue
    if ! grep -qxF "$file" "$TMPDIR/all-plan-unique.txt"; then
      echo "- \`${file}\`"
      extra_count=$((extra_count + 1))
    fi
  done < "$TMPDIR/tagged.txt"

  if [ "$extra_count" -eq 0 ]; then
    echo "_Every tagged file is named in a plan._"
  fi
  echo

  echo "## Untagged source files (apps/, docker/, e2e/, brand/)"
  echo
  echo "Source files in the executor's target folders that carry no \`[v84-*]\` tag."
  echo "Pre-existing boilerplate or support files still waiting to be wired into the tagging system."
  echo
  untagged_count=0
  while IFS= read -r file; do
    [ -z "$file" ] && continue
    echo "- \`${file}\`"
    untagged_count=$((untagged_count + 1))
  done < "$TMPDIR/untagged.txt"

  if [ "$untagged_count" -eq 0 ]; then
    echo "_Every source file in these folders is tagged._"
  fi
  echo
} > "$OUTPUT"

# ── summary to stdout ─────────────────────────────────────────────────────

total_plan="$(wc -l < "$TMPDIR/all-plan-unique.txt" | tr -d ' ')"
total_tagged="$(wc -l < "$TMPDIR/tagged.txt" | tr -d ' ')"
total_untagged="$(wc -l < "$TMPDIR/untagged.txt" | tr -d ' ')"
echo "Wrote ${OUTPUT}"
echo "  plan files: ${total_plan}"
echo "  tagged source files: ${total_tagged}"
echo "  untagged source files: ${total_untagged}"
