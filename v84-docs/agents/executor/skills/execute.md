# Skill: Execute

> Implement tasks by writing actual code, config, and test files

## Your Context

Everything you need is provided to you — conventions, code patterns, source tree, installed packages, and tasks. The context file has it all.

Note: Unlike other agents, the executor DOES use tools — it reads and writes source files, runs commands, and verifies builds. This is the only skill that modifies the codebase.

## Parameters

- `resume-from:` (optional) — task tag to start from. All earlier tasks are assumed complete.

## How To Execute

- Tasks are grouped by plan tag with plan description as header
- Each task entry has:
  - `task:` — what to do (imperative)
  - `files:` — where to write
  - `depends:` — what must be done first
  - `needs:` — dependencies that should already be installed
  - `expands:` / `replaces:` — relationship to past code
- Work top to bottom. Check `depends:` before starting each task.

## How To Tag Code

Every function, class, component, config block gets tagged with both plan tag and role-topic:

```typescript
// [v84-1-1-2][back-nestjs:entities]
@Entity()
export class User { ... }
```

```yaml
# [v84-1-1-1][ops:infra]
services:
  api:
    build: ./api.Dockerfile
```

Rules:
- Tag on the line directly above the function/class/block
- Always include BOTH `[v84-tag]` and `[role-topic]`
- Use the comment syntax of the language
- **Aggregator files get one tag, not many.** When a barrel (`index.ts`), a page/component that composes several features, or any file that groups many re-exports is referenced by multiple plan nodes, put a single tag at the top of the file (pick the earliest/primary plan node). Per-declaration tags are only for files where each exported symbol has its own body — standalone functions in `api.ts`, schemas in `schemas.ts`, DTO classes, controllers — each of those gets its own tag above its block.

## Relationship Fields

- `expands:` — read existing code first, then add to it
- `replaces:` — remove or rewrite old code
- `depends:` — do not start until referenced task is done
- `needs:` — ops should have an install task. If not, flag it.

## Verify

After each logical group of tasks, verify the build passes. If it fails, fix before continuing.

## Running tests

**Always use `v84-docs/scripts/tests/run.sh`** to run tests. Do not improvise `pnpm test`, `docker compose exec ... jest`, `npx playwright test`, or any other ad-hoc invocation — the script sets up the isolated test stack, pre-creates bind-mount directories with correct ownership, streams logs to `test-results/`, writes a summary, and skips teardown on failure so state stays inspectable.

Pick the flag that matches what you need:

| Goal | Command |
|---|---|
| Smoke-test everything before wrapping an iteration | `v84-docs/scripts/tests/run.sh` (no args → full cycle: up → api → web → e2e → down) |
| Bring the stack up once and iterate on failures | `v84-docs/scripts/tests/run.sh --up` |
| Re-run one suite against the already-up stack | `v84-docs/scripts/tests/run.sh --test-api` / `--test-web` / `--test-e2e` |
| Tear the stack down when you're done | `v84-docs/scripts/tests/run.sh --down` |

Flags compose: `--up --test-api` brings the stack up and runs only the API suite; `--test-e2e --down` re-runs Playwright on a warm stack and tears down. Full details in `v84-docs/readme/dev-and-tests.md`.

If a test fails, read `test-results/summary.md` + the step's `.log` file before changing anything. The failing stack is still up (teardown skips on failure) so you can also `docker exec` into `test-api-1` / `test-db-1` to inspect live state.

## Generating the iteration migration

Migrations are **never** written as tasks in `plan/{N}/tasks.md`. One migration per iteration is generated as the last step of the execution phase, after every other task has been implemented and tagged. The dev stack is brought up just for this step and stopped again afterwards — don't leave it running beyond the migration.

Procedure for iteration `{N}`:

1. Confirm every other task in `plan/{N}/tasks.md` is done and its code is tagged.
2. Bring the dev stack up:
   ```
   v84-docs/scripts/dev/run.sh --up
   ```
3. Generate the migration inside the dev api container (migrations run against the dev DB, not the test stack):
   ```
   docker compose -f docker/dev/docker-compose.yml exec api \
     pnpm typeorm migration:generate src/database/migrations/iteration-{N} \
     -d src/database/data-source.ts
   ```
4. If TypeORM reports "no changes in database schema", no file is produced — that iteration has no entity deltas. Skip to step 6.
5. If a file is produced (e.g. `apps/api/src/database/migrations/1775911982357-iteration-{N}.ts`), add the iteration-level tag to its top:
   ```typescript
   // [v84-{N}][back-nestjs:entities]
   export class Iteration{N}1775911982357 implements MigrationInterface { ... }
   ```
6. Stop the dev stack:
   ```
   v84-docs/scripts/dev/run.sh --down
   ```
7. Do not touch `plan/{N}/tasks.md` — it already doesn't mention the migration, and shouldn't.

The name is always `iteration-{N}` — the timestamp prefix is TypeORM's; the `{N}` is the iteration number. One migration per iteration captures every entity change for that iteration in a single file.

## Rules

- Do not invent features not in the tasks
- Do not skip tagging — every block gets both tags
- Do not modify files outside what tasks specify
- Do not browse directories beyond what the tree shows — if it's not tagged, it may not exist yet
- Run `migration:generate src/database/migrations/iteration-{N}` exactly once per iteration, as the last step before `finish.sh`. Never add a migration task to `tasks.md`; never hand-pick a name other than `iteration-{N}`.
- Run tests through `v84-docs/scripts/tests/run.sh` (or its `--up` / `--test-*` / `--down` variants). Never fall back to raw `pnpm test`, `docker compose exec ... jest`, or `npx playwright test` — the script owns stack lifecycle, logging, and failure-preservation semantics.
