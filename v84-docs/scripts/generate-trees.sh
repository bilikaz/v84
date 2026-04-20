#!/bin/bash

# Generate role-specific source trees from tagged files only.
# Only files containing [v84-*] tags appear in the tree.
# This reflects the cumulative state after all completed iterations.
#
# Usage: ./v84-docs/scripts/generate-trees.sh
# Output: v84-docs/trees/{role}.tree + full.tree
#
# For a full unfiltered tree (ignoring tags), use generate-trees-full.sh

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TREES_DIR="${REPO_ROOT}/v84-docs/trees"

# Find all files with v84 code tags
# Matches: // [v84-   # [v84-   /* [v84-   -- [v84-
# This excludes markdown links like [v84-docs/...] and tool call logs
find_tagged_files() {
  grep -rlP '(//|#|/\*|--) \[v84-\d' "$REPO_ROOT" \
    --include="*.ts" --include="*.tsx" --include="*.js" --include="*.mjs" --include="*.cjs" \
    --include="*.mdx" \
    --include="*.css" --include="*.yml" --include="*.yaml" \
    --include="*.Dockerfile" --include="Dockerfile" \
    --include="*.example" \
    2>/dev/null \
    | grep -v node_modules \
    | grep -v .next \
    | grep -v dist \
    | grep -v coverage \
    | grep -v v84-docs \
    | grep -v pnpm-lock \
    | sed "s|^${REPO_ROOT}/||" \
    | sort
}

# Role path filters — which directories each role cares about
match_role() {
  local role="$1"
  local file="$2"

  case "$role" in
    back-nestjs)
      [[ "$file" == apps/api/* || "$file" == brand/* || "$file" == docker/dev/* || "$file" == docker/test/* ]] ;;
    front-nextjs)
      [[ "$file" == apps/web/* || "$file" == apps/storybook/* || "$file" == brand/* || "$file" == e2e/* ]] ;;
    ops)
      [[ "$file" == docker/* || "$file" == .github/* || "$file" == apps/api/test/* || "$file" == apps/web/src/__tests__/* || "$file" == e2e/* ]] ;;
    reviewer)
      # Reviewer sees everything
      return 0 ;;
    *)
      return 1 ;;
  esac
}

generate_tree() {
  local role="$1"
  local output="${TREES_DIR}/${role}.tree"

  {
    echo "# ${role} tree — auto-generated from tagged files"
    echo "# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "# Only files containing [v84-*] tags are listed"
    echo ""

    find_tagged_files | while read -r file; do
      if match_role "$role" "$file"; then
        echo "$file"
      fi
    done
  } > "$output"

  local count=$(grep -c '^[^#]' "$output" 2>/dev/null || echo 0)
  echo "Generated: ${output} (${count} files)"
}

# Generate per-role trees
for role in back-nestjs front-nextjs ops reviewer; do
  generate_tree "$role"
done

# Full tree — all tagged files
{
  echo "# full tree — auto-generated from tagged files"
  echo "# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# Only files containing [v84-*] tags are listed"
  echo ""
  find_tagged_files
} > "${TREES_DIR}/full.tree"

full_count=$(grep -c '^[^#]' "${TREES_DIR}/full.tree" 2>/dev/null || echo 0)
echo "Generated: ${TREES_DIR}/full.tree (${full_count} files)"
echo ""
echo "All trees generated from tagged files."
