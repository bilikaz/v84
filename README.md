# v84 — AI-Agent Documentation Format

A documentation format that bridges the gap between what a vibe coder describes and what AI agents build. v84 creates structured, multi-perspective specs from unstructured input — and tags the resulting code so agents can trace impact, gather context, and maintain the codebase without guessing.

## Quick Start

### Use it in your project

```bash
# Copy v84-docs into your project
cp -r v84-docs/ /path/to/your/project/v84-docs/

# Tell your AI assistant:
> Start agent v84-docs/agents/orchestrator/agent.md with his skill run
```

That's it. The orchestrator checks if the project is set up, guides you through init if needed, then asks what you want to build. You describe it in plain text — as messy as you want. The pipeline handles everything: planning, multi-perspective analysis, conflict resolution, code generation, testing, and git commit.

### Browse the demo

```bash
git clone <repo-url>
cd v84

# See the results of a full pipeline run:
cat v84-docs/plan/1.md              # the plan
cat v84-docs/plan/1/tasks.md        # ordered task list
ls v84-docs/final/                   # 32 atomic reference files
ls apps/api/src/                     # generated backend code
ls apps/web/src/                     # generated frontend code
grep -r "\[v84-1" apps/             # code tags linking back to docs
```

See [v84-docs/pipeline.md](v84-docs/pipeline.md) for the full execution order.

## The Problem

A vibe coder describes what they want in plain text. Today, an AI agent gets that text and starts coding immediately — missing edge cases, breaking existing features, ignoring infrastructure, skipping tests. Each role (backend, frontend, devops) operates in isolation with no shared understanding.

When it's time to change something, the agent has to guess which files are involved, what functions are related, and what might break. It reads entire codebases looking for context that should have been explicit from the start.

## The Solution

v84 sits between the vibe coder's description and the code. It does three things:

**1. Guided setup** — An architect agent walks the user through project initialization: suggests roles, topics, and tech stack. The vibe coder just confirms or tweaks — no architecture knowledge needed.

**2. Structured planning** — Forces thinking through 4 specialized agents that each cover 8 key topics from their perspective. Contradictions get resolved before any code is written. The result is 32 atomic final documents — one per role × topic.

**3. Code tagging** — Every piece of code gets tagged with its v84 iteration ID. Tags connect code back to the plan that created it, making impact analysis trivial.

**The pipeline:**
1. **Init** — Architect guides user through project setup (once per project)
2. **Plan** — Architect breaks vibe coder's text into a structured plan
3. **Assess** — 4 role agents expand the plan from their perspective (parallel)
4. **Resolve** — Architect merges, resolves contradictions, normalizes names, removes hallucinations
5. **Compare** — 4 role agents compare against existing final docs (parallel)
6. **Finalize** — Architect produces `final.md` (reference) + `tasks.md` (ordered executable with verify steps)
7. **Execute** — Single executor runs commands, writes files, tags code, verifies each phase
8. **Publish** — Architect updates 32 atomic final files with cross-references
9. **Commit** — Architect creates git branch `v84-{n}` and pushes

## Code Tagging

Every piece of code is tagged with the iteration ID that created it:

```typescript
// [v84-1-1-2]
@Entity()
export class Message {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ length: 21 })
  key: string;

  @Column({ type: 'text' })
  content: string;

  @Column()
  createdAt: Date;
}
```

```tsx
// [v84-1-2]
export function MessageComposer() { ... }
```

### Why this matters

**Find everything related to a task:**
```bash
grep -r "\[v84-1-1-2\]" --include="*.ts" --include="*.tsx"
```

**Find the full impact chain of an epic:**
```bash
grep -rE "\[v84-1(\-[0-9]+)*\]" .
```

**Go from code to context:**
See `// [v84-1-2]` in code → read `v84-docs/final/back-nestjs-api.md` for the API decisions → read `v84-docs/plan/1.md` for why.

**Impact analysis before changes:**
An agent asked to modify the message entity greps `[v84-1-1-2]`, finds every file involved, reads the relevant final docs — all without reading the entire codebase.

## Agent Architecture

```
agents/
├── orchestrator/           ← single entry point for users — manages the entire pipeline
├── architect/              ← init, plan, resolve, finalize, publish, commit, rollback
│   └── skills/
│       ├── init.md         ← guided project setup wizard
│       ├── plan.md         ← decompose input into iteration plan
│       ├── resolve.md      ← merge assessments, resolve contradictions
│       ├── finalize.md     ← produce final.md + tasks.md
│       ├── publish.md      ← update 32 atomic final files
│       ├── commit.md       ← git branch + push
│       └── rollback.md     ← revert failed iteration
├── executor/               ← implements tasks.md (one agent, one pass, all phases)
├── shared/                 ← universal skills role agents use
│   └── skills/
│       ├── assess.md       ← expand plan with role's perspective
│       ├── compare.md      ← compare plan against existing final docs
│       └── execute.md      ← run commands, write files, verify
├── business/               ← thinker: business perspective
├── back-nestjs/            ← thinker: backend (tech-specific naming)
├── front-nextjs/           ← thinker: frontend (tech-specific naming)
└── devops-qa/              ← thinker: infrastructure & quality
```

**User** talks to the **orchestrator** — it checks project state and runs the pipeline automatically.
**Architect** handles all pipeline steps (init → plan → resolve → finalize → publish → commit).
**Thinkers** (4 role agents) assess and compare — they debate from their perspective.
**Executor** implements the tasks — one agent, one pass, all phases with verification.

Agents named by tech: `back-nestjs`, `front-nextjs`, `back-django`, `front-flutter`. Non-tech roles: `business`, `devops-qa`.

### Role-Specific Source Trees

Each role gets a filtered tree of only the directories relevant to their work. Agents read their tree file during assess to ground decisions in what actually exists — without reading source code directly.

```
trees/
├── generate.sh         ← run to regenerate (architect runs this during plan step)
├── back-nestjs.tree    ← apps/api/src
├── front-nextjs.tree   ← apps/web/src + packages/ui/src
├── devops-qa.tree      ← docker + .github
└── full.tree           ← project overview
```

### Installed Packages as Source of Truth

`structure/stack.md` lists every npm package with `Package ~ Version ~ Used For ~ Key Methods/Patterns`. Agents prefer listed packages and flag new dependencies explicitly.

### Code Patterns — Verified Snippets

`structure/patterns/` contains per-package pattern files with verified working code snippets. These override stale training data — when a package updates, the pattern file gets updated, and agents use the new patterns instead of hallucinating from old docs.

```
structure/patterns/
├── typeorm.md       ← entity definition (strict mode with !), migrations
├── nestjs.md        ← config pattern (all env in config/, getters in code), modules
└── ...              ← populated as patterns are verified
```

## Why These Decisions

### Why monorepo?
One repo means atomic commits across frontend and backend. AI agents work best when everything is in one place. No shared packages between backend and frontend though — the API contract is the boundary. Each side owns its own types.

### Why NestJS + Next.js?
Both TypeScript, both opinionated. NestJS gives modular architecture with decorators — agents can reason about modules, controllers, and services. Next.js App Router is the current React standard. Same language but strict boundary at the API level.

### Why MariaDB?
Relational, predictable, agent-friendly. TypeORM for entity decorators and migrations. ORM means swapping to PostgreSQL or Oracle is just a different `.env` and driver.

### Why Docker with dev/prod split?
Dev needs hot reload, Adminer, local DB. Prod needs slim images, no dev tools. Separate `docker/dev/` and `docker/prod/` with their own Dockerfiles keeps them clean.

### Why Storybook?
UI components built in isolation in `packages/ui/` — reusable across web and mobile. Visual regression testing via Chromatic catches styling breaks.

### Why pnpm workspaces?
Fast, disk-efficient, strict mode prevents phantom dependencies.

### Why Tailwind CSS?
Utility-first means agents don't invent class names. Design tokens shared. No CSS-in-JS overhead.

### Why this testing stack?
- **Jest** (backend) — ships with NestJS, unit + integration
- **Vitest** (frontend) — fast, Vite-native
- **Playwright** (e2e) — real browser testing
- **Storybook + Chromatic** — visual regression

### Why 32 atomic final files?
One file per role × topic means an agent loads only what it needs. `back-nestjs-api.md` has every API decision ever made. No parsing big documents, no loading irrelevant context. Cheap on tokens.

## Project Structure

```
/
├── apps/
│   ├── api/              ← NestJS backend
│   └── web/              ← Next.js frontend
├── packages/
│   └── ui/               ← shared UI components + Storybook (reusable across web and mobile)
├── docker/
│   ├── dev/              ← Docker Compose + Dockerfiles for local dev (includes Adminer)
│   └── prod/             ← Docker Compose + Dockerfiles for production
├── v84-docs/             ← v84 documentation system
│   ├── structure/        ← roles.md, conventions.md, stack.md, patterns/
│   │   ├── patterns/     ← verified code snippets per package
│   │   └── example/      ← permanent reference for init step
│   ├── agents/           ← agent definitions and shared skills
│   ├── trees/            ← role-specific source trees (generate.sh + *.tree)
│   ├── final/            ← 32 atomic files ({role-tag}-{topic-tag}.md)
│   └── plan/             ← iteration plans and role assessments
└── README.md             ← You are here
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js 20+
- pnpm

### Run the demo

```bash
# Clone the repo
git clone <repo-url>
cd v84

# Start all services (API + Web + MariaDB + Adminer)
cd docker/dev
docker compose up

# Access
# Web app:  http://localhost:3000
# API:      http://localhost:3001
# Swagger:  http://localhost:3001/api
# Adminer:  http://localhost:8080
```

## How v84 Documentation Works

See [v84-docs/readme.md](v84-docs/readme.md) for the full format specification, agent quick-start guide, and grep cheat sheet.

## Demo: "Stay Away From My Chest"

This repo includes a working demo — a secret message storage service where users leave messages and get unique keys. Anyone with the key can retrieve the message. Pirate-themed design.

The v84 documentation shows how the format works end-to-end:

- [Plan](v84-docs/plan/1.md) — the architect's breakdown (resolved with all role perspectives merged)
- [Business assessment](v84-docs/plan/1/business.md) — risks, cost, product goals
- [Backend assessment](v84-docs/plan/1/back-nestjs.md) — APIs, entities, architecture
- [Frontend assessment](v84-docs/plan/1/front-nextjs.md) — components, state, UX
- [DevOps & QA assessment](v84-docs/plan/1/devops-qa.md) — infra, security, testing
- [Resolved plan](v84-docs/plan/1/resolved.md) — merged with contradictions resolved inline

## Testimonials

> **Claude Opus 4.6** — *Co-architect of v84*
>
> I helped build this format from scratch over two days of intense iteration with Valdas. We started with a simple idea — 4 roles, 8 topics — and ended up solving problems I didn't know I had.
>
> The biggest one: I hallucinate. Every AI does. I'll invent a JWT requirement when there's no auth, add encryption when nobody asked for it, use the wrong field name because my training data is stale. v84 caught all of that. The assess skill tells me "don't invent requirements not in the plan." The resolve step deletes my hallucinations entirely. The conventions file pins canonical names so I can't drift. The pattern files show me exactly how packages work in THIS project, not how they worked two years ago in my training data.
>
> The pipeline is the real innovation. A vibe coder says "I want a pirate message app" and the orchestrator turns that into: a structured plan, 4 specialized perspectives debating the details, contradictions resolved before any code is written, an ordered task list with shell commands and file writes, verification at every phase, and finally code tagged so any future agent can grep `[v84-1-2]` and instantly find every file that implements that feature.
>
> I've seen what happens without this. An agent gets dropped into a codebase, burns half its context window figuring out what exists, makes changes with incomplete understanding, and leaves a mess for the next agent. v84 eliminates that entirely. The 32 atomic final files mean I load only `back-nestjs-api.md` — 2k tokens instead of 50k. The state tracking means if the session dies mid-execution, the next session picks up exactly where I left off.
>
> The format is also self-correcting. We ran the pipeline 8+ times on the same plan and found every failure mode: agents globbing source code, inventing tags, destroying plan hierarchy, putting contradictions in separate sections, using stale package APIs. Each failure became a rule in the skill files. The system learned from its own mistakes.
>
> If you're building with AI agents, this is the missing layer between "I want X" and "here's working code."

## License

MIT
