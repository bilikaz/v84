# Init Flow

> From "I want to build X" to "iteration 1 can plan."

Init runs four stages once per project: pick active roles, pick
the stack, decide the repo layout (type + per-role section paths
+ optional `global` for monorepo root files), decompose the brief
into tasks. Each produces a persistent file under
`<project>/v84/`; the harness picks up where you left off if you
re-run.

## Stage 1: roles

Driven by `instructions/init/suggest-roles.md` and
`harness/init/roles.py`.

**Three phases:**

1. **AI proposes** — reads the project brief, picks role-tags from
   the menu (`init/roles/*.yaml`'s `when_activate` text), and emits
   a short `summary` describing the overall project shape and why
   those roles fit together.
2. **User selects** — the AI's `summary` is printed first as
   context, then a multi-select painter (`ui/checklist.py`) shows
   the AI's pre-selection; user toggles, confirms.
3. **Templates copied** — for each active role,
   `init/roles/<name>.yaml` is copied to
   `<project>/v84/structure/roles/<name>.yaml` so the project
   owns an editable copy.

**Outputs**:
- `<project>/v84/profile.yaml` with the resolved llm endpoint,
  loop knobs, and the selected `roles:` list.
- `<project>/v84/structure/roles/<name>.yaml` per active role.

The `profile.yaml` `llm:` block has two tiers (`single`, `multi`),
each with `url`, `model`, `max_concurrency`. `single` is the
default for one-at-a-time stage calls; `multi` is the fan-out
endpoint (writers, reviewers, leads, patches). When `multi` is
absent, fan-out falls back to `single`.

## Stage 2: stack

Driven by `instructions/init/suggest-stack.md` and
`harness/init/stack.py`.

**Per active role**, the AI proposes picks for each stack field
(`init/stack/<role>.yaml` defines the field set per role —
backend has language/framework/database/orm/etc., devops has
containers/deployment/ci_cd/etc., frontend has language/build/
framework/ui/state/styling).

**The user reviews** via `ui/field_editor.py` — a three-mode
painter (review → pick → custom). For each field they accept the
AI's pick, choose an alternative, or type a custom value. ESC at
the outer level cancels.

**Outputs**:
- `profile.yaml` gains a `stack:` block — one entry per active
  role, every field present (skipped fields are literally `none`,
  not absent — downstream stages see the full schema and can't
  hallucinate fields they didn't see).
- `<project>/v84/structure/stack/<role>.yaml` per active role
  (pinned copy of the source template; v84-docs updates don't
  retroactively reshape existing projects).

## Stage 3: structure

Driven by `instructions/init/suggest-structure.md` and
`harness/init/structure.py`.

**Single LLM call** — agent reads the brief + active roles + stack
picks and proposes:
- `layout_type`: `monorepo`, `single-app`, `flat`, or `scripts`
- For each active role: a list of `{name, path, notes?}` sections
  matching the role's responsibilities + stack (Next.js earns
  `pages` + `components`; NestJS earns `modules` + `entities` +
  `migrations`; etc.)
- For `monorepo` layout type: a `global` section list with
  project-wide root files (workspace manifest, root package.json,
  root tsconfig, .gitignore, .nvmrc) — these don't belong to any
  single role.

**User reviews each scope sequentially** via the `field_editor`
UI: one role (or `global`) at a time, accept the AI's path
verbatim, switch to a custom path, or drop the section. ESC at
any scope keeps that scope's AI proposal as-is and moves to the
next.

**Outputs**:
- `profile.yaml` gains `project.layout_type` and a `layout:` block
  keyed by `global` (when present) and each active role:
  ```yaml
  project:
    layout_type: monorepo
  layout:
    global:
      - {name: workspace, path: pnpm-workspace.yaml}
      - {name: root_package, path: package.json}
    frontend:
      - {name: app, path: apps/web}
      - {name: pages, path: apps/web/src/pages}
    backend:
      - ...
  ```

No new folder under `v84/structure/` — there's nothing
template-shaped for layout (the AI proposes from scratch per
project), so chosen values live directly in `profile.yaml`. Same
storage pattern as the `stack:` block.

## Stage 4: decompose

Driven by `instructions/init/decompose.md` and
`harness/init/decompose.py`.

**Single LLM call** (with revise loop): brief → top-level tasks.

**Inputs to the agent**:
- The brief (loaded from `<project>/v84/brief.md` if cached;
  otherwise prompted)
- Active roles (compact menu)
- Stack picks

**Output**: `tasks: [...]` — an ordered list of top-level entries
each with one `task` prose block. The agent calibrates count to
project tier (Trivial 1-3, Simpler 3-8, Serious 8-20, Complex
20-30); no padding.

**Revise loop**: user reviews via `ui/detail_list.py`, can either
accept or revise with a comment. Comment goes back to the agent
for another round. On accept:

- `<project>/v84/core.yaml` written:
  ```yaml
  tasks:
    - id: v84-1
      task: |
        ...
    - id: v84-2
      task: |
        ...
  current_iteration: null
  completed_iterations: []
  ```
  Ids are harness-assigned (`v84-N`); the agent emits only
  `task` prose. No status field — `current_iteration` and
  `completed_iterations` track execution position.
- `<project>/v84/brief.md` is **deleted**. Tasks become the source
  of truth from this point; downstream stages do not consult the
  brief.

## What's on disk after init

```
<project>/v84/
├── profile.yaml                 ← roles, stack, layout type +
│                                  per-role section paths,
│                                  llm tiers, loop
├── core.yaml                    ← top-level tasks
└── structure/
    ├── roles/<name>.yaml         ← per active role
    └── stack/<name>.yaml         ← per active role
```

`iterations/` is empty. The next harness run hits `plan` (the
first iteration stage) which decomposes `core.yaml`'s first
top-level task into sub-tasks and creates
`iterations/1/status.yaml`.

## Resumption

Every init stage produces persistent files; re-running the
harness picks up at the first stage whose output is missing:

- No `profile.yaml` → start at `roles`.
- `profile.yaml` exists, no `roles:` block → start at `roles`.
- `profile.yaml` has roles, no `stack:` block → start at `stack`.
- `profile.yaml` has roles + stack, no `layout:` block → start at
  `structure`.
- `profile.yaml` complete, no `core.yaml` → start at `decompose`.
- All four present → init done; jump to `plan` (or whatever
  iteration stage is next per `status.yaml`).

User dropout mid-stage is safe — partial UI state isn't persisted,
but committed picks (e.g. roles already toggled and confirmed)
are. Re-run continues where the last successful stage left off.
