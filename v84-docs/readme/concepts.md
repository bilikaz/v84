# Concepts

The core model of v84.

## Tasks are recursive

A project's work is one tree, persisted in `<project>/v84/core.yaml`:

```yaml
tasks:
  - id: v84-1
    task: |
      Scaffold the monorepo shell ...
    tasks:
      - id: v84-1.1
        task: |
          Set up workspace structure ...
      - id: v84-1.2
        task: |
          Add CI pipeline + lint ...
  - id: v84-2
    task: |
      Add user registration ...
```

Each top-level task is one **iteration**. Sub-tasks are added to a
task by the plan stage at iteration time. The id format is the
iteration number plus dotted indices: `v84-1.2.3` is the third
sub-task under `v84-1.2`. Code tagged `[v84-1.2.3]` ties a source
line to the task it was written for.

Two fields per task: `id` (harness-assigned) and `task` (one prose
block). No title/description split, no status field — completion
state lives in `current_iteration` + `completed_iterations` at the
top of `core.yaml`.

## Actions are concrete file-level work

Tasks describe outcomes; **actions** describe the file-level moves
that produce them. One action = one change to one file (or set of
files), authored by a role's writer:

```yaml
actions:
  - id: v84-1.1.frontend.1
    action: |
      Add the responsive page shell to index.html — meta viewport,
      a full-viewport flex container, and a centred .canvas div.
    files:
      - index.html
  - id: v84-1.2.frontend.1
    action: |
      Wire the atmospheric layer in <style> ...
    files:
      - index.html
    depends:
      - v84-1.1.frontend.1
```

Action ids encode the parent task, the role, and a per-task index
— `v84-1.2.frontend.1` is "frontend's first action under task
v84-1.2." Greppable in source code, in correction files, in
review suggestions.

## Four agent layers per iteration

Every iteration's work passes through four layers, each with one
narrow job:

| Layer       | Scope                            | Owns                                      |
|-------------|----------------------------------|-------------------------------------------|
| **Writer**  | one role's full surface          | drafting / patching the role's actions    |
| **Reviewer**| one lens within one role         | suggestions from a single angle of attack |
| **Lead**    | one role, role-internal only     | accepting / rejecting suggestions; setting role-scoped conv/dec |
| **Architect**| cross-role                      | catching what no single lead could see; proposing global conv/dec |

A role has one writer and (by default) four reviewers. There is
one lead per active role and exactly one architect across the
project. See [four-layer-split.md](four-layer-split.md) for the
responsibility detail and what each layer never does.

## The cycle loops until validate finds nothing left

Each iteration runs a cycle:

```
plan → draft → review → lead → architect → validate
                                              │
                              corrections still pending? ──┐
                                              │            │
                                  YES → round++, patch    │
                                              │            │
                                          patch → review → lead → architect → validate
                                              │                                    ↓
                                  NO  → user_review → done                  (loop back)
```

Round 1 starts with `draft` (writer drafts from scratch). Round 2
and beyond start with `patch` (writer applies the corrections that
landed). **validate** is the cycle-end gate — it counts pending
corrections across roles and either triggers a new cycle (with
patch) or hands off to user_review. See
[iteration-loop.md](iteration-loop.md) for the round mechanics
and the `status.yaml` state machine.

## Conventions vs decisions

Two stores for two kinds of rule:

- **Conventions** are durable rules that should apply across this
  and future iterations ("all DB columns use snake_case mapping").
- **Decisions** are one-shot rulings for this iteration only
  ("session timeout stays at 30 min in this scope").

Both flow through the same lifecycle:

1. Writer or reviewer raises a proposal in `needs_convention` /
   `needs_decision`.
2. Harness records it in the iteration's role-scoped store with
   `status: pending`.
3. Lead verdicts each pending entry: accept (with a final `rule`
   text) or reject. Rejected stays in the store for audit.
4. Architect emits its own globals into `iterations/<n>/global.*`,
   pending until cross-lead validation (Phase B).
5. user_review (Phase B) prompts the user to confirm everything
   accepted, then promotes to `<project>/v84/{role,global}.*`.

See [conventions-and-decisions.md](conventions-and-decisions.md)
for the full lifecycle and the `_load_rules` helper that reads
"in scope" rules from the right combination of root + iteration
files.

## Living documentation

`<project>/v84/` is the project's authoritative state — what's
been agreed, what's pending, what was rejected. Code references
back via `[v84-N.M.role.K]` tags. Iterations leave their full
working state under `iterations/<n>/`; the root-level `<role>.*`
and `global.*` files only fill in once the user_review gate
promotes accepted rules.

The on-disk shape is the source of truth. No state lives only in
agent context windows or LLM logs (those are audit, not state).

## Format discipline

YAML for everything structured. Markdown only for free-form
agent-instruction prose under `instructions/`. Per-field naming
follows two rules:

- `_id` for unique instance handles (`task_id`, `action_id`,
  `iteration_id`).
- `_tag` for category slugs from a known enum (`role_tag`,
  `reviewer_tag`).

Every prose field uses `|` block scalar to avoid YAML's plain-
scalar pitfalls (colon-followed-by-space, embedded quotes).
Details in [format.md](format.md).
