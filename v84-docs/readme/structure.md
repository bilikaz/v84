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
├── instructions/                    ← agent prose + matching JSON Schemas
│   │                                  (every stage is a `.md` + `.schema.json`
│   │                                  pair — see readme/llm-format.md)
│   ├── init/
│   │   ├── suggest-roles.{md,schema.json}
│   │   ├── suggest-stack.{md,schema.json}
│   │   ├── suggest-structure.{md,schema.json}
│   │   └── decompose.{md,schema.json}
│   └── iteration/
│       ├── plan.{md,schema.json}
│       ├── draft.{md,schema.json}
│       ├── review.{md,schema.json}
│       ├── review_validate.{md,schema.json}    ← lead's verdict call
│       ├── lead.{md,schema.json}               ← lead's raise call
│       ├── architect.{md,schema.json}
│       ├── architect_validate.{md,schema.json} ← per-lead vote
│       ├── patch.{md,schema.json}
│       └── classify-rules.{md,schema.json}     ← user_review pre-bucket
├── harness/                         ← Python implementation (PyYAML only)
│   ├── v84.py                       ← CLI entry
│   ├── test_server.py               ← --test-server playground
│   ├── core/
│   │   ├── coreyaml.py              ← read/write core.yaml + id assignment
│   │   ├── context.py               ← prompt-context builders +
│   │   │                              declarative `build_user_msgs(spec)`
│   │   ├── proposals.py             ← per-iteration rules store
│   │   │                              + corrections (pending / accepted /
│   │   │                              rejected / applied) + verdicts
│   │   ├── iter_status.py           ← status.yaml read/write/advance
│   │   │                              (round, next_step, active_roles)
│   │   ├── registry.py              ← unified ALL_STAGES across init+iteration
│   │   ├── runner.py                ← stage-loop driver (shared by menu + CLI)
│   │   ├── stage.py                 ← Stage dataclass
│   │   ├── state.py                 ← project-state detection
│   │   ├── cache.py                 ← per-iteration disk cache for context
│   │   ├── versioning.py            ← opt-in archival of mutating LLM
│   │   │                              outputs (project.logging: true)
│   │   └── util.py
│   ├── llm/
│   │   ├── client.py                ← OpenAI-compat schema-validated JSON
│   │   │                              client (`call_json`); retries on
│   │   │                              parse / validation failure
│   │   ├── concurrent.py            ← `call_many` fan-out via threadpool
│   │   └── config.py                ← profile.yaml llm: tier resolution
│   ├── ui/
│   │   ├── _term.py                 ← alt-screen + read_key
│   │   ├── spinner.py               ← single-call live elapsed
│   │   ├── multi_spinner.py         ← N-track parallel-call display
│   │   ├── checklist.py
│   │   ├── single_select.py         ← supports `kind: header` rows
│   │   ├── field_editor.py          ← per-field skip/custom/recommendation labels
│   │   ├── detail_list.py
│   │   ├── text_input.py
│   │   ├── review_list.py           ← tick + drill + edit + action bar
│   │   └── confirm_modal.py         ← yes/no slip-protection guard
│   ├── menu/                        ← top-level interactive menu
│   │   ├── main.py                  ← single_select loop + dispatch
│   │   ├── start.py                 ← wraps core.runner
│   │   ├── setup_llm.py             ← LLM sub-menu (stub)
│   │   └── manage_rules.py          ← manage promoted rules
│   ├── tools/                       ← LLM-callable tools
│   │   ├── ask_user.py              ← single clarifying question
│   │   └── survey.py                ← batched questions w/ choices
│   ├── init/
│   │   ├── roles.py                 ← propose + select active roles
│   │   ├── stack.py                 ← propose + pick stack picks
│   │   ├── structure.py             ← propose layout type + per-role sections
│   │   └── decompose.py             ← brief → top-level tasks
│   └── iteration/
│       ├── plan.py                  ← task → sub-tasks (revise loop)
│       ├── draft.py                 ← round 1 writer (parallel per role)
│       ├── review.py                ← reviewers (parallel per lens)
│       ├── lead_round.py            ← parallel verdict + raise calls per
│       │                              role; writes split across phases A/B
│       ├── architect.py             ← cross-role single call
│       ├── architect_validate.py    ← per-lead vote on globals + per-role
│       │                              architect corrections; cycle-end check
│       ├── patch.py                 ← round 2+ writer (parallel per role)
│       ├── user_review.py           ← AI-classify accepted rules, user
│       │                              ticks/picks/edits via review_list,
│       │                              promote to root + write tasks.md
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
│   ├── global.rules.yaml            ← user-promoted global rules
│   ├── <role>.rules.yaml            ← user-promoted role-scoped rules
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
├── status.yaml                      ← {round: N, next_step: <stage>,
│                                      active_roles?: [..]}; plan creates it,
│                                      every stage advances it; architect_validate
│                                      narrows active_roles for round 2+
├── plan.yaml                        ← Q&A from sub-task planning (audit)
├── <role>.yaml                      ← writer's actions list (versioned via
│                                      core.versioning when project.logging on)
├── <role>.corrections-pending.yaml  ← reviewer corrections + architect's
│                                      cross-role corrections targeting this
│                                      role, awaiting the lead's verdict in
│                                      review_validate / architect_validate
├── <role>.corrections.yaml          ← lead-accepted reviewer corrections,
│                                      lead's own raises, lead-accepted
│                                      architect cross-role corrections;
│                                      cleared by patch each round
├── <role>.corrections-rejected.yaml ← rejected entries with `rejected_by`
│                                      tag (`<role>.reviewer` /
│                                      `<role>.lead` / `architect`)
│                                      + `reason` when set
├── <role>.corrections-applied.yaml  ← (round 2+) what patch applied — audit
│                                      so next round's reviewers can verify
├── <role>.rules.yaml                ← role-scoped rule proposals
│                                      (status: pending|accepted|rejected,
│                                       `reason` on rejected; `text` on accepted)
├── global.rules.yaml                ← architect's global proposals;
│                                      architect_validate fans out to leads
│                                      to vote; rejected carry `rejected_by:
│                                      <role>.lead` + `rejection_reason`
├── rule_classifications.yaml        ← AI pre-bucket cache for user_review
│                                      ({id: {bucket, reason}}); reused on
│                                      re-entry when the accepted-id set
│                                      hasn't changed
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

When `project.logging: true` is set in `profile.yaml`, every
overwrite of `<role>.yaml` archives the prior contents to
`<role>.yaml.<n>` (next-free integer) instead of dropping them —
useful for research, since you can step back through round 1's
draft, round 2's patch, round 3's patch, etc. side-by-side.

## File-by-file purpose

### Top-level project state

| File | Owns | Read by |
|---|---|---|
| `profile.yaml` | active roles + llm tiers + loop knobs + `project.layout_type` + `layout:` (per-role + global section paths) | every stage |
| `core.yaml` | task tree (recursive), `current_iteration`, `completed_iterations` | every stage |
| `structure/roles/*.yaml` | activated role definitions (responsibilities + 4 reviewers each) | writer, reviewer, lead, architect |
| `structure/stack/*.yaml` | per-role stack field templates (pinned) | writer, reviewer, lead, architect, patch |
| `global.rules.yaml` | user-promoted active global rules | every layer |
| `<role>.rules.yaml` | user-promoted active role-scoped rules | that role's writer/reviewer/lead/patch |
| `documentation/<role>.yaml` | per-role implementation history accumulated across iterations (parent task + sub-tasks + actions) | writer/patch (build-on-top), reviewer/lead (catch regressions) |

### Per-iteration files

| File | Written by | Read by |
|---|---|---|
| `status.yaml` | plan + every stage | harness state detection |
| `plan.yaml` | plan stage | future iterations' plan agent (cascade memory) |
| `<role>.yaml` | draft (round 1) / patch (round 2+) | reviewer, lead_round, architect, patch |
| `<role>.corrections-pending.yaml` | review (reviewer corrections), lead_round Phase A (rejected reviewer entries removed; accepted ones stay), lead_round Phase B (lead's own raises appended), architect raise (architect cross-role corrections) | lead_round (verdict call), architect (verdict call: lead_validate), architect_validate (per-role lead vote on architect cross-role) |
| `<role>.corrections.yaml` | architect Phase A on lead_validate accept (pending lead-blessed → binding), architect_validate (architect corrections accepted by lead), architect Phase A on rule accept (synth apply-correction) | patch, architect |
| `<role>.corrections-rejected.yaml` | lead_round Phase A (lead-rejected reviewer corrections), architect Phase A (architect-rejected lead-blessed corrections), architect_validate (architect cross-role rejected by lead) | architect (audit), future-round reviewer (verify) |
| `<role>.corrections-applied.yaml` | patch | next round's reviewers (verify what was honored) |
| `<role>.rules.yaml` | draft+review (pending), lead_round Phase A on accept (records lead's preferred `text`, status STAYS pending), lead_round Phase A on reject (status: rejected), lead_round Phase B (lead raises append as pending), architect Phase A (lead_validate accept → status: accepted; reject → status: rejected; promotes_from retirement → status: superseded), patch | lead_round, architect, patch, user_review |
| `global.rules.yaml` | architect (proposes), architect_validate (cross-lead vote → status update + rejection_reason) | architect (next round, with rejected globals visible), architect_validate, user_review |
| `rule_classifications.yaml` | user_review (cached output of `classify-rules` LLM call) | user_review on re-entry (cache reuse when accepted-id set unchanged) |
| `tasks.md` | user_review (on close path) | external implementer (Claude Code, Cursor, human) |
| `fix.md` | finish (when verification fails) | external implementer; cleared on next pristine pass |
| `cache/<func>.<role>.md` | draft/patch/review/lead_round via `core.cache` (write-through, mtime-keyed) | next stage call in same iteration; humans inspecting "what was sent" |

## What each tier reads (in scope)

`core.context.rules_block(role)` returns active rules in scope
for `role`. Sources:

- `v84/global.rules.yaml` — root globals
- `v84/<role>.rules.yaml` — root role-scoped
- `iterations/<n>/global.rules.yaml` filtered to `status: accepted`
- `iterations/<n>/<role>.rules.yaml` filtered to `status: accepted`

`pending_rules_block(role)` and `rejected_rules_block(role)` are
separate helpers; they only read iteration files.

A rule is by definition approved. Pending proposals and rejected
ones go through different helpers so callers are explicit about
what they want.

## Naming

- All file/dir names lowercase.
- Hyphenated for compound terms (`corrections-rejected.yaml`,
  `corrections-applied.yaml`).
- YAML keys snake_case (`task_id`, `action_id`, `next_step`).
- IDs are the dotted form (`v84-1.2.frontend.1`).
- Role tags bare (`frontend`, `devops`); reviewer tags bare
  (`pages`, `primitives`).

Details in [format.md](format.md).
