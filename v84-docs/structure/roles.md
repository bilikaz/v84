# Roles & Topics

> Toon tables use ~ as separator

## Placeholder Topics

Not every role needs 8 active topics. Use `-` as tag for unused slots — scripts and agents skip them. Projects start lean and add topics as complexity grows.

## Roles (Views)

Tag ~ Role
back-nestjs ~ Backend Developer (NestJS)
front-nextjs ~ Frontend Developer (Next.js)
reviewer ~ Reviewer
ops ~ Ops

## Topics by Role

### Backend Developer (NestJS)

Tag ~ Topic ~ Scope ~ NOT yours (belongs to)
api ~ REST Endpoints & API Layer ~ controllers, routes, DTOs, status codes, Swagger, strategies, guards, decorators ~ NOT: entities (entities), service logic (services), gateways (realtime)
realtime ~ WebSockets & Events ~ gateways, event names, payloads, rooms, subscriptions ~ NOT: REST endpoints (api), business logic called from gateways (services)
entities ~ Entities & Data Model ~ entity classes, columns, relations, indexes, seed files, factories, seed-runner implementation ~ NOT: services that use entities (services), controllers (api), migration generation/run (ops:infra)
services ~ Business Logic & Rules ~ service methods, domain rules, orchestration, token generation, session management, all *.service.ts logic ~ NOT: entities (entities), controllers (api), DTOs (api), strategies/guards (api), async work (jobs), notification content (notifications)
jobs ~ Jobs, Queues & Cron ~ background workers, scheduled tasks, retry strategies ~ NOT: service logic triggered synchronously (services), notification content (notifications)
notifications ~ Notifications & Templates ~ email templates, push/SMS, notification service, rendered content ~ NOT: service logic that triggers notifications (services), scheduled sending (jobs)
- ~ (placeholder) ~ available for future topics
- ~ (placeholder) ~ available for future topics

### Frontend Developer (Next.js)

Tag ~ Topic ~ Scope ~ NOT yours (belongs to)
pages ~ Pages, Routes, Auth & Composition ~ page.tsx route files, layouts, navigation, URL structure, route guards (RequireAuth, RequireRole), AuthProvider, useAuth, auth state management ~ NOT: UI primitives (ui), form logic (forms), API calls (api), WS subscriptions (realtime)
ui ~ UI Components & Storybook ~ reusable primitives (Button, Input, Table), Storybook stories ~ NOT: page composition (pages), form logic (forms), data fetching (api)
realtime ~ WebSockets & Live Data ~ socket client, subscriptions, live state updates ~ NOT: REST fetching (api), page composition (pages)
forms ~ Forms & Validation ~ zod schemas, form components, field-level errors, submission flows ~ NOT: page layout (pages), UI primitives (ui), API calls (api)
api ~ API Layer & Backend-for-Frontend ~ route handlers in app/api/*, server-auth, session storage, proxy, cookies, apiFetch wrapper, module api.ts files, types.ts, response types ~ NOT: pages (pages), AuthProvider/useAuth (pages), route guards (pages), UI primitives (ui), form validation (forms), WS subscriptions (realtime)
- ~ (placeholder) ~ available for future topics
- ~ (placeholder) ~ available for future topics
- ~ (placeholder) ~ available for future topics

### Ops

Tag ~ Topic ~ Description
infra ~ Infrastructure, CI/CD, Monitoring ~ Docker | compose | Dockerfiles | .env | scripts | hot reload | local setup | pnpm seed command | migration commands (generate, run) and migration file artifacts | CI/CD pipelines | monitoring | logging | dashboards ~ NOT: seed implementation (back-nestjs:entities), entity definitions (back-nestjs:entities)
testing ~ Testing (API, Web, E2E) ~ Unit | integration | e2e for API and web | Playwright | coverage history
deps ~ Dependencies & Updates ~ Package versions | update history | breaking changes
- ~ (placeholder) ~ available for future topics
- ~ (placeholder) ~ available for future topics
- ~ (placeholder) ~ available for future topics
- ~ (placeholder) ~ available for future topics
- ~ (placeholder) ~ available for future topics

### Reviewer

Tag ~ Topic ~ Description
security ~ Security & Attack Surface ~ Injection points | data exposure | auth gaps | real threats per iteration
performance ~ Performance & Optimization ~ N+1 queries | missing indexes | bundle size | re-render flags
quality ~ Quality, Risk, Impact ~ Prerequisites | user stories & acceptance criteria | cost awareness (infra/services/packages) | accepted shortcuts, deferred work, tech debt | edge cases, empty states, null handling, concurrent writes | what breaks
brand ~ Brand Consistency ~ Visual + verbal identity | hardcoded strings | token usage | rebranding readiness
- ~ (placeholder) ~ available for future topics
- ~ (placeholder) ~ available for future topics
- ~ (placeholder) ~ available for future topics
- ~ (placeholder) ~ available for future topics
