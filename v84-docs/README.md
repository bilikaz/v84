# v84

> Specification-driven development with a multi-role review cycle.
> Tasks are recursive. Reviews are layered. Iterations loop until
> the architect's catches stop landing.

v84 is a documentation-and-code system for AI-assisted software
development. A project's `v84/` directory holds the authoritative
description of what's being built and how each iteration's work was
agreed; running code is a faithful translation of what's there.

The contribution v84 makes over plain spec-driven flows is the
**multi-role review cycle**: each iteration's work passes through
four agent layers (writer / reviewer / lead / architect) before
the iteration closes. Each layer has one job and a narrow scope,
and the cycle iterates round-by-round until cross-cutting questions
stop surfacing.

## Status

The full pipeline is wired end-to-end:

- **init**: roles → stack → structure → decompose
- **iteration**:
  - **plan** → decompose iteration into sub-tasks
  - **pre-pass** → rules_lead → rules_architect → rules_validate
    → rules_consolidate → user_rules_review (front-loads the
    iteration's binding rules before any actions are drafted)
  - **cycle** → draft → review → lead_round → architect (raise +
    verdict in parallel) → architect_validate → patch (round 2+)
  - **close** → user_review → finish (verify file presence +
    tags, write `documentation/<role>.yaml`, close iteration)

`lead_round` fires two LLM calls per role in parallel: a verdict
call (`review_validate.md`) on every reviewer correction +
pending rule, and a raise call (`lead.md`) for additions the
reviewers missed. The `architect` stage similarly fires two LLM
calls in parallel: a raise call (`architect.md`) for cross-role
corrections + global rule proposals, and a verdict call
(`lead_validate.md`) voting accept/reject on every lead-blessed
correction and rule in scope. The verdict call is gated — it
fires only when scope is non-empty. `architect_validate` is a
single fan-out per lead that votes on architect-proposed globals
(single-veto) and architect's cross-role corrections targeting
that role.

## The lead-blessed pending lifecycle

Rules and corrections stay `pending` through every layer that
hasn't yet judged them. Reviewer corrections the lead accepts
and lead's own raises both stay in `<role>.corrections-pending.yaml`
until the architect's `lead_validate` makes the final call —
accepted ones move to `<role>.corrections.yaml` (binding for
patch), rejected ones move to `<role>.corrections-rejected.yaml`.
Same for rules: lead's accept records the lead's preferred
wording but doesn't flip status; the architect's accept in
`lead_validate` is what transitions a rule to `accepted` and
synthesizes its apply-correction. `corrections.yaml` is
architect-blessed only — a clean punch list for patch.

v84 produces the spec; an external implementer (Claude Code,
Cursor, a human) executes the actions. After each successful
iteration finish writes `iterations/<n>/tasks.md` for that
implementer; on re-entry, finish verifies file existence + tag
presence and either writes `iterations/<n>/fix.md` or closes the
iteration.

## The model in one paragraph

A project decomposes into a top-level task list (`core.yaml`).
Each task is one iteration. An iteration starts by planning its
sub-tasks, then a **pre-pass** front-loads the iteration's
binding rules: each lead proposes 5–7 role-internal rules; the
architect proposes 8–12 cross-role globals; per-lead validation
votes single-veto on globals; architect consolidation rejects
lead rules that conflict, drift, or duplicate; the user gates
which rules promote to project root before drafting starts.
Then the **cycle** runs: every active role's writer drafts
concrete actions, every reviewer (one per lens, four per role)
emits corrections. `lead_round` fires two parallel LLM calls per
role — verdict votes accept/reject on pending reviewer items;
raise optionally adds the lead's own corrections and rules. The
**architect** stage fires two parallel calls: raise emits
cross-role corrections + global proposals; verdict
(`lead_validate`) votes accept/reject on every lead-blessed
correction and rule in scope. `architect_validate` fans out one
call per lead voting on architect's globals (single-veto) and
cross-role corrections. Pending corrections remain → round++ and
patch opens the new cycle; otherwise → `user_review` classifies
+ promotes the iteration's mid-cycle rules and writes the
implementer handoff. The iteration closes via the finish stage
once every action's files exist and carry the right tag. Rules
and per-role implementation history accrete iteration by
iteration under `<project>/v84/`.

## How to read these docs

1. [readme/concepts.md](readme/concepts.md) — the core model
   (tasks, actions, agent layers, rounds, rules).
2. [readme/structure.md](readme/structure.md) — folder layout in
   v84-docs/ and in a project's `v84/`, with what each file holds.
3. [readme/four-layer-split.md](readme/four-layer-split.md) —
   the writer / reviewer / lead / architect responsibility split.
4. [readme/iteration-loop.md](readme/iteration-loop.md) — round
   mechanics, status.yaml state machine, validate's cycle-end check.
5. [readme/cycle-flow.md](readme/cycle-flow.md) — what each stage
   does inside one iteration, file-by-file.
6. [readme/init-flow.md](readme/init-flow.md) — first-run walkthrough.
7. [readme/roles.md](readme/roles.md) — the eight role templates
   and the per-role four reviewer lenses.
8. [readme/rules.md](readme/rules.md)
   — the lifecycle of rules (proposal → pending → accepted/rejected
   → user-promoted to project root).
8a. [readme/rule-initial-session.md](readme/rule-initial-session.md)
   — the pre-pass: five stages between `plan` and `cycle` that
   settle the iteration's binding rules before any actions are
   drafted.
9. [readme/format.md](readme/format.md) — naming + YAML conventions
   (snake_case, `_id` vs `_tag`, block scalars, the marker).
10. [readme/comparison.md](readme/comparison.md) — where v84 sits
    next to spec-kit and OpenSpec.
11. [readme/glossary.md](readme/glossary.md) — alphabetical reference.
12. [readme/screens.md](readme/screens.md) — visual + behavioural
    reference for every interactive screen (painters, modals,
    keymaps, signatures).
13. [readme/llm-format.md](readme/llm-format.md) — the JSON-on-
    the-wire / YAML-on-disk boundary, the `.md` + `.schema.json`
    instruction-pair shape, retry + streaming behaviour.
14. [readme/playground.md](readme/playground.md) — the local
    `--test-server` web playground for iterating on prompts.
15. [readme/ai-protocol.md](readme/ai-protocol.md) — design for a
    file-based question/answer protocol so non-TTY orchestrators
    can drive the harness. Forward-looking — the `--ai` flag is
    not yet implemented.

## Directory layout (this repo, the v84 system)

```
v84-docs/
├── README.md                       ← this file
├── readme/                         ← conceptual docs
├── init/
│   ├── roles/<name>.yaml           ← role templates copied at init
│   └── stack/<name>.yaml           ← stack field templates per role
├── instructions/                   ← agent system prompts +
│   │                                  matching JSON Schemas
│   ├── init/
│   │   ├── suggest-roles.{md,schema.json}
│   │   ├── suggest-stack.{md,schema.json}
│   │   ├── suggest-structure.{md,schema.json}
│   │   └── decompose.{md,schema.json}
│   └── iteration/
│       ├── plan.{md,schema.json}
│       ├── rules_lead.{md,schema.json}        ← pre-pass: per-role lead proposes
│       ├── rules_architect.{md,schema.json}   ← pre-pass: cross-role globals
│       ├── rules_validate.{md,schema.json}    ← pre-pass: per-lead vote on globals
│       ├── rules_consolidate.{md,schema.json} ← pre-pass: architect dedup pass
│       ├── draft.{md,schema.json}
│       ├── review.{md,schema.json}
│       ├── review_validate.{md,schema.json}   ← lead's verdict call
│       ├── lead.{md,schema.json}              ← lead's raise call
│       ├── architect.{md,schema.json}         ← architect's raise call
│       ├── lead_validate.{md,schema.json}     ← architect's verdict call
│       ├── architect_validate.{md,schema.json}← per-lead vote
│       ├── patch.{md,schema.json}
│       └── classify-rules.{md,schema.json}    ← user_{rules_,}review pre-bucket
└── harness/                        ← Python implementation
    ├── v84.py                      ← CLI entry
    ├── test_server.py              ← --test-server playground
    ├── core/                       ← shared helpers (registry,
    │                                  state, iter_status, context,
    │                                  cache, proposals, coreyaml,
    │                                  runner, versioning, util)
    ├── llm/                        ← OpenAI-compat schema-validated
    │                                  JSON client + fan-out
    ├── ui/                         ← terminal painters (single_select,
    │                                  checklist, field_editor,
    │                                  detail_list, text_input,
    │                                  spinner, multi_spinner,
    │                                  review_list, confirm_modal)
    ├── menu/                       ← top-level interactive menu
    │                                  (Start / Setup LLM /
    │                                  Manage rules)
    ├── tools/                      ← LLM-callable tools
    │                                  (ask_user, survey)
    ├── init/                       ← init stages (roles, stack,
    │                                  structure, decompose)
    └── iteration/                  ← iteration stages (plan;
                                       pre-pass: rules_lead,
                                       rules_architect, rules_validate,
                                       rules_consolidate,
                                       user_rules_review;
                                       cycle: draft, review, lead_round,
                                       architect (raise + lead_validate
                                       in parallel), architect_validate,
                                       patch; close: user_review, finish;
                                       handoff + documentation are
                                       non-stage helpers called from
                                       finish / user_review)
```

## Directory layout (a project using v84)

```
<project-root>/
├── v84/
│   ├── profile.yaml                ← roles + stack picks +
│   │                                  layout type + per-role +
│   │                                  global section paths + llm
│   ├── core.yaml                   ← task tree + iteration pointer
│   ├── structure/
│   │   ├── roles/<name>.yaml       ← copies of activated role templates
│   │   └── stack/<name>.yaml       ← copies of stack templates
│   ├── global.rules.yaml           ← user-promoted global rules
│   ├── <role>.rules.yaml           ← user-promoted role-scoped rules
│   ├── documentation/<role>.yaml   ← per-role implementation history,
│   │                                  appended on each iteration close
│   └── iterations/<n>/             ← per-iteration workspace
│       ├── status.yaml             ← {round, next_step, active_roles?}
│       ├── plan.yaml               ← Q&A from sub-task planning
│       ├── <role>.yaml             ← writer draft (actions list)
│       ├── <role>.corrections-pending.yaml
│       │                              ← reviewer corrections + architect
│       │                                cross-role corrections, awaiting
│       │                                lead validation
│       ├── <role>.corrections.yaml ← lead-accepted punch list (the
│       │                              writer's input for patch)
│       ├── <role>.corrections-rejected.yaml
│       ├── <role>.corrections-applied.yaml  (round 2+)
│       ├── <role>.rules.yaml       ← per-role pending/accepted/rejected
│       ├── global.rules.yaml       ← architect-proposed; lead-validated
│       ├── tasks.md                ← handoff for external implementer
│       ├── fix.md                  ← finish stage punch list (when gaps)
│       ├── rule_classifications.yaml  ← AI pre-bucket cache (user_review)
│       └── cache/                  ← rendered context blocks
│                                      (mtime-keyed, inspectable)
└── <code>                          ← apps/, src/, etc., tagged with
                                       [v84-N.M.role.K]
```

Full per-file detail in [readme/structure.md](readme/structure.md).
