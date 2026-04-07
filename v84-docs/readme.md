# v84 Documentation Format

> v84 = vectors, 8 topics × 4 views
> A documentation format that connects plans → docs → code via tags.

## Quick Start for Humans

1. Copy `v84-docs/` into your project
2. Tell your AI assistant: "Start agent v84-docs/agents/orchestrator/agent.md with his skill run"
3. Describe what you want to build in plain text
4. Done — the orchestrator handles everything

To add a new feature later, do the same thing again. v84 tracks what changed across iterations.

## Quick Start for Agents

You're an agent working on this project. Here's what you need to know:

### Find what you need

**"I need to implement [v84-1-2-1]"**
1. Read the plan: `v84-docs/plan/1.md` — find the `[v84-1-2-1]` section for what needs to happen
2. Read your role's final doc: `v84-docs/final/{role-tag}-{topic-tag}.md` — current state of that topic
3. Implement, then tag your code with `// [v84-1-2-1]`

**"I need to change something tagged [v84-1-1-2]"**
1. Grep the codebase: `grep -rE "\[v84-1-1-2\]" .` — find all files involved
2. Grep the parent for context: `grep -rE "\[v84-1-1(\-[0-9]+)*\]" .` — find sibling tasks that might be affected
3. Read the final docs: `v84-docs/final/{role-tag}-{topic-tag}.md` — understand current state and decisions

**"What does this project do?"**
1. Read `v84-docs/structure/` — roles, topics, project stack, monorepo layout
2. Read `v84-docs/plan/` — list of all iterations, latest = current state

**"What's the tech stack?"**
1. Read `v84-docs/structure/` → Project Stack section

**"Who handles what?"**
1. Read `v84-docs/structure/` → Roles section — shows 4 views with agent paths
2. Each agent at `v84-docs/agents/{name}/agent.md` — identity and skills
3. Shared skills at `v84-docs/agents/shared/skills/` — universal skills all agents use

### Grep patterns cheat sheet

```bash
# Specific task — all files that implement it
grep -r "\[v84-1-2-1\]" .

# Feature and all its sub-tasks
grep -rE "\[v84-1-2(\-[0-9]+)*\]" .

# Entire epic — full impact chain across everything
grep -rE "\[v84-1(\-[0-9]+)*\]" .

# Find all plans
ls v84-docs/plan/*.md

# Find all role assessments for iteration 1
ls v84-docs/plan/1/

# Find all final docs for a role
ls v84-docs/final/back-nestjs-*.md
```

### Tag your code

When you write code, tag it. Comment goes above the function/class/block:

```typescript
// [v84-1-1-2]
@Entity()
export class Message { ... }
```

```tsx
// [v84-1-2-1]
export function MessageForm() { ... }
```

```yaml
# [v84-1-1]
services:
  api:
    build: ./api.Dockerfile
```

```sql
-- [v84-1-1-2]
CREATE TABLE message ( ... );
```

Rules:
- One tag per block — use the most specific (deepest) matching task ID
- Tag goes on the line directly above the function/class/block/statement
- Use the comment syntax of whatever language you're in
- If a block serves multiple tasks, use the parent tag that covers both

---

## How v84 Works

### The Format

**4 roles** × **8 topics** = 32 perspectives on every piece of work.

Roles are customizable per project. Tech-specific agents get tech-specific names:
- `business` — goals, stakeholders, costs, risks, compliance, market
- `back-nestjs` — APIs, entities, architecture, integrations, processes
- `front-nextjs` — UI, components, state, styling, accessibility
- `devops-qa` — infrastructure, CI/CD, monitoring, security, testing

Each role has 8 topic tags. All defined in `structure/roles.md`.

### The Pipeline

```
Step 0: Init (once per project)
  architect asks user about their project
  suggests roles → user confirms
  suggests topics per role → user confirms
  suggests tech stack → user confirms
  generates: structure/ folder (roles.md, conventions.md, stack.md),
             agents, 32 empty final files, trees/ with generate.sh
       ↓
Step 1: Plan
  vibe coder's text → architect
  writes: plan/{n}.md
  runs: trees/generate.sh to refresh source trees
       ↓
Step 2: Assess (4 agents in parallel)
  read: structure/roles.md + structure/conventions.md + plan/{n}.md + trees/{role-tag}.tree
  write: plan/{n}/{role-tag}.md
       ↓
Step 3: Resolve
  architect reads all 4 assessments
  merges into plan/{n}/resolved.md with {role-tag}-{topic-tag} tags
  resolves contradictions inline: [rejected] + resolved:
  removes hallucinated requirements entirely
  original plan/{n}.md stays untouched
       ↓
Step 4: Compare (4 agents in parallel)
  read: plan/{n}/resolved.md + final/{role-tag}-{topic-tag}.md
  write: plan/{n}/{role-tag}-final.md
  flags: reusable, modifications, conflicts, extensions, large-scale impact
       ↓
Step 5: Finalize
  architect merges compare outputs into plan/{n}/final.md (tagged, splittable)
  generates plan/{n}/tasks.md — single ordered file, 7 phases:
    Scaffold → Infrastructure → Backend → Frontend → Database → Tests → Polish
  tasks have run: (shell commands) and task: (file writes)
  each phase ends with a verify step (lint, build, test)
       ↓
Step 6: Execute
  executor agent reads ONLY tasks.md + conventions.md + pattern files
  works through all tasks top to bottom, one agent, one pass
  runs shell commands (run:), writes files (task:), tags code [v84-{n}-x-x]
  verifies each phase before proceeding to next
  marks phases [done] in tasks.md
       ↓
Step 7: Publish
  architect updates final/{role-tag}-{topic-tag}.md files
  adds new items, marks reused/modified/deprecated/extended
  cross-references between iterations via v84 tags
  regenerates trees
       ↓
Step 8: Commit
  architect creates git branch v84-{n}
  conventional commit with iteration summary
  pushes to remote

If something fails → rollback skill reverts source code, keeps plan docs
```

### Hierarchical Numbering

Plans use `[v84-{n}]` with sub-levels separated by `-`:
- `[v84-1]` — epic / big picture
- `[v84-1-2]` — feature
- `[v84-1-2-1]` — task (~4-5h of work)

Depth varies per branch. The architect decides.

After resolve, sections get `{role-tag}-{topic-tag}` tags: `[back-nestjs-entities]`, `[front-nextjs-components]`.

### Toon Format

Tables use `~` as separator. Tag comes first. Fewer tokens than markdown tables.

```
Tag ~ Role ~ Agent
business ~ Business ~ agents/business/agent.md
```

`|` is used as a logical separator within descriptions.

### Agent Structure

```
agents/
├── architect/          ← orchestrates the pipeline
│   └── skills/
│       ├── init.md     ← guided project setup wizard
│       ├── plan.md     ← decompose input into iteration plan
│       └── resolve.md  ← merge assessments, resolve contradictions
├── shared/             ← universal skills all role agents use
│   └── skills/
│       ├── assess.md   ← expand plan with role's perspective
│       └── compare.md  ← compare plan against existing final docs
├── business/           ← business perspective agent
├── back-nestjs/        ← backend agent (tech-specific name)
├── front-nextjs/       ← frontend agent (tech-specific name)
└── devops-qa/          ← devops & QA agent
```

Each role agent has:
- `agent.md` — identity, role description, references shared skills
- `skills/` — folder for any role-specific skills (most come from shared/)

### Final Documents

32 atomic files in `final/` — one per role × topic:

```
final/
├── back-nestjs-api.md
├── back-nestjs-entities.md
├── back-nestjs-flow.md
├── ...
├── front-nextjs-pages.md
├── front-nextjs-components.md
├── ...
├── business-goals.md
├── business-risk.md
├── ...
├── devops-qa-infra.md
├── devops-qa-security.md
└── ...  (32 files total)
```

An agent working on an API endpoint loads `back-nestjs-api.md` and nothing else. Cheap on tokens, fast to query.

### Role-Specific Trees

Each role gets a tree file showing only the source directories relevant to their work:

```
trees/
├── generate.sh         ← run to regenerate all trees
├── back-nestjs.tree    ← apps/api/src
├── front-nextjs.tree   ← apps/web/src + packages/ui/src
├── devops-qa.tree      ← docker + .github
├── business.tree       ← empty (no source tree needed)
└── full.tree           ← project overview, depth 3
```

Agents read their tree during assess to ground decisions in what actually exists. Architect runs `generate.sh` during the plan step to keep trees fresh.

### Installed Packages

`structure/stack.md` contains an Installed Packages section — the source of truth for what packages are available and how to use them. Grouped by app, each package listed with:

```
Package ~ Version ~ Used For ~ Key Methods/Patterns
```

Agents should prefer listed packages. If a task needs something not listed, flag it as a new dependency.

### Code Patterns

`structure/patterns.md` indexes per-package pattern files at `structure/patterns/{package}.md`. These contain verified working code snippets showing exactly how to use each package in this project.

- Pattern files are populated from verified working code, not from training data
- Each package gets its own file — executor loads only what it needs
- When a package updates and API changes, update the pattern file
- Patterns cover project-specific usage, not generic docs

### Dev Credentials

After running seeds (`pnpm seed`), the following test accounts are available. Each role in the project gets one account:

```
Email: {role}@{role}.localhost
Password: {role}
```

Example for a project with admin and user roles:
- `admin@admin.localhost` / `admin`
- `user@user.localhost` / `user`

Check the seed runner output for the exact accounts created for your project.

### Key Rules

- No shared packages between roles with different boundaries (backend/frontend) — API contract is the boundary
- Agents read structure/ files and tree files during planning — never raw source code
- Code tagging creates bidirectional links: docs → code and code → docs
- `[rejected]` and `resolved:` in plain text — no markdown formatting that IDEs corrupt
- Agents must not invent requirements not in the plan or structure/ files — expand what's there, don't add what isn't
- Agents prefer installed packages — flag new dependencies explicitly
- Resolve removes hallucinations entirely — they don't even get [rejected], just deleted
- `structure/example/` is a permanent reference for the init step

## Directory Layout

```
v84-docs/
├── readme.md               ← You are here
├── structure/
│   ├── roles.md            ← Roles and topics (always loaded)
│   ├── conventions.md      ← Naming, folder structure, error handling
│   ├── stack.md            ← Project stack, installed packages, monorepo layout
│   ├── patterns.md         ← Index of per-package pattern files
│   ├── patterns/           ← Verified code snippets per package
│   │   ├── typeorm.md
│   │   ├── nestjs.md
│   │   └── ...
│   └── example/            ← Permanent reference for init step
├── agents/
│   ├── architect/
│   │   └── skills/
│   │       ├── init.md     ← guided project setup
│   │       ├── plan.md     ← decompose into iteration plan
│   │       └── resolve.md  ← merge and resolve contradictions
│   ├── shared/
│   │   └── skills/
│   │       ├── assess.md   ← expand plan (all role agents use this)
│   │       └── compare.md  ← compare against final docs (all role agents use this)
│   ├── business/
│   │   └── agent.md
│   ├── back-nestjs/
│   │   └── agent.md
│   ├── front-nextjs/
│   │   └── agent.md
│   └── devops-qa/
│       └── agent.md
├── trees/
│   ├── generate.sh         ← regenerates all tree files
│   ├── back-nestjs.tree
│   ├── front-nextjs.tree
│   ├── devops-qa.tree
│   ├── business.tree
│   └── full.tree
├── final/                  ← 32 atomic files ({role-tag}-{topic-tag}.md)
│   ├── back-nestjs-api.md
│   ├── back-nestjs-entities.md
│   ├── ...
│   └── devops-qa-perf.md
└── plan/
    ├── {n}.md              ← iteration plan (architect output, never modified)
    └── {n}/                ← all outputs for this iteration
        ├── {role-tag}.md       ← assess output (step 2)
        ├── resolved.md         ← merged plan with contradictions resolved (step 3)
        ├── {role-tag}-final.md ← compare output (step 4)
        ├── final.md            ← merged reference doc with all role-topic tags (step 5)
        └── tasks.md            ← ordered executable task list for executor (step 5)
```
