# v84

> Specification-driven development for AI coding agents.
> v84 produces the spec — your implementer (Claude Code, Cursor,
> a human) writes the code.

v84 is a documentation-and-harness system that turns "I want to
build X" into a structured, reviewed, tagged set of actions an
external code-writing agent can execute reliably. Iterations
loop a four-layer agent review (writer → 4 reviewers per role →
lead → architect) until the cycle stabilises, then hand off a
self-contained `tasks.md` spec for the implementer.

The point isn't to write code with AI. The point is to **make
the spec good enough that any code-writing agent — local Qwen,
Frontier Claude, a junior developer — produces converging,
correct output from it.**

## Why this exists

Most AI-coding flows look like: prompt → blob of code → manual
fix-up. That works for trivial tasks and falls apart on
multi-role brownfield work where:

- Decisions made in one part of the codebase silently break others
- Conventions drift across iterations because nothing enforces them
- Cheap local models can't hold enough context to stay coherent
- Frontier models burn tokens on details that should be settled once

v84 inverts the cost: spend more LLM calls *up front* to produce
a tight spec (with explicit conventions, decisions, action plans,
and tagging rules), then cheap implementers can execute it.
Empirically, a Qwen-27B Q3 quant running locally produces output
on par with Claude Opus when the spec carries the load —
[see the side-by-side](#the-thesis-in-one-experiment).

## How it works

Each project decomposes into a top-level task list (one task =
one iteration). Within an iteration:

```
plan         decompose this iteration's task into sub-tasks
draft        per-role writer drafts concrete actions (parallel)
review       per-role-per-lens reviewer suggestions (parallel,
             4 lenses per role)
lead         per-role lead synthesises (parallel)
architect    cross-role single call
validate     cross-lead vote on architect's globals + corrections check
patch        round 2+ writer applies corrections (parallel)
user_review  user reviews accepted conv/dec, promotes to project root,
             writes implementer handoff (tasks.md)
finish       verify file presence + tags, append to documentation,
             close iteration
```

The cycle loops (round 2, 3, …) until the architect has nothing
left to say. Each iteration accumulates conventions and decisions
that bind every future iteration — the spec gets sharper over time.

**Init phase** (run once per project): pick active roles → pick
the stack → decide repo layout (monorepo / single-app / flat /
scripts) + per-role section paths → decompose the brief into
top-level tasks.

**Iteration phase** (per top-level task): the cycle above.

**Handoff**: every closed iteration produces
`iterations/<n>/tasks.md` — a self-contained markdown doc with
plan + roles + active conventions + repo layout + tagging
convention + per-role action list. Hand it to your code-writing
agent. When the agent's done, re-run v84 and the `finish` stage
verifies every action's files exist and carry the right tag, or
emits a `fix.md` punch list for another pass.

## Quick start

```bash
# 1. Clone the repo
git clone https://github.com/bilikaz/v84.git
cd v84

# 2. Point at any LLM endpoint (local or hosted, OpenAI-compat)
python3 v84-docs/harness/v84.py --llm-set http://localhost:8000/v1

# 3. Run the harness from your project root
cd /path/to/your-project
python3 /path/to/v84-docs/harness/v84.py
```

The first run drops you into the **menu**:

```
v84 — main menu
project: /path/to/your-project
status:  fresh project — no v84/ folder yet

  > Start / resume      — run the next pending stage
    Setup LLM           — change endpoint or re-probe model
    Manage conventions  — review/edit project-promoted rules
    Manage decisions    — review/edit project-promoted rulings
    Quit
```

Pick **Start**. The harness walks you through init (roles → stack
→ structure → decompose), then runs the iteration cycle. When an
iteration converges, you'll review accepted conventions/decisions,
get the handoff `tasks.md`, run your implementer, then come back
and let `finish` verify.

## The thesis in one experiment

Same spec produced by v84, four different implementers asked to
build "tree growing in a field with farm animals around him":

| Model | Result | Issues |
|---|---|---|
| Claude Opus | Clean composition, layered tree, detailed animals | Sheep with two legs |
| Claude Sonnet | Pine tree + ringed sun (icon-style read of the brief) | Stylistic divergence |
| Claude Haiku | Round tree + animals on ground | Hard to recognize animals |
| Qwen-27B Q3.6 (local) | Layered tree + 3 animated clouds + all animals legged on ground | A single CSS unit bug; one-line fix |

After the unit fix, **the local Qwen output matched or beat the
Frontier Claude variants on composition.** Spec quality is the
dominant factor; once the spec is tight, capability differences
across the model tier compress dramatically.

## What v84 produces on disk

For each project under v84:

```
<your-project>/
├── v84/                            ← all v84 state
│   ├── profile.yaml                ← roles, stack, layout, llm config
│   ├── core.yaml                   ← task tree + iteration pointer
│   ├── structure/                  ← copied role + stack templates
│   ├── global.{conventions,decisions}.yaml   ← user-promoted rules
│   ├── <role>.{conventions,decisions}.yaml   ← per-role rules
│   ├── documentation/<role>.yaml   ← per-role implementation history
│   └── iterations/<n>/
│       ├── status.yaml
│       ├── plan.yaml               ← Q&A from sub-task planning
│       ├── <role>.yaml             ← writer's actions list
│       ├── reviews/                ← per-lens suggestions
│       ├── <role>.corrections*.yaml
│       ├── tasks.md                ← handoff for external implementer
│       ├── fix.md                  ← finish-stage punch list (if any)
│       └── cache/                  ← rendered context blocks (inspect)
└── <code>                          ← apps/, src/, etc.; tagged with
                                       [v84-N.M.role.K] back to the action
```

Every produced file traces back to an action via the
`[v84-N.M.role.K]` tag — greppable from source code to the
specific action that requested it.

## Design highlights

- **Four-layer review** — writer / 4 reviewers per role / lead /
  architect. Each layer has one narrow job. Reviewer is told to
  default to silence; lead synthesises; architect handles
  cross-role concerns. No layer's context grows unbounded.
- **Convention/decision accretion** — every iteration's reviewers
  and lead can raise rules. Lead-authored rules settle directly
  accepted (lead is the role's authority); architect-proposed
  globals go through cross-lead vote with rejection reasons
  recorded. User has the final say at iteration close.
- **Cross-iteration history** — per-role accumulated actions
  fed back as context to future writers, so the agent builds on
  top instead of redoing.
- **Local-LLM friendly** — small per-call scope (single role's
  surface for writers, single lens for reviewers) keeps cheap
  models inside their reliability envelope. vLLM prefix caching
  amortises the stable system + plan + role-definition prefixes.
- **Layout-aware** — projects pick monorepo / single-app / flat /
  scripts at init; per-role section paths flow into every action's
  `files:` field automatically.
- **Hand-off, not hand-craft** — v84 doesn't write your code. It
  writes the spec your code-writing agent reads.

## Documentation

The deep docs live under [`v84-docs/`](v84-docs/):

- [v84-docs/README.md](v84-docs/README.md) — system overview and
  reading order
- [v84-docs/readme/concepts.md](v84-docs/readme/concepts.md) — the
  core model (tasks, actions, agent layers, rounds, conv/dec)
- [v84-docs/readme/init-flow.md](v84-docs/readme/init-flow.md) —
  the four init stages
- [v84-docs/readme/cycle-flow.md](v84-docs/readme/cycle-flow.md)
  — what each iteration stage does, file by file
- [v84-docs/readme/iteration-loop.md](v84-docs/readme/iteration-loop.md)
  — round mechanics + the status state machine
- [v84-docs/readme/four-layer-split.md](v84-docs/readme/four-layer-split.md)
  — writer / reviewer / lead / architect responsibilities
- [v84-docs/readme/conventions-and-decisions.md](v84-docs/readme/conventions-and-decisions.md)
  — rule lifecycle (proposal → accepted → user-promoted)
- [v84-docs/readme/roles.md](v84-docs/readme/roles.md) — the eight
  role templates
- [v84-docs/readme/format.md](v84-docs/readme/format.md) — naming
  + YAML conventions, the marker pattern
- [v84-docs/readme/comparison.md](v84-docs/readme/comparison.md) —
  v84 vs spec-kit vs OpenSpec
- [v84-docs/readme/glossary.md](v84-docs/readme/glossary.md) —
  alphabetical reference

## Status

The full pipeline is wired end-to-end: init → plan → draft →
review → lead → architect → validate → patch → user_review →
finish. No stubs. The included sample project (`v84/`) is a
real iteration that produced the four-implementer comparison
above.

## Requirements

- Python 3.10+
- An OpenAI-compatible LLM endpoint (vLLM, llama.cpp, ollama,
  Anthropic API, OpenAI API, …)
- PyYAML

That's it. No Docker, no Node, no build step — the harness is
~3000 lines of Python.

## License

MIT
