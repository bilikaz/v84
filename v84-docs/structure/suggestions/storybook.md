# Suggestion: Storybook

## When

Every project that has a UI component library (packages/ui or similar). This is NOT optional.

## Rule

Every UI component MUST have a Storybook story. Components without stories are untestable in isolation and unverifiable during review. If a component exists in packages/ui, it gets a `.stories.tsx` file — no exceptions.

Storybook is the industry standard for component development. There is no acceptable alternative at this scale. Do NOT skip it, do NOT defer it to "later", do NOT treat it as nice-to-have.

When suggesting Storybook:
- Install the framework-specific packages: `@storybook/react` + `@storybook/react-vite` for React, `@storybook/vue3` + `@storybook/vue3-vite` for Vue, etc. Check `structure/stack.md` for the project's frontend framework — do NOT guess.
- It MUST be in packages/ui devDependencies
- It MUST have a Docker container with Traefik routing (`storybook.localhost`)
- It MUST be in stack.md under packages/ui
- Every component task in Phase 4 MUST include a corresponding `.stories.tsx` task
- See `patterns/storybook.md` for setup — NEVER run `storybook init` (interactive, hangs agents)

## Why

Components built without Storybook end up tested only through page integration — bugs hide until the full app runs. Storybook catches prop issues, edge cases, and visual regressions before they reach pages. Skipping it means shipping untested UI.
