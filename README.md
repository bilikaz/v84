# v84

A monorepo boilerplate + the **v84 documentation format** that lets AI agents plan, build, and maintain it. Backend is NestJS, frontend is Next.js (App Router), everything runs in Docker with Traefik `.localhost` routing. The `v84-docs/` tree carries a structured plan → review → execute pipeline so an AI agent can take a paragraph of intent and produce tagged, tested, reviewed code.

## Build the next feature with AI

Tell your AI assistant:

> **You are the executor agent. Read `v84-docs/agents/executor/agent.md` and run your `run` skill.**

The executor checks the pipeline state, asks what you want to build (or resumes an in-progress iteration), then drives everything: `scripts/architect/run.sh plan` → `scripts/cycle/run.sh` (draft → lead → architect review until APPROVED) → `scripts/executor/extract.sh` → implements the resulting tasks from `plan/{n}/tasks.md` → `scripts/executor/finish.sh`. You describe intent in plain text; the agent handles pipeline, code, migrations, tests, and tagging.

First time on a machine? Export your LLM creds once per shell (`LLM_API_URL`, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`) — see [v84-docs/readme/running-scripts.md](v84-docs/readme/running-scripts.md) for provider detection rules and examples.

Brand-new project (no `v84-docs/structure/` yet)? The executor's `init` skill runs a guided setup conversation first, then hands off to `run`.

## Quick start

```bash
v84-docs/scripts/dev/run.sh              # bring up the full dev stack
docker compose -f docker/dev/docker-compose.yml exec api pnpm --filter @v84/api seed
```

Dev URLs (all resolve via Traefik; on Windows + WSL2 add entries to `hosts`):

| Service | URL |
|---|---|
| Web app | http://web.localhost |
| API + Swagger | http://api.localhost/api/docs |
| Storybook | http://storybook.localhost |
| Mail catcher | http://mail.localhost |
| DB admin | http://adminer.localhost |
| Traefik dashboard | http://traefik.localhost |

Seed credentials: `admin@admin.localhost` / `user@user.localhost`, password `password`.

Tests, migrations, reset, and all other workflows: [**v84-docs/readme/dev-and-tests.md**](v84-docs/readme/dev-and-tests.md).

## Architecture

```
Browser → Next.js BFF (apps/web) → NestJS API (apps/api) → MariaDB / Redis / Mailpit
              ↕                          ↕
      opaque session cookie        JWT access + refresh tokens
      (httpOnly, sameSite=lax)     (never sent to browser)
```

- **BFF pattern** — the browser never sees an access token. Next.js route handlers in `apps/web/src/app/api/*` attach the upstream JWT server-side; the browser only holds an opaque session cookie keyed into in-memory storage.
- **Brand system** — visual identity in [`brand/tokens`](brand/), verbal identity in [`brand/copy`](brand/), shipped as dual ESM/CJS. Tailwind, email templates, Storybook, and the API all consume the same values.
- **Isolated test stack** — `docker/test/` is a parallel compose project (own DB / Redis / Mailpit) so integration tests never touch dev state.

## Working with the codebase

| What you want | Where to look |
|---|---|
| Bring dev up / down / reset / seed | [v84-docs/readme/dev-and-tests.md](v84-docs/readme/dev-and-tests.md) |
| Run tests (API + web + Playwright) | [v84-docs/readme/dev-and-tests.md](v84-docs/readme/dev-and-tests.md) |
| Generate an iteration migration | [v84-docs/readme/dev-and-tests.md](v84-docs/readme/dev-and-tests.md) |
| Shared conventions (naming, IDs, migrations, testing) | [v84-docs/structure/conventions.md](v84-docs/structure/conventions.md) |
| Per-role conventions | [v84-docs/structure/conventions/](v84-docs/structure/conventions/) |
| Environment variables | [docker/dev/.env.example](docker/dev/.env.example) |

## How the v84 documentation format works

v84 is the documentation layer that sits between "paragraph of user intent" and "tagged, tested code". Everything about the format itself — pipeline, agents, scripts, drift reports — lives under `v84-docs/`:

- [v84-docs/readme.md](v84-docs/readme.md) — format overview, tag syntax, grep cheatsheet.
- [v84-docs/readme/pipeline.md](v84-docs/readme/pipeline.md) — step-by-step execution order.
- [v84-docs/readme/running-scripts.md](v84-docs/readme/running-scripts.md) — invoke the pipeline from bash (any LLM provider).
- [v84-docs/readme/agents-guide.md](v84-docs/readme/agents-guide.md) — agent architecture and context bundling.
- [v84-docs/readme/directory.md](v84-docs/readme/directory.md) — full directory layout.

## Project layout

```
/
├── apps/
│   ├── api/              ← NestJS backend (TypeORM + MariaDB + Redis)
│   ├── web/              ← Next.js App Router + BFF
│   └── storybook/        ← Storybook host (ui primitives + email templates)
├── brand/                ← tokens (.mjs/.cjs/.d.ts) + copy + logos
├── docker/
│   ├── dev/              ← dev compose: Traefik, Adminer, Mailpit, hot reload
│   └── test/             ← isolated test stack
├── e2e/                  ← Playwright tests + helpers
├── test-results/         ← logs + summary from test runs (gitignored)
└── v84-docs/             ← the v84 documentation system
```

## Prerequisites

- Docker + Docker Compose
- Node.js 20+
- pnpm 9+

## License

MIT
