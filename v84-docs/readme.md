# v84 Documentation Format

> v84 = vectors, 8 topics × 4 views
> A documentation format that connects plans → docs → code via tags.

## Quick start for humans

1. Copy `v84-docs/` into your project.
2. Tell your AI assistant: "Start agent `v84-docs/agents/executor/agent.md` with its `run` skill."
3. Describe what you want to build in plain text.
4. Done — the executor drives the pipeline and writes the code.

To add a new feature later, run another iteration. v84 tracks what changed across iterations via hierarchical `[v84-{n}-…]` tags in plan docs and in source comments.

## Quick start for agents

**"I need to implement `[v84-2-2-1]`"**
1. Read the plan narrative: `v84-docs/plan/2.md` (or the `final/plan.md` rollup).
2. Read your role's final doc: `v84-docs/final/{role}/{topic}.md`.
3. Implement, then tag touched code with `// [v84-2-2-1][{role}:{topic}]`.

**"I need to change something tagged `[v84-1-1-2]`"**
1. `grep -r "\[v84-1-1-2\]" .` — find every file touching that plan node.
2. `grep -r "\[v84-1-1-2\]\[back-nestjs" .` — narrow to one role.
3. Read `v84-docs/final/{role}/{topic}.md` for the current state and the decisions behind it.

**Grep cheat sheet:**
```bash
grep -r "\[v84-1-2-1\]" .              # all code for one plan node
grep -r "\[back-nestjs:entities\]" .   # all code from one topic
grep -r "\[v84-1-2-1\]\[back-" .       # exact intersection
ls v84-docs/plan/*.md                  # all iteration plan narratives
ls v84-docs/final/back-nestjs/*.md     # all final docs for a role
```

## How v84 works

**4 roles** × **up to 8 topics each** = up to 32 perspectives on every piece of work.

Roles are customizable per project. Tech-specific roles get tech-specific names:

- `reviewer` — brand, performance, quality, security (+ up to 4 more slots).
- `back-nestjs` — API, entities, services, notifications, jobs, realtime.
- `front-nextjs` — pages, UI, forms, API/BFF, realtime.
- `ops` — infra, deps, testing.

Each role has up to 8 topic tags. Unused slots are placeholders. All defined in `structure/roles.md`.

### The pipeline (summary)

```
Plan (architect)
→ Cycle — draft / patch → lead review → architect review, loops until APPROVED
→ Extract tasks (script) → Execute (executor agent)
→ Finish (script: promote to final/, regenerate trees, optional commit)
```

Deterministic scripts live under `v84-docs/scripts/`. LLM-driven steps are wrapped by the same scripts so every invocation is reproducible. See [readme/pipeline.md](readme/pipeline.md).

### Entry format

Agents write tagged entries in `plan/{n}/{role}/{topic}.md`:

```
[v84-2-1-1]#1 User entity with TypeORM decorators
  task: create entity, snake_case columns, strict init
  files: apps/api/src/modules/users/entities/user.entity.ts
  depends: [v84-2-1-1]#1
```

Code gets dual tags so you can grep in both directions:

```typescript
// [v84-2-1-1][back-nestjs:entities]
@Entity()
export class User { ... }
```

### Toon format

Tables use `~` as separator — cheaper than markdown pipes, same information.

```
Tag ~ Role
reviewer ~ Reviewer
```

### Hierarchical numbering

```
[v84-1]       ← big picture (iteration)
[v84-1-2]     ← feature
[v84-1-2-1]   ← complete deliverable (user can see or test it)
```

Depth varies per branch. The architect decides. Leaves are complete deliverables — not tiny steps.

## Further reading

- [readme/pipeline.md](readme/pipeline.md) — step-by-step execution order, file flow, state tracking, recovery.
- [readme/running-scripts.md](readme/running-scripts.md) — run the full pipeline via bash scripts, any LLM provider.
- [readme/agents-guide.md](readme/agents-guide.md) — agent architecture, context files, conventions, key rules.
- [readme/directory.md](readme/directory.md) — full directory layout, trees, missing-report, dev credentials.
- [readme/dev-and-tests.md](readme/dev-and-tests.md) — dev stack and test suite runners (`scripts/dev/run.sh`, `scripts/tests/run.sh`).
- [structure/roles.md](structure/roles.md) — roles and topics.
- [structure/conventions.md](structure/conventions.md) — shared project rules.
