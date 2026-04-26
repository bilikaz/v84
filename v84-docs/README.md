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
- **iteration cycle**: plan → draft → review → lead → architect →
  validate (with cross-lead validation of architect's globals) →
  patch (round 2+) → user_review → finish (verify file presence
  + tags, write `documentation/<role>.yaml`, close iteration)

v84 produces the spec; an external implementer (Claude Code,
Cursor, a human) executes the actions. After each successful
iteration finish writes `iterations/<n>/tasks.md` for that
implementer; on re-entry, finish verifies file existence + tag
presence and either writes `iterations/<n>/fix.md` or closes the
iteration.

## The model in one paragraph

A project decomposes into a top-level task list (`core.yaml`).
Each task is one iteration. An iteration starts by planning its
sub-tasks, then runs a cycle: every active role's writer drafts
concrete actions, every reviewer (one per lens, four per role)
critiques from a single angle, the role's lead synthesises the
suggestions, the architect stitches across roles, validate
fan-outs to the leads to vote on architect-proposed globals and
checks whether anything still needs fixing. If corrections remain
→ patch starts a new round; if not → user_review promotes
accepted rules and writes the implementer handoff. Iteration
closes via the finish stage once every action's files exist and
carry the right tag. Conventions, decisions, and per-role
implementation history accrete iteration by iteration under
`<project>/v84/`.

## How to read these docs

1. [readme/concepts.md](readme/concepts.md) — the core model
   (tasks, actions, agent layers, rounds, conv/dec).
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
8. [readme/conventions-and-decisions.md](readme/conventions-and-decisions.md)
   — the lifecycle of rules (proposal → pending → accepted/rejected
   → user-promoted to project root).
9. [readme/format.md](readme/format.md) — naming + YAML conventions
   (snake_case, `_id` vs `_tag`, block scalars, the marker).
10. [readme/comparison.md](readme/comparison.md) — where v84 sits
    next to spec-kit and OpenSpec.
11. [readme/glossary.md](readme/glossary.md) — alphabetical reference.

## Directory layout (this repo, the v84 system)

```
v84-docs/
├── README.md                       ← this file
├── readme/                         ← conceptual docs
├── init/
│   ├── roles/<name>.yaml           ← role templates copied at init
│   └── stack/<name>.yaml           ← stack field templates per role
├── instructions/                   ← agent system prompts
│   ├── init/{suggest-roles,suggest-stack,suggest-structure,decompose}.md
│   └── iteration/{plan,draft,review,lead,architect,patch,validate-globals}.md
└── harness/                        ← Python implementation
    ├── v84.py                      ← CLI entry
    ├── core/                       ← shared helpers (registry,
    │                                  state, status, context,
    │                                  cache, proposals, coreyaml,
    │                                  runner)
    ├── llm/                        ← OpenAI-compat client + fan-out
    ├── ui/                         ← terminal painters
    ├── menu/                       ← top-level interactive menu
    │                                  (Start / Setup LLM /
    │                                  Manage conv / Manage dec)
    ├── init/                       ← init stages (roles, stack,
    │                                  structure, decompose)
    └── iteration/                  ← iteration stages (plan, draft,
                                       review, lead, architect,
                                       validate, patch, user_review,
                                       finish; handoff +
                                       documentation are non-stage
                                       helpers called from finish)
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
│   ├── global.conventions.yaml     ← user-promoted global rules
│   ├── global.decisions.yaml
│   ├── <role>.conventions.yaml     ← user-promoted role-scoped rules
│   ├── <role>.decisions.yaml
│   ├── documentation/<role>.yaml   ← per-role implementation history,
│   │                                  appended on each iteration close
│   └── iterations/<n>/             ← per-iteration workspace
│       ├── status.yaml             ← {round, next_step}
│       ├── plan.yaml               ← Q&A from sub-task planning
│       ├── <role>.yaml             ← writer draft (actions list)
│       ├── reviews/<role>.<reviewer_tag>.yaml
│       ├── <role>.corrections.yaml
│       ├── <role>.corrections-rejected.yaml
│       ├── <role>.corrections-applied.yaml  (round 2+)
│       ├── <role>.conventions.yaml ← per-role pending/accepted/rejected
│       ├── <role>.decisions.yaml
│       ├── global.conventions.yaml ← architect-proposed; lead-validated
│       ├── global.decisions.yaml
│       ├── tasks.md                ← handoff for external implementer
│       ├── fix.md                  ← finish stage punch list (when gaps)
│       └── cache/                  ← rendered context blocks
│                                      (mtime-keyed, inspectable)
└── <code>                          ← apps/, src/, etc., tagged with
                                       [v84-N.M.role.K]
```

Full per-file detail in [readme/structure.md](readme/structure.md).
