# Conventions — Backend (NestJS), {role_tag}: back-nestjs

> Toon tables use `~` as separator.

Rules apply exclusively to the `back-nestjs` role.

## Entity & Data Model

Convention ~ Rule
entity primary key ~ always declare as `id` with `@PrimaryColumn('uuid')` | assign value in the entity constructor via the `uuid` package | NEVER use `@PrimaryGeneratedColumn('uuid')` (produces wrong ID format — see shared conventions `IDs`). Every entity follows this exact pattern:
```typescript
import { v7 as uuidv7 } from 'uuid';

@Entity()
export class User {
  @PrimaryColumn('uuid')
  id: string = uuidv7();

  // ...other columns
}
```
entity columns ~ snake_case in database, camelCase in TypeScript | use `{ name: 'snake_case' }` inside the `@Column` decorator
entity properties ~ always use non-null assertion operator `!` (`email!: string`) — `strictPropertyInitialization` is enabled
timestamps ~ use `@CreateDateColumn({ name: 'created_at' })` and `@UpdateDateColumn({ name: 'updated_at' })` for `createdAt` / `updatedAt`
entity ownership ~ entities belong to their feature module | file path: `apps/api/src/modules/{feature}/entities/{entity}.entity.ts` (singular) | all lifecycle hooks (`@BeforeInsert`, `@BeforeUpdate`, `@AfterLoad`, etc.) and internal logic (hashing, normalization, validation) live inside the entity class

## API Layer & DTOs

Convention ~ Rule
DTO naming ~ descriptive and action-oriented: `CreateUserDto`, `LoginDto`, `UpdateUserDto`, `RefreshTokenDto`, `ChangeEmailDto` | response DTOs use `XxxResponseDto` suffix (e.g. `UserResponseDto`) | file names match class name in kebab-case
list endpoints ~ every `GET /{plural}` endpoint MUST accept pagination via `ListXxxQueryDto` (`page`, `limit` with sensible defaults) | must return `PaginatedResponseDto<XxxResponseDto>` with shape `{ items, total, page, limit, pages }` | generic class lives in `apps/api/src/common/dto/paginated-response.dto.ts`
API endpoint paths ~ use plural nouns: `/messages`, `/users`, `/sessions` | EXCEPTION: `/auth` remains singular

## Folder Structure & Modules

Every path is from repo root. Use exact paths — no shortcuts, no abbreviations, no relative paths.

Convention ~ Rule
feature modules ~ located at `apps/api/src/modules/{feature}` (plural naming, `auth` exception defined in shared conventions)
shared infrastructure ~ `common/`, `config/`, `database/`, `templates/` live directly under `apps/api/src/` and behave like feature modules with subfolders
barrel exports ~ created ONLY at the lowest level | each sub-folder inside `modules/{feature}/{dto|entities|guards|...}` and inside `apps/api/src/[common|config|database|templates]` gets its own `index.ts` | NO top-level barrels at `modules/{feature}/index.ts` or `apps/api/src/{common|config|database|templates}/index.ts` | import from sub-barrels (e.g. `../../common/guards`) to avoid circular imports in NestJS DI
module file ~ `apps/api/src/modules/{feature}/{feature}.module.ts`
service file ~ `apps/api/src/modules/{feature}/{feature}.service.ts`
controller file ~ `apps/api/src/modules/{feature}/{feature}.controller.ts` (optional — omit for service-only modules like `notifications`)
DTO files ~ `apps/api/src/modules/{feature}/dto/{name}.dto.ts`
strategies, decorators, guards ~ ALWAYS placed in `common/` regardless of usage:  
`apps/api/src/common/strategies/{name}.strategy.ts`  
`apps/api/src/common/decorators/{name}.decorator.ts`  
`apps/api/src/common/guards/{name}.guard.ts`
config parsing ~ all environment/config values parsed via `registerAs()` at `apps/api/src/config/{name}.config.ts`
database module ~ `apps/api/src/database/database.module.ts` registers TypeORM (via `TypeOrmModule.forRootAsync`), Redis, etc.
non-TypeORM services ~ wrapped at `apps/api/src/database/{database}.service.ts`
data source ~ `apps/api/src/database/data-source.ts` used for migrations and external tools

## Migrations

Process-level migration rules (when to generate, what to name, who tags, auto-run-on-startup) live in **shared conventions → Migrations**. The only backend-specific rule:

Convention ~ Rule
data source config ~ `apps/api/src/database/data-source.ts` MUST reuse `apps/api/src/config/database.config.ts` | never duplicate environment variable lookups

## Seeds & Initial Data

Convention ~ Rule
runner ~ `pnpm seed` executes `apps/api/src/database/seed-runner.ts` | discovers `*.seed.ts` files | checks `seed_history` table | runs only new seeds | auto-creates `seed_history` table | skips already-executed seeds | re-running is always safe
production guard ~ seed runner MUST check `NODE_ENV` at startup | exit with non-zero code + explicit error if `production` | this hard guard allows safe commit of dev credentials (`admin@admin.localhost` / `password`)
factory usage ~ all seeds (`apps/api/src/database/seeds/{name}.seed.ts`) MUST use factories (`apps/api/src/database/factories/{name}.factory.ts`) + `faker`
demo data ~ seed useful dev entities (users, admins, products, categories, …) | use `{role}@{role}.localhost` emails | set password to `password`
lifecycle restriction ~ NEVER run seeds from `OnApplicationBootstrap` or other lifecycle hooks

## Templates (Emails / Notifications)

Convention ~ Rule
location ~ `apps/api/src/templates/{channel}/` (`emails/`, `push/`, `sms/`) | NOT a separate package — single consumer only
email templates ~ built as React components with `@react-email/components` | renderers export `render<Name>Email(props)` returning `{ html, text }`
consumer ~ `NotificationsService` imports templates via relative path and passes output to `nodemailer`
storybook stories ~ `*.stories.tsx` colocated with templates | only `apps/api/src/templates/` participates in Storybook (follow shared Storybook rules)

## Brand (Backend)

General brand rules live in shared conventions. Backend-specific rule only:

Convention ~ Rule
import via re-export ~ email templates import brand values through `apps/api/src/templates/emails/theme.ts` (which re-exports from `brand/`) | NEVER import directly from `brand/` | keeps `rootDir: ./src` clean and centralizes path changes

## Error Handling

Convention ~ Rule
api errors ~ throw NestJS built-in exceptions (`NotFoundException`, `BadRequestException`, etc.)
404 behavior ~ return 404 for both invalid ID format and missing record | NEVER leak whether an entity exists
validation errors ~ let `ValidationPipe` + `class-validator` handle input | return 400 with error array

## Logging

Convention ~ Rule
logger ~ use `pino` with structured JSON output
log levels ~ `info` for business events | `debug` for internal details | `error` for failures
sensitive data ~ NEVER log passwords, tokens, or secrets | log only IDs and safe metadata
request tracing ~ attach uuid v7 request ID to every log entry

## Authentication & 2FA

Convention ~ Rule
login contract ~ `POST /auth/login` takes `{ email, password, totpCode? }` and handles the full login in one call | when the account has 2FA enabled and `totpCode` is missing/wrong, the response is `{ requires2fa: true }` and the same endpoint accepts the retry with the code | keeps the contract flat, removes server-side login state, and lets clients that already know 2FA is on finish login in one round-trip
2FA setup payload ~ the API returns the raw TOTP secret (e.g. `{ secret: 'BASE32...' }`) and nothing else | keeps QR-library dependencies out of the backend and keeps the API shape stable across clients
2FA verify ~ `AuthService.verifyTotp(user, code)` is the single verification path reused by both setup (`POST /auth/2fa/verify`) and login (inside `/auth/login`) | one code path = one place to harden