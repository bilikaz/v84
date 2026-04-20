#!/bin/bash

# Build per-agent context files:
#   - {role}/packages.md                — one per role (from package.json)
#   - {role}/{topic}/identity.md        — composed from roles.md
#   - {role}/{topic}/corrections.md     — extracted from corrections.md (if exists)
#
# Usage: ./v84-docs/scripts/build-context.sh {n}
# Output: v84-docs/context/{role}/{topic}/{identity,corrections}.md
#         v84-docs/context/{role}/packages.md
#         v84-docs/context/architect/packages.md

set -euo pipefail

ITERATION="${1:?Usage: build-context.sh <iteration-number>}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PLAN_DIR="${REPO_ROOT}/v84-docs/plan/${ITERATION}"
STRUCTURE="${REPO_ROOT}/v84-docs/structure"
CONTEXT_DIR="${REPO_ROOT}/v84-docs/context"
ROLES_FILE="${STRUCTURE}/roles.md"
CORRECTIONS="${PLAN_DIR}/corrections.md"

API_PKG="${REPO_ROOT}/apps/api/package.json"
WEB_PKG="${REPO_ROOT}/apps/web/package.json"
ROOT_PKG="${REPO_ROOT}/package.json"

# Fresh start
rm -rf "$CONTEXT_DIR"
mkdir -p "$CONTEXT_DIR"

# --- Package helpers ---

list_pkgs() {
  local file="$1" field="$2"
  [ -f "$file" ] || return 0
  jq -r --arg f "$field" '.[$f] // {} | to_entries[] | "- \(.key) @ \(.value)"' "$file" 2>/dev/null
}

workspace_section() {
  local label="$1" file="$2"
  [ -f "$file" ] || return 0
  local deps dev_deps
  deps=$(list_pkgs "$file" "dependencies")
  dev_deps=$(list_pkgs "$file" "devDependencies")
  echo "## ${label}"
  echo ""
  if [ -n "$deps" ]; then
    echo "### dependencies"
    echo ""
    echo "$deps"
    echo ""
  fi
  if [ -n "$dev_deps" ]; then
    echo "### devDependencies"
    echo ""
    echo "$dev_deps"
    echo ""
  fi
}

packages_for_role() {
  local role="$1" out="$2"
  {
    echo "# Installed Packages — ${role}"
    echo ""
    case "$role" in
      back-nestjs)
        workspace_section "apps/api" "$API_PKG"
        workspace_section "root (monorepo)" "$ROOT_PKG"
        ;;
      front-nextjs)
        workspace_section "apps/web" "$WEB_PKG"
        workspace_section "root (monorepo)" "$ROOT_PKG"
        ;;
      ops|reviewer|architect|executor)
        workspace_section "root (monorepo)" "$ROOT_PKG"
        workspace_section "apps/api" "$API_PKG"
        workspace_section "apps/web" "$WEB_PKG"
        ;;
    esac
  } > "$out"
}

# --- Parse roles.md ---

declare -A role_names
declare -A role_pkg_done
declare -A role_topics

while IFS= read -r line; do
  if [[ "$line" =~ ^[a-z][a-z0-9-]*[[:space:]]*~ ]] && [[ $(echo "$line" | awk -F' ~ ' '{print NF}') -eq 2 ]]; then
    tag=$(echo "$line" | awk -F' ~ ' '{print $1}' | xargs)
    role_names["$tag"]=$(echo "$line" | awk -F' ~ ' '{print $2}' | xargs)
  fi
done < "$ROLES_FILE"

current_role=""
count=0

while IFS= read -r line; do
  if [[ "$line" =~ ^###[[:space:]]+(.*) ]]; then
    heading="${BASH_REMATCH[1]}"
    current_role=""
    for tag in "${!role_names[@]}"; do
      if [ "${role_names[$tag]}" = "$heading" ]; then
        current_role="$tag"
        break
      fi
    done
    continue
  fi

  [ -z "$current_role" ] && continue

  if [[ "$line" =~ ^[a-z][a-z0-9-]*[[:space:]]*~ ]]; then
    topic_tag=$(echo "$line" | awk -F' ~ ' '{print $1}' | xargs)
    [ "$topic_tag" = "-" ] && continue

    topic_name=$(echo "$line" | awk -F' ~ ' '{print $2}' | sed 's/^ *//;s/ *$//')
    topic_scope=$(echo "$line" | awk -F' ~ ' '{print $3}' | sed 's/^ *//;s/ *$//')
    topic_not=$(echo "$line" | awk -F' ~ ' '{print $4}' | sed 's/^ *//;s/ *$//')
    agent_tag="${current_role}:${topic_tag}"
    role_dir="${CONTEXT_DIR}/${current_role}"
    topic_dir="${role_dir}/${topic_tag}"
    mkdir -p "$topic_dir"

    # packages — once per role
    if [ -z "${role_pkg_done[$current_role]:-}" ]; then
      packages_for_role "$current_role" "${role_dir}/packages.md"
      role_pkg_done["$current_role"]=1
    fi

    # accumulate topic scopes for this role
    role_topics["$current_role"]+="${line}
"

    # identity
    {
      echo "Role: ${role_names[$current_role]}, {role_tag}: ${current_role}"
      echo "Topic: ${topic_name}, {topic_tag}: ${topic_tag}"
      echo "{agent_tag}: ${agent_tag}"
      echo "Scope: ${topic_scope}"
      [ -n "$topic_not" ] && echo "${topic_not}"
    } > "${topic_dir}/identity.md"

    # corrections for this agent (if any).
    # Extract the block from "## [agent_tag]" header up to (but NOT including)
    # the next "## [..." header, or to EOF. awk handles both cases cleanly —
    # the old sed approach used '$d' to drop the trailing header line, which
    # accidentally dropped the body instead when the section was at EOF.
    if [ -f "$CORRECTIONS" ]; then
      section=$(awk -v tag="## [${agent_tag}]" '
        $0 == tag { in_section = 1; print; next }
        in_section && /^## \[/ { exit }
        in_section { print }
      ' "$CORRECTIONS")
      if [ -n "$section" ]; then
        echo "$section" > "${topic_dir}/corrections.md"
      fi
    fi

    count=$((count+1))
  fi
done < "$ROLES_FILE"

# --- Write topics.md per role ---

for role in "${!role_topics[@]}"; do
  printf '%s' "${role_topics[$role]}" > "${CONTEXT_DIR}/${role}/topics.md"
done

# --- Architect + executor ---

mkdir -p "${CONTEXT_DIR}/architect"
packages_for_role "architect" "${CONTEXT_DIR}/architect/packages.md"

mkdir -p "${CONTEXT_DIR}/executor"
packages_for_role "executor" "${CONTEXT_DIR}/executor/packages.md"

echo "Prepared: ${CONTEXT_DIR}/"
echo "Agents: ${count} (+ architect, executor)"
