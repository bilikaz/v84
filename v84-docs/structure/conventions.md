# Conventions — Shared

Rules that all agents must follow.

> Toon tables use `~` as separator.

## Project Stack

Infrastructure, tooling, and conventions that are not npm packages. npm packages are auto-generated per role into `v84-docs/context/{role-topic}/packages.md` — `package.json` is the source of truth.

Type ~ Choice ~ Notes
repo ~ monorepo ~ single repository for all services
database ~ MariaDB ~ relational database | TypeORM for ORM | migrations via TypeORM CLI
dev-environment ~ Docker Compose ~ all services containerized for local development
db-admin ~ Adminer ~ web UI for database access in development
mail-catcher ~ Mailpit ~ captures all outgoing mail in dev and test | exposes SMTP + web UI | no real emails leave the stack
ci ~ GitHub Actions ~ lint → test → build → deploy pipeline
containerization ~ Docker ~ multi-stage builds | slim production images
env-management ~ dotenv ~ commit `.env.example` | `.env` in `.gitignore` | EXCEPTION: commit `docker/test/.env` for throwaway test-stack credentials

## Monorepo Structure

Top-level layout. Full file trees live in `v84-docs/trees/`.

```
/
├── apps/
│   ├── api/              ← NestJS backend
│   ├── web/              ← Next.js frontend
│   └── storybook/        ← Storybook host workspace 
├── brand/                ← tokens.mjs/.cjs/.d.ts + copy.mjs/.cjs/.d.ts + logos/
├── docker/
│   ├── dev/              ← all services + MariaDB + Adminer + Mailpit + hot reload
│   └── test/             ← isolated test stack | own MariaDB, Redis
├── e2e/                  ← Playwright end-to-end tests
├── .github/
│   └── workflows/        ← CI/CD pipelines
├── .husky/               ← git hooks
├── pnpm-workspace.yaml
├── tsconfig.base.json    ← shared TypeScript configuration
├── .eslintrc.js          ← shared ESLint configuration
├── .prettierrc           ← shared Prettier configuration
├── playwright.config.ts
└── v84-docs/             ← this documentation system
```


## Storybook

Storybook hosts stories from multiple apps (web UI primitives + api email templates). Rules apply everywhere.

Convention ~ Rule
host workspace ~ `apps/storybook/` — dev-only, no source of its own
story colocation ~ `*.stories.tsx` lives next to its source file — only in `apps/web/src/ui/**/*.stories.tsx` and `apps/api/src/templates/**/*.stories.tsx`. Feature components in `apps/web/src/modules/` do NOT get stories.
tsc exclude ~ every consumer tsconfig (`apps/web/tsconfig.json`, `apps/api/tsconfig.json`) MUST exclude `src/**/*.stories.tsx` so the app runtime never pulls in `@storybook/react`
story naming ~ `<Component>.stories.tsx`. Sidebar groups by folder path (e.g. `Components/Button`, `Emails/Templates/PasswordResetEmail`).
mock data ~ embed plain fixtures inside the story file. Stories must never hit the network.
adding a source location ~ update three files: `apps/storybook/.storybook/main.ts` glob, `apps/storybook/tailwind.config.ts` content paths, and the bind-mount in `docker/dev/docker-compose.yml`

## Code Organization

Convention ~ Rule
barrel exports ~ only the lowest-level sub-folders have `index.ts` barrels (e.g. `pages/`, `components/`, `dto/`, `entities/`, `guards/`, `hooks/`, `providers/`, `strategies/`, `ui/primitives/`). NEVER create top-level barrels at `modules/{feature}/index.ts`, `common/index.ts`, or `ui/index.ts` — they cause circular imports when sibling folders cross-depend. Import from the sub-barrel (`@/common/hooks`) or directly from the file (`../users/users.service`).
one class per file ~ entity, DTO, service, controller, and component each get their own file
test location ~ API integration tests in `apps/api/test/`, web unit tests in `apps/web/src/__tests__/`, Playwright e2e tests in `e2e/` at repo root. Group tests by concern. Do NOT co-locate tests with source files. Keep `src/` clean and test helpers centralized.
test file naming ~ API test files MUST use the `.e2e.spec.ts` suffix (e.g. `apps/api/test/auth.e2e.spec.ts`) even though they are integration tests — matches the Jest glob pattern. Playwright tests in `e2e/` use `.spec.ts` (e.g. `e2e/auth.spec.ts`). Web unit tests use `.test.ts` (e.g. `apps/web/src/__tests__/lib/storage.test.ts`). These three suffixes are fixed — do NOT flag them as drift.
shared types ~ no shared packages between backend and frontend. Each side owns its own types.

## Brand

Convention ~ Rule
visual identity ~ lives in `brand/` (colors, radii, spacing, typography). Never hardcode values — import from `brand/tokens`.
verbal identity ~ lives in `brand/` (app name, subjects, taglines). Never hardcode brand strings like `'V84'` — import from `brand/copy`. Rebranding must be a one-file change.
i18n ready ~ when i18n is added, `brand/copy` becomes the layer where strings turn into translation keys. Templates stay pure rendering. Services stay pure orchestration.
dual format ~ ship `tokens` and `copy` as `.mjs` (ESM) + `.cjs` (CJS) + `.d.ts` (types) plus a `brand/package.json` with `exports` conditions routing `import`→`.mjs`, `require`→`.cjs`, `types`→`.d.ts`. Never ship plain `.ts` files.
why dual ~ Vite/Storybook serves ESM (needs `.mjs`); NestJS compiles to CJS where `require()` cannot load ESM in Node 20 (needs `.cjs`). One runtime file cannot satisfy both.
hand-synced ~ `tokens.mjs` and `tokens.cjs` must hold identical values (same for `copy.mjs` and `copy.cjs`). Edit `.mjs` as the source and copy every change into `.cjs` in the same commit.
adding a token ~ edit all three files (`.mjs`, `.cjs`, `.d.ts`) together. `tsc` errors will appear at every consumer until all callers update.
flat structure ~ tokens hold primitives only. Do NOT nest Tailwind-shaped objects like `{ primary: { 500: ..., 600: ... } }`. Each consumer reshapes them as needed.
docker mounts ~ `brand/` is read-only bind-mounted into `api`, `web`, and `storybook` containers at `/app/brand`.
fonts ~ display fonts (`brand/fonts/*.woff2`) apply to web and Storybook rendering only. Email templates MUST use the system `fontFamily.sans` stack from `brand/tokens` — email clients do not render web fonts reliably.

## Naming

Convention ~ Rule
env variables ~ UPPER_SNAKE_CASE (e.g. `DATABASE_HOST`, `API_PORT`)
db columns ~ snake_case (e.g. `password_hash`, `created_at`, `two_factor_enabled`)
code properties ~ camelCase (e.g. `passwordHash`, `createdAt`, `twoFactorEnabled`)
feature module names ~ plural (e.g. `users`, `sessions`, `notifications`) — EXCEPTION: `auth` remains singular

## IDs

Convention ~ Rule
id format ~ uuid v7 — time-sortable with better database indexing than v4. Use uuid v7 wherever an ID is generated, in any role or workspace.
generation responsibility ~ servers generate all IDs. Clients NEVER create IDs — they receive them in response payloads and treat them as opaque strings.

## Migrations

Migrations are a cross-iteration process rule, not a backend task. Planning agents must never propose a migration as an entry in `plan/{N}/**/*.md`, and reviewers must never ask for one.

Convention ~ Rule
generation ~ auto-generated exactly once at the end of every iteration's execution phase — after all other tasks are implemented and tagged, before `scripts/executor/finish.sh {N}` runs | NEVER written as a task in `plan/{N}/tasks.md`, NEVER requested by corrections | if the generator reports "no changes in database schema" the iteration promotes with zero migration files, which is fine
naming ~ always `iteration-{n}` (e.g. `iteration-2`, `iteration-3`) | timestamp prefix added automatically by TypeORM, producing files like `1775911982357-iteration-2.ts` | NEVER pick descriptive names like `add_user_avatar` or `init` — iteration number is the entire name
generate command ~ `docker compose -f docker/dev/docker-compose.yml exec api pnpm typeorm migration:generate src/database/migrations/iteration-{n} -d src/database/data-source.ts`
run ~ applied automatically on app startup via `migrationsRun: true` in the backend's `DatabaseModule` | NEVER run `migration:run` via CLI in development
tagging ~ after the file is produced, add `// [v84-{n}][back-nestjs:entities]` at the top — iteration-level plan tag, since the file aggregates every entity delta that iteration introduced