# Suggestions

Default recommendations the architect uses during init when suggesting tech stack and tooling. Each file contains a suggestion rule that applies when certain conditions are met.

## How to maintain

- Add a suggestion file when you want the architect to always recommend something
- Each file should specify: when it applies, what to suggest, and why
- Update or remove files when preferences change
- These are defaults — the user can always override during init

## Available suggestions

Condition ~ File
nextjs ~ suggestions/nextjs.md
storybook ~ suggestions/storybook.md
traefik ~ suggestions/traefik.md
mariadb ~ suggestions/mariadb.md
pnpm ~ suggestions/pnpm.md
tailwind-css ~ suggestions/tailwind-css.md
jest ~ suggestions/jest.md
vitest ~ suggestions/vitest.md
playwright ~ suggestions/playwright.md
