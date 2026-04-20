#!/bin/bash

# Nuke `final/` and re-run `finish.sh` for every iteration in order. Use after
# hand-editing plan drafts (adding entries, fixing paths, renaming tags) so
# the promoted history in `final/` reflects the current drafts exactly.
#
# Not the same as running `finish.sh N` on its own — that APPENDS to final/,
# which is right while the pipeline runs but leaves stale entries after a
# draft edit. This script is the one-button "replay the whole history".
#
# Iterations are discovered from `plan/{n}.md` files (same pattern the script
# already uses) and run in numeric order.
#
# Usage:
#   v84-docs/scripts/executor/finish-all.sh              replay all iterations
#   v84-docs/scripts/executor/finish-all.sh --commit     pass --commit to each

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
PLANS_DIR="${REPO_ROOT}/v84-docs/plan"
FINAL_DIR="${REPO_ROOT}/v84-docs/final"

COMMIT_FLAG=""
for arg in "$@"; do
  case "$arg" in
    --commit) COMMIT_FLAG="--commit" ;;
    -h|--help)
      sed -n '3,16p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      echo "Run '$0 --help' for usage." >&2
      exit 2
      ;;
  esac
done

iterations=()
for f in "${PLANS_DIR}"/*.md; do
  [ -f "$f" ] || continue
  name="$(basename "$f" .md)"
  [[ "$name" =~ ^[0-9]+$ ]] || continue
  iterations+=("$name")
done

if [ ${#iterations[@]} -eq 0 ]; then
  echo "No plan/{n}.md files found — nothing to promote." >&2
  exit 1
fi

# Numeric sort so 10 comes after 9. mapfile keeps IFS untouched, so the
# later "${iterations[*]}" expansions space-separate cleanly.
mapfile -t iterations < <(printf '%s\n' "${iterations[@]}" | sort -n)

echo "Rebuilding final/ from ${#iterations[@]} iteration(s): ${iterations[*]}"
rm -rf "$FINAL_DIR"

for n in "${iterations[@]}"; do
  echo ""
  echo "=== finish.sh $n ${COMMIT_FLAG} ==="
  bash "${SCRIPT_DIR}/finish.sh" "$n" ${COMMIT_FLAG}
done

echo ""
echo "============================================"
echo "Rebuilt final/ across iterations: ${iterations[*]}"
echo "============================================"
