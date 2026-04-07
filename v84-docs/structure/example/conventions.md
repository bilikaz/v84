# Conventions & Patterns

Rules that agents must follow when making design decisions. These reduce ambiguity and prevent naming/style drift across runs.

> Toon tables use ~ as separator

## Naming

Convention ~ Rule
entity primary key ~ always `id` (auto-increment int), never exposed to clients
entity unique key ~ always `key` (varchar), generated with uuid v4(), used for external lookups
message text field ~ always `body` (not content, not message, not text)
timestamps ~ always `createdAt`, `updatedAt` using TypeORM decorators @CreateDateColumn / @UpdateDateColumn
DTOs ~ name as {Action}{Entity}Dto: CreateMessageDto, UpdateMessageDto
response DTOs ~ name as {Entity}ResponseDto: MessageResponseDto
API endpoints ~ plural nouns: /messages, /users, /keys (not /message, /user)
env variables ~ UPPER_SNAKE_CASE: DATABASE_HOST, API_PORT, MESSAGE_MAX_LENGTH

## IDs & Keys

Convention ~ Rule
database primary key ~ auto-increment int, internal only, never in API responses
external-facing key ~ uuid v4 via uuid package, stored as varchar(36), unique indexed
log correlation ~ uuid v4 per request for tracing
session/token ids ~ uuid v4

## Code Organization

Convention ~ Rule
barrel exports ~ every module folder has an index.ts re-exporting public API
one class per file ~ entity, DTO, service, controller each get their own file
component structure ~ React: one component per file, named export matching filename
test co-location ~ test files live next to source: message.service.spec.ts beside message.service.ts
shared types ~ no shared packages between backend and frontend — each side owns its own types

## Backend Folder Structure (NestJS)

Entities and migrations are data-layer concerns shared across the app. Modules are feature concerns that consume entities.

```
src/
├── config/                ← all config files (env parsing, defaults, type conversion)
│   ├── app.config.ts
│   ├── database.config.ts
│   └── index.ts
├── entities/              ← all entities (shared across modules)
│   ├── message.entity.ts
│   └── index.ts
├── migrations/            ← all migrations
│   └── 1712300000000-CreateMessageTable.ts
├── messages/              ← feature module: controller, service, DTOs only
│   ├── dto/
│   │   ├── create-message.dto.ts
│   │   └── index.ts
│   ├── messages.controller.ts
│   ├── messages.service.ts
│   ├── messages.module.ts
│   └── index.ts
└── app.module.ts
```

Convention ~ Rule
entities folder ~ all entities live in src/entities/, not inside module folders — entities get referenced across modules
migrations folder ~ all migrations live in src/migrations/
config folder ~ all env parsing and config lives in src/config/ — application code uses ConfigService getters only
module folder ~ contains controller, service, DTOs, and module definition — no entities, no migrations, no config

## Error Handling

Convention ~ Rule
API errors ~ use NestJS built-in exceptions: NotFoundException, BadRequestException, etc.
404 behavior ~ for key-based lookups, return 404 for both invalid format and not-found — never leak key existence
validation errors ~ let ValidationPipe handle, return 400 with class-validator error array
frontend errors ~ catch at fetch boundary, show inline error, never clear user input on failure

## Logging

Convention ~ Rule
logger ~ pino with structured JSON
log level ~ info for business events (create, retrieve), debug for internals, error for failures
sensitive data ~ never log message body/content, only log keys and metadata
request tracing ~ attach uuid v4 request ID to every log entry

## Styling (Frontend)

Convention ~ Rule
css approach ~ Tailwind utility classes, no custom CSS files unless absolutely necessary
theme tokens ~ define in tailwind.config.ts via theme.extend
color format ~ hex values: #D4A017, #3E2723, #FFF8E7
responsive ~ mobile-first, single column default, expand on larger breakpoints
fonts ~ display font for headings, system sans-serif for body text
