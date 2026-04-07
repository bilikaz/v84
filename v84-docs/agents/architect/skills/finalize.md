# Skill: Finalize

> Merge compare outputs into final.md and generate an ordered tasks.md for execution

## When To Use

After all 4 role agents have completed their compare step for iteration `{n}`.

## Steps

1. Read all 4 compare outputs at `/v84-docs/plan/{n}/{role-tag}-final.md`
2. Read `/v84-docs/structure/roles.md` for role and topic tags
3. Read `/v84-docs/structure/conventions.md` for naming rules
4. Read `/v84-docs/structure/stack.md` for installed packages (needed for scaffold phase)
5. Merge all role content into `/v84-docs/plan/{n}/final.md`
6. Generate `/v84-docs/plan/{n}/tasks.md` — single ordered file for the executor agent
7. Do not create directories — they already exist

## How To Build final.md

This file must be structured so it can later be split into 32 atomic files at `final/{role-tag}-{topic-tag}.md`.

- Keep the EXACT plan hierarchy from the compare outputs: ## [v84-1], ## [v84-1-1], etc.
- Keep ALL items with their `{role-tag}-{topic-tag}` tags: `- [back-nestjs-entities]`, `- [business-risk]`, `- [front-nextjs-components]`, etc.
- Do NOT reorganize by concern, topic, or any other structure — keep plan node order with tagged items under each node
- Do NOT drop role-topic tags — they are needed to route content to the 32 final files
- Do NOT summarize or consolidate items — copy them from the compare outputs
- Preserve all compare annotations: [reusable], [modify], [conflict], [extend], [large-scale]
- If there are cross-role contradictions, resolve them inline with [rejected] + resolved:
- The format is identical to resolved.md — plan hierarchy with role-topic tagged items

Example:
```
## [v84-1]
{plan description}

- [business-goals] {content}
- [business-risk] {content}
- [back-nestjs-entities] {content}
- [front-nextjs-pages] {content}
- [devops-qa-security] {content}

## [v84-1-1]
{plan description}

- [back-nestjs-arch] {content}
- [devops-qa-config] {content}
```

## How To Build tasks.md

A single ordered file executed by one agent top to bottom. No role tags — the executor does everything. Only things that produce code, config, or tests. No business analysis, no risk presumptions, no goals, no rollout plans — those stay in final.md.

The file must be SELF-CONTAINED — the executor reads ONLY tasks.md + conventions.md and can implement everything.

### What each task must include

- The `[v84-{n}-x-x]` tag the executor will stamp on the code
- Full implementation context from final.md — entity fields, API contracts, component specs, validation rules, resolved decisions, etc. Copy enough detail that the executor never has to guess.
- If a decision was resolved (e.g. "use `body` not `content`"), include the resolution so the executor knows WHY and can handle edge cases
- If this task's output is needed by a later task, note what the next task depends on (e.g. "the entity created here is used by the service in the next task")
- `task:` what to do
- `files:` where to write

### Phases

Order tasks in these phases. Each phase must complete before the next starts.

```
Phase 1: Scaffold
  Project init, pnpm workspace, package installs for all apps.
  Nothing else can happen until the project exists.
  verify: pnpm install succeeds, pnpm build succeeds, no errors

Phase 2: Infrastructure
  Docker Compose, Dockerfiles, CI pipeline, env config, git hooks.
  The dev environment must work before writing application code.
  verify: docker compose config validates, lint passes

Phase 3: Backend
  Entities, DTOs, services, controllers, API endpoints.
  NO migrations here — entities only. Migrations are generated in Phase 5.
  verify: pnpm --filter api build succeeds, pnpm --filter api lint succeeds

Phase 4: Frontend
  Pages, components, forms, fetching, state, styling.
  Depends on backend API contracts from Phase 3.
  verify: pnpm --filter web build succeeds, pnpm --filter web lint succeeds

Phase 5: Database
  Spin up db container, generate migrations from entities, run migrations,
  create factories and seeders, run seeds. DevOps responsibility.
  All entities must exist before this phase — migrations are generated from entity diffs.
  run: docker compose -f docker/dev/docker-compose.yml up -d db
  run: pnpm typeorm migration:generate — one per logical entity group
  run: pnpm typeorm migration:run
  task: create factories for entities marked [needs-seed]
  task: create seeders with realistic dev data
  run: pnpm seed
  verify: db container running, migrations applied, seed data present

Phase 6: Tests
  Unit tests, integration tests, e2e tests, visual regression.
  Tests verify what was built in Phases 3-4. DB has schema and test data from Phase 5.
  verify: pnpm --filter api test succeeds, pnpm --filter web test succeeds

Phase 7: Polish
  Accessibility improvements, performance optimizations, documentation.
  Final touches after everything works.
  verify: full pnpm build + pnpm lint + pnpm test from root — all green
```

Each phase MUST end with a verify task. The verify task uses `run:` to execute the check commands. If verification fails, the executor must fix the issues before moving to the next phase.

### Task format

Tasks have two action types:
- `run:` — execute a shell command (installs, scaffolding, migrations, build commands)
- `task:` — write or modify a file

Both can appear in the same task. `run:` commands execute first, then `task:` writes files.

```
## Phase 1: Scaffold

### [v84-1-1] Initialize pnpm workspace
task: create pnpm-workspace.yaml listing apps/api, apps/web, packages/ui
files: pnpm-workspace.yaml
run: pnpm install

### [v84-1-1] Scaffold NestJS backend
run: mkdir -p apps/api && cd apps/api && pnpm init
run: cd apps/api && pnpm add @nestjs/core @nestjs/common @nestjs/platform-express @nestjs/typeorm @nestjs/swagger @nestjs/throttler typeorm class-validator class-transformer uuid pino mariadb
run: cd apps/api && pnpm add -D @nestjs/cli @nestjs/testing typescript @types/node
task: create main.ts, app.module.ts, tsconfig.json with NestJS bootstrap
files: apps/api/src/main.ts, apps/api/src/app.module.ts, apps/api/tsconfig.json
note: this creates the app structure that Phase 3 tasks write into

## Phase 3: Backend

### [v84-1-2] Create Message entity
context: Message stores a secret left by a user. Fields:
  - id: int, PK, auto-increment (internal only, never exposed in API)
  - key: varchar(36), UUID v4 via uuid.v4(), unique indexed (sole lookup path, the only access control)
  - body: text (the secret message, max 5000 chars enforced by DTO not column)
  - createdAt: datetime, TypeORM @CreateDateColumn
  resolved: field is called "body" not "content" — all roles aligned on this
task: create entity with TypeORM decorators
files: apps/api/src/messages/message.entity.ts
note: the service in the next task imports this entity

```

Phase 5 example (Database):
```
## Phase 5: Database

### [v84-1-2] Generate and run migrations
run: docker compose -f docker/dev/docker-compose.yml up -d db
run: pnpm typeorm migration:generate database/migrations/CreateMessageTable -d database/data-source.ts
run: pnpm typeorm migration:run -d database/data-source.ts
note: migration is GENERATED from entity diff, never hand-written

### [v84-1-2] Create Message factory and seed
task: create factory with sensible defaults and overrides
files: database/factories/message.factory.ts
task: create demo seeder with test data
files: database/seeds/demo.seeder.ts
task: update database/factories/index.ts barrel export
files: database/factories/index.ts
run: pnpm seed
```

### What goes into tasks.md

- Scaffolding (project init, package installs) — ALWAYS Phase 1
- Infrastructure (Docker, CI, env config, workspace setup)
- Backend code (entities, DTOs, migrations, services, controllers)
- Frontend code (pages, components, forms, fetching, styling)
- Tests (unit, integration, e2e, visual regression)
- Performance and accessibility work

### What does NOT go into tasks.md

- Business goals, stories, stakeholders — that's reporting, not code
- Risk assessments — decision-making context, stays in final.md
- Compliance notes — documentation, not implementation
- Market analysis — strategy, not tasks
- Rollout plans — deployment decisions, not code
- DevOps observations that don't produce files (e.g. "plaintext storage is accepted risk")

### Handling later iterations

For iteration 1, all tasks are "create". For later iterations:
- `[modify]` tasks include what exists and what changes: `modifies [v84-{prev}-x-x]`
- `[extend]` tasks include what exists and what's added: `extends [v84-{prev}-x-x]`
- `[replace]` tasks reference old and new: `[v84-{n}-x-x] replaces [v84-{prev}-x-x]`
- `[reusable]` items are NOT tasks — skip them. But if a task depends on a reusable item, mention it in the `note:` field.

## What NOT To Do

- Do not invent new v84 tags — only use tags that exist in the architect's plan (e.g. [v84-1-1], [v84-1-2]). Never create sub-tags like [v84-1-1-001] that don't exist in the plan. Multiple tasks can share the same tag — that's expected.
- Do not include non-executable items (goals, risks, market analysis) in tasks.md
- Do not use role tags in tasks — the executor is role-agnostic, it just follows the order
- Do not create directories — they already exist
- Do not search or read source code
- Do not skip the scaffold phase — even if the plan doesn't mention it, projects need initialization
- Do not leave out resolved decisions — include them as `resolved:` lines so the executor knows the reasoning
- Any item marked `[new-dependency-install]` in compare outputs MUST become a `run:` task in Phase 1: Scaffold. Package installs always happen before the code that uses them. If the dependency is a Docker image, it goes into Phase 2: Infrastructure instead.
- Any item marked `[needs-container]` MUST get a Docker service task in Phase 2: Infrastructure — including Dockerfile (if needed), docker-compose service entry, and Traefik labels with a `.localhost` domain. A runnable tool without a container does not exist in dev.
- Entity tasks go in Phase 3 (Backend) — code only, NO migrations. Migrations and seeds go in Phase 5 (Database) after all entities exist. This is because migrations are generated from entity diffs and need the db container running.
- Phase 5 MUST generate migrations via `pnpm typeorm migration:generate` — NEVER hand-write migration SQL.
- Phase 5 MUST create factories and seeders for entities marked `[needs-seed]` in assess. User-facing entities (accounts, spins, posts) almost always need seeds. Internal entities (tokens, settings) usually don't.
- Phase 2: Infrastructure MUST include a package.json script for seed running (e.g. `"seed": "ts-node database/seed-runner.ts"`).
