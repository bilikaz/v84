# Structure

Folder layout — both the v84-docs/ system and a project that uses it.

## v84-docs/ (this repo)

```
v84-docs/
├── README.md
├── readme/                          ← these conceptual docs
├── init/
│   ├── roles/<name>.yaml            ← 8 role templates copied at init
│   └── stack/<name>.yaml            ← per-role stack field templates
├── instructions/                    ← agent system prompts
│   ├── init/
│   │   ├── suggest-roles.md
│   │   ├── suggest-stack.md
│   │   └── decompose.md
│   └── iteration/
│       ├── plan.md
│       ├── draft.md
│       ├── review.md
│       ├── lead.md
│       ├── architect.md
│       └── patch.md
├── harness/                         ← Python implementation (PyYAML only)
│   ├── v84.py                       ← CLI entry
│   ├── core/
│   │   ├── coreyaml.py              ← read/write core.yaml + id assignment
│   │   ├── context.py               ← prompt-context builders
│   │   │                              (roles_block, stack_block,
│   │   │                              plan_block, conventions_block,
│   │   │                              decisions_block + pending/rejected
│   │   │                              variants)
│   │   ├── proposals.py             ← per-iteration conv/dec store
│   │   │                              + corrections + suggestion gathering
│   │   ├── iter_status.py           ← status.yaml read/write/advance
│   │   ├── registry.py              ← unified ALL_STAGES across init+iteration
│   │   ├── runner.py                ← stage-loop driver (shared by menu + CLI)
│   │   ├── stage.py                 ← Stage dataclass
│   │   ├── state.py                 ← project-state detection
│   │   ├── cache.py                 ← per-iteration disk cache for context
│   │   └── util.py
│   ├── llm/
│   │   ├── client.py                ← OpenAI-compat call + marker parsing
│   │   ├── concurrent.py            ← call_many fan-out via threadpool
│   │   └── config.py                ← profile.yaml llm: tier resolution
│   ├── ui/
│   │   ├── _term.py                 ← alt-screen + read_key
│   │   ├── spinner.py               ← single-call live elapsed
│   │   ├── multi_spinner.py         ← N-track parallel-call display
│   │   ├── checklist.py
│   │   ├── single_select.py         ← supports `kind: header` rows
│   │   ├── field_editor.py          ← per-field skip/custom/recommendation labels
│   │   ├── detail_list.py
│   │   └── text_input.py
│   ├── menu/                        ← top-level interactive menu
│   │   ├── main.py                  ← single_select loop + dispatch
│   │   ├── start.py                 ← wraps core.runner
│   │   ├── setup_llm.py             ← LLM sub-menu (stub)
│   │   └── manage_rules.py          ← manage promoted conv/dec
│   ├── init/
│   │   ├── roles.py                 ← propose + select active roles
│   │   ├── stack.py                 ← propose + pick stack picks
│   │   ├── structure.py             ← propose layout type + per-role sections
│   │   └── decompose.py             ← brief → top-level tasks
│   └── iteration/
│       ├── plan.py                  ← task → sub-tasks (revise loop)
│       ├── draft.py                 ← round 1 writer (parallel per role)
│       ├── review.py                ← reviewers (parallel per lens)
│       ├── lead.py                  ← per-role synthesis (parallel)
│       ├── architect.py             ← cross-role single call
│       ├── validate.py              ← cross-lead globals + corrections check
│       ├── patch.py                 ← round 2+ writer (parallel per role)
│       ├── user_review.py           ← promote conv/dec + write tasks.md handoff
│       ├── handoff.py               ← renders iterations/<n>/tasks.md (helper)
│       ├── documentation.py         ← appends to documentation/<role>.yaml
│       └── finish.py                ← verify files+tags, close iteration
```

## A project using v84

```
<project-root>/
├── v84/                             ← all v84 state
│   ├── profile.yaml                 ← active roles + llm tiers + loop knobs
│   │                                  + project.layout_type + layout:
│   │                                  block (per-role + global sections)
│   ├── core.yaml                    ← task tree + iteration pointer
│   ├── structure/
│   │   ├── roles/<name>.yaml        ← copied + editable role templates
│   │   └── stack/<name>.yaml        ← copied stack templates (pinned to project)
│   ├── global.conventions.yaml      ← user-promoted global rules
│   ├── global.decisions.yaml
│   ├── <role>.conventions.yaml      ← user-promoted role-scoped rules
│   ├── <role>.decisions.yaml
│   ├── documentation/
│   │   └── <role>.yaml              ← per-role implementation history,
│   │                                  appended on each iteration close
│   └── iterations/
│       └── <n>/                     ← per-iteration workspace
└── <code>                           ← apps/, src/, etc., tagged with [v84-N.M.role.K]
```

## Inside `iterations/<n>/`

Per-iteration workspace. Built up stage by stage, files added as
the cycle progresses.

```
iterations/<n>/
├── status.yaml                      ← {round: N, next_step: <stage>}
│                                      created by plan, advanced by every stage
├── plan.yaml                        ← Q&A from sub-task planning (audit)
├── <role>.yaml                      ← writer's actions list
├── reviews/
│   └── <role>.<reviewer_tag>.yaml   ← per-lens suggestions (with harness ids)
├── <role>.corrections.yaml          ← lead-accepted suggestions + lead's own
│                                      + architect's cross-role catches
├── <role>.corrections-rejected.yaml ← rejected entries with `rejected_by` tag
│                                      + `rejection_reason` (when set by lead)
├── <role>.corrections-applied.yaml  ← (round 2+) what patch applied — audit
│                                      so next round's reviewers can verify
├── <role>.conventions.yaml          ← role-scoped conv proposals
│                                      (status: pending|accepted|rejected,
│                                       `rejection_reason` on rejected)
├── <role>.decisions.yaml            ← same shape for decisions
├── global.conventions.yaml          ← architect's global proposals;
│                                      validate fan-outs to leads to vote;
│                                      rejected carry `rejected_by:
│                                      <role>.lead` + `rejection_reason`
├── global.decisions.yaml            ← same for decisions
├── tasks.md                         ← handoff for external implementer,
│                                      written by user_review on close
├── fix.md                           ← finish-stage punch list (only when
│                                      file/tag verification fails)
└── cache/                           ← rendered context blocks per
    └── <func>.<role>.md                builder, mtime-validated; used
                                        by draft / patch / review / lead
                                        to skip re-rendering and to
                                        inspect "what was sent"
```

## File-by-file purpose

### Top-level project state

| File | Owns | Read by |
|---|---|---|
| `profile.yaml` | active roles + llm tiers + loop knobs + `project.layout_type` + `layout:` (per-role + global section paths) | every stage |
| `core.yaml` | task tree (recursive), `current_iteration`, `completed_iterations` | every stage |
| `structure/roles/*.yaml` | activated role definitions (responsibilities + 4 reviewers each) | writer, reviewer, lead, architect |
| `structure/stack/*.yaml` | per-role stack field templates (pinned) | writer, reviewer, lead, architect, patch |
| `global.conventions.yaml` | user-promoted active global conventions | every layer |
| `global.decisions.yaml` | same for decisions | every layer |
| `<role>.conventions.yaml` | user-promoted active role-scoped conventions | that role's writer/reviewer/lead/patch |
| `<role>.decisions.yaml` | same for decisions | same |
| `documentation/<role>.yaml` | per-role implementation history accumulated across iterations (parent task + sub-tasks + actions) | writer/patch (build-on-top), reviewer/lead (catch regressions) |

### Per-iteration files

| File | Written by | Read by |
|---|---|---|
| `status.yaml` | plan + every stage | harness state detection |
| `plan.yaml` | plan stage | future iterations' plan agent (cascade memory) |
| `<role>.yaml` | draft (round 1) / patch (round 2+) | reviewer, lead, architect, patch |
| `reviews/<role>.<reviewer>.yaml` | review stage | lead, architect |
| `<role>.corrections.yaml` | lead (initial), architect (appends cross-role) | patch, architect |
| `<role>.corrections-rejected.yaml` | lead, architect | architect (audit), future-round reviewer (verify) |
| `<role>.corrections-applied.yaml` | patch | next round's reviewers (verify what was honored) |
| `<role>.conventions.yaml` | draft+review (pending), lead (status updates) | lead, architect, patch |
| `<role>.decisions.yaml` | same | same |
| `global.conventions.yaml` | architect (proposes), validate (lead vote → status update + rejection_reason) | architect (next round, with rejected globals visible), validate, patch |
| `global.decisions.yaml` | same | same |
| `tasks.md` | user_review (on close path) | external implementer (Claude Code, Cursor, human) |
| `fix.md` | finish (when verification fails) | external implementer; cleared on next pristine pass |
| `cache/<func>.<role>.md` | draft/patch/review/lead via `core.cache` (write-through, mtime-keyed) | next stage call in same iteration; humans inspecting "what was sent" |

## What each tier reads (in scope)

`core.context.conventions_block(role)` returns active conventions
in scope for `role`. Sources:

- `v84/global.conventions.yaml` — root globals
- `v84/<role>.conventions.yaml` — root role-scoped
- `iterations/<n>/global.conventions.yaml` filtered to `status: accepted`
- `iterations/<n>/<role>.conventions.yaml` filtered to `status: accepted`

`pending_conventions_block(role)` and
`rejected_conventions_block(role)` are separate helpers; they only
read iteration files. Same trio for decisions.

The convention is: a "convention" by definition is approved. Pending
proposals and rejected ones go through different helpers so callers
are explicit about what they want.

## Naming

- All file/dir names lowercase.
- Hyphenated for compound terms (`corrections-rejected.yaml`,
  `corrections-applied.yaml`).
- YAML keys snake_case (`task_id`, `action_id`, `next_step`).
- IDs are the dotted form (`v84-1.2.frontend.1`).
- Role tags bare (`frontend`, `devops`); reviewer tags bare
  (`pages`, `primitives`).

Details in [format.md](format.md).
