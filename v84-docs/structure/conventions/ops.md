# Conventions — Ops, {role_tag}: ops

> Toon tables use `~` as separator.

## Docker & Dev Environment

Convention ~ Rule
dev environment ~ Docker Compose in `docker/dev/` with hot reload, Adminer, and local DB
test environment ~ Docker Compose in `docker/test/` — completely separate stack with its own DB, Redis, and Mailpit. Never touches the dev stack
Dockerfiles ~ separate per environment: `docker/dev/api.Dockerfile`, `docker/test/api.Dockerfile`
node_modules shadowing ~ every service with a host bind-mounted source directory gets an anonymous `/app/.../node_modules` volume
env files ~ commit `docker/dev/.env.example` with all variables documented | gitignore `docker/dev/.env` (machine-specific) | commit `docker/test/.env` (throwaway credentials for the isolated test stack — safe to share)
env vars ~ all `UPPER_SNAKE_CASE` | parsing happens in config files (API side) or `.env` (Docker side)
scripts ~ root `package.json` provides convenience scripts: `dev:api`, `dev:web`, `build`, `lint`, `test`, `test:up`, `test:down`, `test:api`, `test:web`, `test:e2e`, `seed`
seed script ~ `pnpm seed` executes `apps/api/src/database/seed-runner.ts` | runner and seed files are owned by back-nestjs | infra only owns the npm script entry

## Dev Workflow — Changing Deps and Env

Convention ~ Rule
adding a dependency ~ update `package.json` on host via `pnpm --filter` | then run `docker compose build && docker compose up -d` | NEVER run `pnpm install` inside a running container
changing env vars ~ edit `docker/dev/.env` | then run `docker compose up -d` | restart does NOT re-read `env_file`
changing docker-compose.yml ~ run `docker compose up -d` to apply | Compose diffs and recreates only affected services

## Dependencies

Convention ~ Rule
package manager ~ pnpm with strict mode
new packages ~ every new package must be justified | check existing alternatives in INSTALLED PACKAGES first
version tracking ~ `package.json` is the source of truth | `packages.md` is auto-generated from it

## Testing — Philosophy

Convention ~ Rule
no mock-echo tests ~ never mock a dependency then assert the mock returned what you told it to — that tests nothing
integration over unit ~ prefer tests that hit real infrastructure (DB, Redis, email) over heavily mocked units
ask before writing ~ before every test ask: "what bug would this catch that reading the source wouldn't?" | if nothing, do not write it
honest gaps ~ a known untested area is better than a fake-green wall of mocked tests hiding real gaps

## Testing — Assertion Rules

Convention ~ Rule
positive shape only ~ use `toEqual` with the exact key set to pin response shapes — catches extra or missing fields
never `not.toHaveProperty` ~ redundant if you already have a positive shape assertion (`toEqual` or `Object.keys` equality)
never `toMatchObject` for response bodies ~ it silently ignores extra fields | use `toEqual` with `expect.any()` matchers for dynamic values instead
pin full shapes ~ include all fields, including standard ones (e.g. JWT `iat`, `exp`) — leave no holes for extra fields to slip through

## Testing — What to Test vs Skip

Convention ~ Rule
real logic ~ test TTL expiry, time-based decisions, state machines, branching logic, data transformations, security boundaries (`httpOnly`, session cleanup)
guard presence ~ one-line `expect(status).toBe(401/403)` per endpoint to verify decorators/guards are applied — cheap and effective
business rules ~ duplicate email rejection, cross-user isolation, token single-use, role enforcement
skip passthrough ~ mock returns X then assert X back — this is a mirror, not a test
skip framework behavior ~ trust NestJS (500 on unhandled error) and ValidationPipe (400 on bad input)
skip trivial wiring ~ skip simple proxy functions like `return proxyAuthed({to: '/path'}, req)`

## Testing — Test Isolation (Separate Stack)

All tests run against a completely isolated Docker Compose stack in `docker/test/`. Dev environment is never touched.

Convention ~ Rule
separate stack ~ `docker/test/docker-compose.yml` defines isolated containers, own `.env`, own Dockerfiles | never reference `docker/dev/`
own everything ~ test stack fully owns its DB, Redis, and Mailpit | no shared-infra hacks
email capture ~ use in-process `mail-capture.ts` for API integration tests | use Mailpit for Playwright e2e (real SMTP)
reset contract ~ every test (API Jest + Playwright e2e) starts from the freshly-seeded baseline | the single source of truth is `apps/api/src/database/test-reset.ts` which exports two `reset*` helpers: `resetDatabase(dataSource)` truncates every TypeORM-managed table (auto-discovered via `dataSource.entityMetadatas`) AND wipes the raw-SQL `seed_history` meta table so a subsequent `runAllSeeders` sees every seeder as needing to run, and `resetDatabaseAndSeed(dataSource, redis)` wraps `resetDatabase` + FLUSHDB + `runAllSeeders(..., { force: true })` | the seeded path is the default used by both suites — plain `resetDatabase` is exported for rare tests that need a strictly empty DB | never hardcode a table list, new `@Entity()` classes must be wiped automatically
test-only endpoint ~ `POST /api/v1/test/reset` exposed by `src/modules/test/test.controller.ts` | `TestModule` imports `DatabaseModule` (for the global `DataSource`) and declares `RedisService` in its own `providers` list (same pattern as AuthModule) | conditionally imported in `AppModule` only when `NODE_ENV === 'test'` | `docker/test/.env` sets `NODE_ENV=test` for the test stack | dev and prod NEVER see the endpoint
test flow ~ `pnpm test` runs the full cycle: `test:up` → `test:api` → `test:web` → `test:e2e` → `test:down` (with volume teardown) | equivalent: `v84-docs/scripts/tests/run.sh` no args

## Testing — API Tests (Jest + Supertest)

Convention ~ Rule
real infrastructure ~ tests hit real MariaDB, real Redis, and in-process email capture | no mocks
run inside container ~ `pnpm test:api` executes Jest inside the test stack's api container
clean slate ~ `beforeEach(() => ctx.resetState())` in every spec — `resetState` calls the shared `resetDatabaseAndSeed` helper so every test starts with the full seed baseline (`admin@admin.localhost` + `user@user.localhost` + anything new seeders add), not an empty DB
shared helpers ~ `apps/api/test/helpers/auth-flows.ts` provides `registerAndComplete`, `loginHappyPath`, `generateTotp`, `promoteToAdmin`

## Testing — Web Tests (Vitest)

Convention ~ Rule
test real logic only ~ storage TTL, session refresh threshold, cookie security flags, session cleanup on failure
no route handler tests ~ BFF handlers are thin glue — testing them usually creates mock-echo tests | skip them
env from setup.ts ~ set all `process.env` values in `src/__tests__/setup.ts` | never hardcode in test files
storage cleanup ~ `setup.ts` registers a global `beforeEach` that calls `storage.clear()` | individual tests never touch `globalThis.__sessionStorage`
server-only stub ~ alias the `server-only` package to an empty stub in Vitest config so imports do not throw

## Testing — E2E Tests (Playwright)

Convention ~ Rule
reset between tests ~ every spec file MUST call `test.beforeEach(() => resetBackend())` at the top of its `test.describe` | `resetBackend()` lives in `e2e/helpers/api.ts` and hits the `POST /api/v1/test/reset` endpoint, then clears Mailpit | without it, stale sessions and accounts from prior tests pollute the current run
seeded baseline ~ after `resetBackend()` the DB holds exactly `admin@admin.localhost` + `user@user.localhost` (password `password`) | specs can login as admin directly without creating one, or call `registerViaApi(...)` for a fresh non-admin
shared helpers ~ `e2e/helpers/api.ts` provides `deleteAllEmails`, `waitForEmail`, `extractVerifyLink`, `registerViaApi`, `loginViaApi`, `resetBackend` | `e2e/helpers/totp.ts` provides `generateTotp`
unique fixtures ~ per-test ephemeral data (emails, usernames) uses a `unique()` generator (`${Date.now()}-${random-suffix}`) so concurrent runs and per-test leaks can't collide