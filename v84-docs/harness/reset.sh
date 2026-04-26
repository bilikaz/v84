#!/bin/bash
#
# reset.sh — Wipe project state for a clean test run.
#
# By default, removes:
#     <project-root>/v84/         the project's state folder
#
# With --logs (or --all), also removes:
#     <project-root>/.v84-logs/   cached LLM request/response dumps
#
# The LLM config cache at ~/.config/v84/config.yaml is NOT touched;
# to forget the cached LLM URL, use:
#     python3 v84-docs/harness/v84.py --reset-llm
#
# The project root is resolved from this script's location, not CWD,
# so the script works regardless of where you invoke it from.

set -eu

# Resolve paths from the script's own location.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
V84_DOCS="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$V84_DOCS/.." && pwd)"

# Flags
RM_LOGS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --logs|--all)
      RM_LOGS=1
      ;;
    -h|--help)
      # Print the top comment block (stop at the first non-# line).
      awk 'NR==1 {next} /^#/ {sub(/^# ?/,""); print; next} {exit}' "$0"
      exit 0
      ;;
    *)
      echo "unknown flag: $1" >&2
      echo "usage: reset.sh [--logs|--all]" >&2
      exit 2
      ;;
  esac
  shift
done

STATE="$PROJECT_ROOT/v84"
LOGS="$PROJECT_ROOT/.v84-logs"

echo "project root: $PROJECT_ROOT"

if [ -e "$STATE" ]; then
  echo "→ removing $STATE"
  rm -rf "$STATE"
else
  echo "  no state folder at $STATE (already clean)"
fi

if [ "$RM_LOGS" -eq 1 ]; then
  if [ -e "$LOGS" ]; then
    echo "→ removing $LOGS"
    rm -rf "$LOGS"
  else
    echo "  no logs at $LOGS (already clean)"
  fi
fi

echo "✓ reset complete"
