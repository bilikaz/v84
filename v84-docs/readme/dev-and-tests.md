# Running the Dev Stack and Tests

> Two thin wrappers around `docker compose` so you don't have to memorise flags or docker-compose paths. Both use the same "no args = sensible default, flags for specific steps" pattern.

## Dev stack — `v84-docs/scripts/dev/run.sh`

Everything local developers need. No args starts the stack and prints URLs.

| Command | What it does |
|---|---|
| `v84-docs/scripts/dev/run.sh` | Start the full dev stack (same as `--up`) and print the `.localhost` URLs. |
| `v84-docs/scripts/dev/run.sh --up` | Same, explicitly. |
| `v84-docs/scripts/dev/run.sh --down` | Stop services but **keep** volumes (MariaDB rows, Redis keys, captured mail). Safe on exit. |
| `v84-docs/scripts/dev/run.sh --reset` | Stop and **wipe** volumes — equivalent to `docker compose down -v`. Use when you want a fresh DB or seed state. |
| `v84-docs/scripts/dev/run.sh --rebuild` | Rebuild every image, then start. Use after `pnpm install` adds new native deps or when a Dockerfile changes. |
| `v84-docs/scripts/dev/run.sh --logs` | Follow the compose logs until Ctrl-C. |
| `v84-docs/scripts/dev/run.sh --status` | `docker compose ps` equivalent. |

On first successful `--up` you'll see a printout like:

```
Web app            http://web.localhost
API + Swagger      http://api.localhost/api/docs
Storybook          http://storybook.localhost
Mail catcher       http://mail.localhost
DB admin           http://adminer.localhost
Traefik dashboard  http://traefik.localhost
```

All of `*.localhost` resolves to `127.0.0.1` on modern macOS / Linux; on Windows + WSL2 you may need `127.0.0.1 web.localhost api.localhost …` entries in `C:\Windows\System32\drivers\etc\hosts`.

Every step writes its full output to `test-results/dev-{up,down,rebuild,reset}.log`, so if a build fails or a healthcheck never flips you can read the post-mortem without re-running.

### Seeding the dev database

Dev doesn't seed on startup — run it manually once the stack is up:

```bash
docker compose -f docker/dev/docker-compose.yml exec api pnpm --filter @v84/api seed
```

Credentials: `admin@admin.localhost` / `user@user.localhost`, password `password`.

### Generating a migration

Last step of an iteration's execution phase. Stack is brought up just for this and stopped right after — don't leave it running.

```bash
v84-docs/scripts/dev/run.sh --up
docker compose -f docker/dev/docker-compose.yml exec api \
  pnpm typeorm migration:generate src/database/migrations/iteration-{N} \
  -d src/database/data-source.ts
# tag the generated file's first line: // [v84-{N}][back-nestjs:entities]
v84-docs/scripts/dev/run.sh --down
```

The name is always `iteration-{N}`. If TypeORM reports "no changes in database schema", skip the tag step — no file is produced and that's fine.

## Test suite — `v84-docs/scripts/tests/run.sh`

One-shot runner for the **isolated** test stack (`docker/test/docker-compose.yml`) — completely separate from dev: own containers, own volumes, own port namespace. No args = full cycle: up → API → Web unit → Playwright e2e → down.

| Command | What it does |
|---|---|
| `v84-docs/scripts/tests/run.sh` | Full cycle. Stack up, every suite, stack down, summary to `test-results/summary.md`. |
| `v84-docs/scripts/tests/run.sh --up` | Just bring the test stack up and leave it running. |
| `v84-docs/scripts/tests/run.sh --down` | Just tear it down (including volume wipe). |
| `v84-docs/scripts/tests/run.sh --test-api` | Re-run API integration suite against an already-up stack — useful while iterating on one test. |
| `v84-docs/scripts/tests/run.sh --test-web` | Re-run web unit suite (Vitest inside the web container). |
| `v84-docs/scripts/tests/run.sh --test-e2e` | Re-run Playwright e2e in the ephemeral `e2e` container. |

Flags compose. Common patterns:

- `run.sh --up --test-api` — bring stack up and run only API tests, leaving the stack running so you can re-run after a fix.
- `run.sh --test-e2e --down` — re-run e2e on a live stack and then tear down.
- `run.sh --up` then edit/run/edit repeatedly with `--test-e2e`, finish with `run.sh --down`.

### Where each suite runs

| Suite | Runs inside | Why |
|---|---|---|
| API integration | `test-api-1` container (`pnpm test`) | Needs real MariaDB + Redis + Mailpit — Jest hits them over the compose network. |
| Web unit | `test-web-1` container (`vitest run`) | Same Node version and `node_modules` as the Next.js app — no host/container drift. |
| Playwright e2e | ephemeral `test-e2e-1` container (`npx playwright test`) | Official Playwright image already has Chromium + its system deps. Drives `test-web-1` over the compose network. |

### Failure behaviour

If any step fails, `run.sh` **skips the teardown** — the stack stays up so you can inspect state. You'll see a hint:

```
Skipping teardown — earlier step(s) failed.
Stack left up so you can inspect state (Redis keys, DB rows, captured email).
Tear it down manually once done: v84-docs/scripts/tests/run.sh --down
```

This applies even when you pass `--down` explicitly — the intent is always "only wipe if everything was green". To force a wipe, run `run.sh --down` again in a second invocation.

### How state reset works (important for new tests)

Every test — Jest (API) and Playwright (e2e) — starts from the **freshly-seeded** baseline: `admin@admin.localhost` + `user@user.localhost` (password `password`), plus anything new `*.seeder.ts` files add. There is no "empty DB" state visible to a running test, and there is no leakage between tests.

The single source of truth is [`apps/api/src/database/test-reset.ts`](../../apps/api/src/database/test-reset.ts). Two helpers, both prefixed `reset*` so they sit next to each other in autocomplete:

```
resetDatabase(dataSource):
  1. discover every TypeORM-managed table via dataSource.entityMetadatas
  2. DELETE FROM each one (FK checks off → on)

resetDatabaseAndSeed(dataSource, redis):
  1. resetDatabase(dataSource)
  2. FLUSHDB Redis
  3. runAllSeeders(..., { force: true }) — runs every seed file fresh
```

The default path every test takes is `resetDatabaseAndSeed`:

- **API Jest tests** — `ctx.resetState()` (in [test/helpers/app.ts](../../apps/api/test/helpers/app.ts)) wraps `resetDatabaseAndSeed` + `mail.reset()`. Every spec's `beforeEach` calls it.
- **Playwright e2e** — the API exposes `POST /api/v1/test/reset` via [`src/modules/test/`](../../apps/api/src/modules/test). The module is conditionally imported into `AppModule` only when `NODE_ENV === 'test'` (set by [`docker/test/.env`](../../docker/test/.env)); dev and prod builds never register the endpoint. Each e2e spec's `test.beforeEach` calls `resetBackend()` from [`e2e/helpers/api.ts`](../../e2e/helpers/api.ts), which POSTs to it and clears Mailpit.

`resetDatabase` (without seed) is exported for the rare test that wants a strictly empty DB — most tests shouldn't reach for it.

**Adding a new entity?** Nothing to change in the reset flow — the entity-metadata scan picks it up automatically. **Adding a new seeder?** Drop a `*.seeder.ts` into [`apps/api/src/database/seeds/`](../../apps/api/src/database/seeds); `runAllSeeders` discovers it and every test suite thereafter starts with that data baked in.

**Writing a new e2e spec?** Add `test.beforeEach(() => resetBackend())` at the top of the `test.describe` — without it the spec inherits whatever the previous test left behind.

### Log layout in `test-results/`

Everything lands in the repo-root `test-results/` folder.

```
test-results/
├── summary.md          ← one-page pass/fail table for the last run
├── stack-up.log        ← compose build + healthcheck waits
├── stack-down.log      ← teardown
├── api.log             ← Jest output (full)
├── web.log             ← Vitest output
├── e2e.log             ← Playwright stdout
├── dev-{up,down,…}.log ← dev/run.sh logs (when used)
├── e2e_tmp/            ← Playwright per-test artefacts (screenshots, error-context.md)
│   └── {test-name}/ …
└── e2e_report/         ← Playwright html report (index.html)
```

Playwright wipes its own outputDir (`e2e_tmp/`) and the html report folder (`e2e_report/`) at the start of each run — that's why both live in their own sub-directory. Log files in the root are never touched by Playwright.
