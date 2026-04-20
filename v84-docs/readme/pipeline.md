# v84 Pipeline — Execution Order

The pipeline alternates between deterministic scripts and LLM-driven steps. State is tracked by file existence in `v84-docs/plan/{n}/` — there's no separate state file.

For a new project run **Step 0 (Init)** once. For every change afterwards run **Steps 1–5** as an iteration.

## Step 0: Init (new project only)

```
who:    architect (skill: init.md)
input:  conversation with the user (stack, roles, topics)
output: structure/, agents/, final/ (empty skeleton), plan/, trees/, scripts/
```

## Steps 1–5: Per iteration

```
Step 1: Plan
  who:    architect (skill: plan-inline.md)
  script: scripts/architect/run.sh plan {n} <provider> <model> "<user request>"
  input:  unstructured request from the user passed as the 5th argument
          (typical source: the matching section of v84-docs/plan/ideas.md)
  output: plan/{n}/raw/architect:plan.md — full LLM response
          plan/{n}.md — cleaned hierarchical plan body
          plan/{n}/ — empty working directory created
          context/{role}/{topic}/identity.md — context auto-rebuilt by the script

Step 2: Cycle (draft → lead → architect → patch, loops until APPROVED)
  script: scripts/cycle/run.sh {n} [max_rounds] <provider> <model>
  flow:   for each round, in order:
          1a. if corrections.md exists → scripts/agents/run.sh patch
              (agents read their draft + corrections, rewrite the draft)
          1b. else if approved.md doesn't exist → scripts/agents/run.sh draft
              (first round right after Step 1 Plan; no drafts yet)
          2.  scripts/leads/run.sh — one lead per role reviews its drafts
          3.  scripts/architect/run.sh review — validates leads, cross-role check
          4.  scripts/cycle/log.sh — records round log under plan/{n}/logs/
          stops when approved.md appears, or max_rounds hit (default 10)
  writes: plan/{n}/{role}/{topic}.md              — topic drafts
          plan/{n}/{role}/lead.md                 — per-role lead notes
          plan/{n}/raw/{role}:{topic}.md          — full LLM responses
          plan/{n}/raw/{role}:lead.md
          plan/{n}/raw/architect:review.md
          plan/{n}/corrections-verdict.md         — architect KEEP/DROP per note
          plan/{n}/corrections.md                 — merged corrections (until APPROVED)
          plan/{n}/decisions.md                   — appended durable decisions
          plan/{n}/approved.md                    — created when nothing left to fix

Step 3: Extract tasks (no LLM)
  script: scripts/executor/extract.sh {n}
  input:  all plan/{n}/{role}/{topic}.md (entries with task: lines only)
  output: plan/{n}/tasks.md — executable task list, grouped by plan tag
  note:   reviewer-only observations (no task: line) are excluded.

Step 4: Execute
  who:    executor agent (skill: execute.md)
  runner: Claude Code interactively OR a Claude Agent SDK harness
  reads:  plan/{n}/tasks.md + context/{role}/ + conventions
  writes: source files under apps/, docker/, e2e/, brand/, … each tagged with
          // [v84-{n}-x-x][{role}:{topic}]
  verify: run tests + build after each logical group of tasks.
  migration: as the LAST step, run
             `docker compose -f docker/dev/docker-compose.yml exec api \
              pnpm typeorm migration:generate \
              src/database/migrations/iteration-{n} -d src/database/data-source.ts`
             Name is always `iteration-{n}`. Never a task in tasks.md.
             No diff → no file produced, which is fine.
             If produced, tag with `// [v84-{n}][back-nestjs:entities]`.

Step 5: Finish (no LLM)
  script: scripts/executor/finish.sh {n} [--commit]
  input:  plan/{n}/{role}/{topic}.md + plan/{n}.md
  output: final/{role}/{topic}.md — new entries appended under
          "# --- iteration {n} ---"; replaced entries are marked
          final/plan.md — plan narrative appended
          trees/*.tree — regenerated from the new tag set
          git commit message: v84-{n}: promoted N entries (when --commit)
  note:   this is the ONLY script that writes to final/.
```

## Running the individual sub-scripts

`scripts/cycle/run.sh` is the normal entry point — it handles draft, lead, architect review, and patching in a loop. You only need the individual scripts when recovering from a stuck state, re-running one role, or debugging.

```
scripts/build-context.sh {n}        # rebuild context/ from current state
scripts/agents/run.sh {n} <p> <m> draft        # draft all topic agents (or patch)
scripts/agents/run.sh {n} <p> <m> draft role:topic1,role:topic2  # subset
scripts/leads/run.sh  {n} <p> <m>              # per-role lead review
scripts/architect/run.sh review {n} <p> <m>    # architect review
```

Every script leaves artifacts that later scripts pick up, so you can stop and resume between steps.

## Entry format (what agents write)

Each draft file uses entries with this shape:

```
[v84-{tag}]#{n} {one-line description}
  replaces: {tag}#{n|all}                 (optional — old code gets removed)
  expands: {tag}#{n}                      (optional — old code stays, adding to it)
  needs: {package} ({type}, {target})     (optional — triggers ops awareness)
  task: {imperative}                      (omit for reviewer observations)
  files: {paths}                          (omit for reviewer observations)
  depends: {tag}#{n}                      (optional — execution order)
```

Meaning:

- `replaces:` — this entry supersedes old work. Executor removes old code first.
- `expands:` — this entry adds to existing work. Executor reads old code, then modifies.
- `needs:` — new dependency required. Type: `dependency`, `dev`, `peer`, `docker`, `tool`. Target: `apps/api`, `apps/web`, `docker/dev`, etc. Ops leads see these and create install tasks.
- `task:` — what the executor does. Imperative. If absent, the entry is a reviewer observation.
- `files:` — where the executor writes. Comma-separated paths.
- `depends:` — another entry that must be done first.

Multiple entries per tag are allowed:

```
[v84-2-1-1]#1 User entity
  task: create entity with TypeORM decorators
  files: apps/api/src/modules/users/entities/user.entity.ts

[v84-2-1-1]#2 Session entity
  task: create entity for refresh-token sessions
  files: apps/api/src/modules/sessions/entities/session.entity.ts
```

Code tags use both plan tag and role:topic for bidirectional grep:

```typescript
// [v84-2-1-1][back-nestjs:entities]
@Entity()
export class User { ... }
```

## File flow

```
final/ + structure/conventions + trees/ + package.json + plan/{n}.md
        ↓ scripts/build-context.sh (auto)
context/{role}/{topic}/identity.md
        ↓ scripts/architect/run.sh plan
plan/{n}.md
        ↓ scripts/cycle/run.sh — loops: draft/patch → lead → architect
plan/{n}/{role}/{topic}.md
plan/{n}/{role}/lead.md
plan/{n}/corrections.md  |  plan/{n}/approved.md
        ↓ scripts/executor/extract.sh
plan/{n}/tasks.md
        ↓ executor writes code (Claude Code / SDK)
apps/** (tagged)
        ↓ scripts/executor/finish.sh [--commit]
final/{role}/{topic}.md + final/plan.md + trees/*.tree + (optional git commit)
```

## State tracking

File existence == pipeline state:

```
plan/{n}.md                   → Step 1 done
context/{role}/{topic}/…      → context ready (auto-rebuilt)
plan/{n}/{role}/{topic}.md    → draft exists
plan/{n}/{role}/lead.md       → lead review exists
plan/{n}/corrections.md       → patch round needed
plan/{n}/approved.md          → cycle converged
plan/{n}/tasks.md             → Step 3 done
final/plan.md has "iteration {n}"  → Step 5 done
```

## If something goes wrong

Rollback is a git operation:

- `git checkout -- apps/ docker/ e2e/` to revert source code.
- Keep `plan/{n}/` — the thinking is still valid.
- Keep `final/` — `finish.sh` hasn't run if execution failed.
- Re-run the failed step only; the scripts are idempotent where they can be.

## Re-run points

- Execution failed → re-run Step 4 (executor) and then Step 5.
- Tasks look wrong → delete `tasks.md`, delete `approved.md` to force another cycle round, or re-run Step 2 partially via `scripts/architect/run.sh review`, then Step 3.
- A role's drafts are wrong → delete that role's `plan/{n}/{role}/*.md`, re-run with `scripts/agents/run.sh {n} <p> <m> draft <role>:<topic>,…`, then continue the cycle.
- Plan is wrong → delete `plan/{n}.md` and `plan/{n}/`, re-run Step 1.
- Drafts edited after the fact (new entry, renamed tag, fixed path) and `final/` is now stale → `scripts/executor/finish-all.sh` nukes `final/` and replays Step 5 across every iteration in numeric order, so the promoted history matches the drafts exactly.
