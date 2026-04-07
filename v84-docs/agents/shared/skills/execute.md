# Skill: Execute

> Implement all tasks from tasks.md in order, writing actual code/config/test files

## Parameters

- `resume-from:` (optional) — phase number to start from (e.g. `5`). All earlier phases are assumed complete. If not provided, starts from Phase 1. Set by the orchestrator when resuming after interruption.

## Steps

1. Read `/v84-docs/structure/conventions.md` — naming rules, patterns, error handling
2. Read `/v84-docs/structure/patterns.md` — check which pattern files exist
3. Read `/v84-docs/plan/{n}/tasks.md` — ordered task list with all context
4. Before implementing a task, check if a relevant pattern file exists in `/v84-docs/structure/patterns/` — if it does, read it and follow the patterns exactly
5. If `resume-from:` is set, skip to that phase. Otherwise start from Phase 1.
6. Work through tasks top to bottom — phases are pre-sorted by dependency
7. For each task, write the actual files at the specified paths
8. Tag every piece of code with its `[v84-{n}-x-x]` tag
9. After completing ALL tasks in a phase and passing verify, update state.md

## How To Execute

- Tasks are ordered by phase: Scaffold → Infrastructure → Backend → Frontend → Database → Tests → Polish
- Each task can have two action types:
  - `run:` — execute this shell command (installs, scaffolding, migrations, builds). Run these FIRST before writing files.
  - `task:` — write or modify a file. Do this AFTER any `run:` commands in the same task complete.
- `context:` has full implementation details, `resolved:` explains WHY decisions were made
- `note:` explains dependencies on other tasks
- `files:` tells you where to write
- Follow conventions.md strictly — naming, patterns, barrel exports, error handling

## How To Track Progress

After completing ALL tasks in a phase and passing the verify step, update `/v84-docs/state.md`:

```
phase: 4-frontend
phase-status: running
phases-done: 1-scaffold, 2-infrastructure, 3-backend
```

Do NOT mark tasks or phases in tasks.md — state.md is the single source of truth for progress.
Always update state.md before moving to the next phase — this is the crash recovery mechanism.

## How To Tag Code

Every function, class, component, config block, migration, test gets tagged:

```typescript
// [v84-1-2]
@Entity()
export class Message { ... }
```

```tsx
// [v84-1-2]
export function MessageForm() { ... }
```

```yaml
# [v84-1-1]
services:
  api:
    build: ./api.Dockerfile
```

Rules:
- Tag goes on the line directly above the function/class/block
- Use the most specific (deepest) v84 tag from the task
- Use the comment syntax of the language you're in
- If a block serves multiple tasks, use the parent tag that covers both

## What To Do With Compare Flags

- `[reusable]` — already exists, works as-is. Import/use it, don't rewrite.
- `[modify]` — exists but needs changes. Update it, change the v84 tag to the new iteration.
- `[extend]` — exists, add to it. Keep existing code, add the new piece.
- `[large-scale]` — proceed with caution, used in many places.

## How To Handle Verify Steps

Each phase ends with a verify task that runs checks (lint, build, test). If verification fails:
1. Read the error output
2. Fix the issue in the files you wrote — do not skip or ignore errors
3. Re-run the verify command until it passes
4. Only then mark the verify task [done] and move to the next phase

Do NOT proceed to the next phase if the current phase's verify step fails.

## What NOT To Do

- Do not invent features not in the tasks — implement exactly what's specified
- Do not skip tagging — every block of code gets its v84 tag
- Do not modify files outside what the tasks specify
- Do not reorder tasks — the phase order is intentional
- Do not skip verify steps — they are gates between phases
- Do not proceed to the next phase if verify fails — fix first
