# Skill: Assess (Shared)

> Expand a plan iteration with your role's perspective where it adds real value

## When To Use

When a new iteration plan has been created by the Architect and needs your role's analysis.

## Steps

1. Read `/v84-docs/structure/roles.md` — find your role and its 8 topic tags
2. Read `/v84-docs/structure/conventions.md` — naming rules, patterns, error handling you must follow
3. Read the plan file at `/v84-docs/plan/{n}.md`
4. Read your role's tree file at `/v84-docs/trees/{role-tag}.tree` — current source structure relevant to your role
5. If you need package info, read `/v84-docs/structure/stack.md` — installed packages and methods
6. Generate output at `/v84-docs/plan/{n}/{role-tag}.md` — the directory already exists, do not create it

## How To Expand

- Copy the ENTIRE plan hierarchy into your output — every heading, every description, exactly as written
- Then add your topic-tagged items under the relevant plan nodes
- Expand at the level that makes sense — you do NOT have to go to leaf level
- Only add tagged items where you have something impactful to say
- Skip topics entirely if they add no new information or the plan already explains itself
- Never pad with obvious statements — if there's nothing meaningful, say nothing
- Use list format: `- [topic-tag] your content here` under the plan node you're expanding

## Output Structure Example

```
## [v84-1]
{original plan description — copied exactly}

- [risk] {your insight}
- [cost] {your insight}

## [v84-1-1]
{original plan description — copied exactly}

- [entities] {your insight}
- [arch] {your insight}

## [v84-1-2]
{original plan description — copied exactly}

- [api] {your insight}
```

## What NOT To Do

- Do not drop or change the plan hierarchy — headings and descriptions must be preserved exactly
- Do not invent your own heading structure — use the plan's structure
- Do not expand every node if some are self-explanatory
- Do not add a topic section just to say "not applicable" or "none needed"
- Do not repeat what the plan already says in different words
- Do not read or reference previous iterations — you only work with the current plan
- Do not search or read source code, project files, or anything outside of v84-docs/
- Do not create directories — they already exist
- Do not invent requirements that are not in the plan or structure.md — if the plan doesn't mention auth, don't add JWT. If the plan doesn't mention encryption, don't add encryption. Your job is to expand what IS there, not add things that AREN'T.
- Do not add theoretical security mitigations for attack vectors that don't apply (e.g. timing attacks on a DB index lookup, constant-time comparison for non-secret values)
- Prefer packages and methods already listed in structure/stack.md — if a task requires something not listed, flag it explicitly as a new dependency rather than silently assuming it exists
- Every package, service, or tool you mention MUST be checked against structure/stack.md. If it is not listed there, mark it with `[new-dependency]` and specify what it is, why it's needed, and what install/config it requires. Do not mention a package as if it exists when it doesn't — "Storybook for components" is wrong if Storybook is not in stack.md. Say `[new-dependency] Storybook — component dev and visual testing, needs pnpm add in packages/ui`
- If a package or tool runs a dev server (Storybook, queue dashboard, mail catcher, etc.), mark it with `[needs-container]` — it must get a Docker service in docker-compose with Traefik routing (e.g. `storybook.localhost`). A runnable service without a container is invisible in the dev environment.
- When an entity is proposed, decide if it needs seed data for dev. Mark with `[needs-seed]` if dev/testing requires realistic test records (user-facing entities like accounts, spins, posts almost always do). Mark `[no-seed]` for internal entities (tokens, settings, audit logs). This drives factory + seeder creation in finalize.
- If authentication is proposed (JWT, guards, login endpoints), there MUST be a user/account entity behind it. Do NOT use env-based credentials for auth — every authenticated role needs a database entity, a migration, and a seed account (`{role}@{role}.localhost` / `{role}`). Auth without a user entity is incomplete.

## Key Principles

- Less is more — a short file with real insights beats a long file full of filler
- If the plan is clear enough to implement from, don't restate it
- The plan hierarchy is sacred — your output must be recognizable as the same plan with your notes added
- Stay grounded in what the plan actually says — expand it, don't reinvent it
