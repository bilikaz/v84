# Suggestion: pnpm Workspaces

## When

Every monorepo project, regardless of size.

## Rule

Always suggest pnpm as the package manager with workspaces enabled. Never suggest npm or yarn for monorepo setups.

## Why

Fast installs, disk-efficient, strict mode prevents phantom dependencies. The default for AI-agent built projects where reliability matters.