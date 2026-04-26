# Comparison: v84 vs OpenSpec vs spec-kit

> Same thesis (specs drive code). Different answers to the same
> questions.

All three tools share the spec-driven thesis: specifications are
primary artefacts, code expresses them. They diverge on:

1. Is the spec **frozen** or **living**?
2. Is a change **one pass** or **iterative**?
3. Are there **phase gates** or **fluid** workflows?
4. Are there durable **engineering rules** (constitution / conventions)?
5. How are **multi-domain** changes handled?
6. How tightly is the spec tied to **code** after generation?

## At a glance

| Question                     | spec-kit             | OpenSpec             | v84                         |
|------------------------------|----------------------|----------------------|-----------------------------|
| Spec is                      | frozen per-feature   | living (delta merge) | living (per-iteration)      |
| Change flow                  | single pass          | single pass          | round-based loop            |
| Phase gates                  | yes (9 articles)     | none                 | yes (validate, user_review) |
| Constitution / conventions   | yes, immutable       | none                 | per-iteration + promoted    |
| Multi-domain changes         | single-agent         | single-agent         | role-split (writer per role)|
| Layered review               | none                 | none                 | writer + 4 reviewers + lead + architect |
| Stopping signal              | checklist complete   | manual "done"        | validate finds no corrections|
| Plan↔code traceability       | weak                 | weak                 | strong (dotted ids in tags) |
| Local-LLM friendly           | no                   | no                   | yes (scope narrowing per call)|
| LLM cost per change          | ~3 calls             | ~3 calls             | 13–37+ calls per round      |

## Where each shines

### spec-kit

- Greenfield features where the spec can be written once and
  implemented straight through.
- Constitution-driven discipline — every change obeys the same
  fixed articles.
- Ecosystem: first-class integrations across major IDEs and AI
  assistants.

### OpenSpec

- Brownfield change with low ceremony — propose, apply, archive.
- Living specs that grow through delta merges.
- Audit-friendly: dated archive folders preserve every change.

### v84

- Cascade-prone brownfield: changes whose second-order effects
  matter and need surfacing before code lands.
- Multi-domain work where ownership ambiguity across roles is the
  main failure mode.
- Diversity-of-perspective review: many narrow reviewers catch
  gaps a single broad reviewer misses.
- Living engineering rules that grow from iteration evidence
  rather than being frozen up front.
- Local LLM fit: per-call scope narrowing makes cheap models
  reliable inside a multi-step pipeline.

## What v84 takes from each

### From OpenSpec

- The "living documentation" thesis — `<project>/v84/` is the
  authoritative state, not a frozen snapshot.
- Per-iteration workspace folders that preserve the work in full
  (round-by-round + audit files).
- Idea of merging deltas rather than overwriting.

### From spec-kit

- The notion of project-wide engineering rules (our promoted
  conventions in `<project>/v84/{role,global}.conventions.yaml`).
- Authority concentration in a synthesising agent (our architect).

### New in v84

- Four-layer review split (writer / reviewer / lead / architect)
  with strict per-layer scope.
- Round-based cycle with validate as the cycle-end decider — stops
  on "no corrections left," not on a checklist.
- Recursive task tree as the project's source of truth, with
  per-iteration sub-task decomposition.
- Status-driven state machine (`status.yaml`) that drives stage
  dispatch and round transitions.
- Per-tier LLM concurrency configuration — fan-out stages parallel
  up to `multi.max_concurrency`, single-call stages stay on
  `single`.
- Iteration-anchored ids end-to-end (action ids in source tags,
  correction ids, suggestion ids — all greppable from the same
  prefix).

## What v84 deliberately does NOT take

### From spec-kit

- **Immutable constitution.** v84's conventions are living — they
  emerge from iteration evidence, can be edited at user_review,
  can be superseded.
- **Phase-gate checklists.** v84 stops on "no corrections left,"
  not on a list going green.
- **Single-agent spec pass.** No lens diversity; single-agent
  passes leak gaps.

### From OpenSpec

- **No phase gates.** v84 has them (validate, user_review).
- **Single-writer default.** v84 splits per role to keep ownership
  clean for multi-domain change.
- **Manual "done" trigger.** v84's architect + validate compute
  done-ness from emitted content.

## When to use which

| Situation                                  | Reach for                              |
|--------------------------------------------|----------------------------------------|
| Small greenfield project, one dev          | **spec-kit** — constitution + single pass fit |
| Brownfield, mostly one-domain changes      | **OpenSpec** — deltas + low ceremony fit |
| Brownfield, cross-cutting cascade-prone    | **v84** — loop + role split + per-role leads |
| Local LLM / cost-sensitive pipeline        | **v84** — per-call scope narrowing makes cheap models work |
| Scripting / one-off tools                  | **OpenSpec** or **v84 backend+testing only** |

## Honest summary

- **OpenSpec** is the cleanest if changes are mostly one-domain.
  Excellent storage model, minimal philosophy, no overhead.
- **spec-kit** is the most mature ecosystem play with constitutional
  discipline.
- **v84** is for hard changes — cross-cutting brownfield work where
  the loop pays off. It costs more LLM calls per change but pays
  back on ownership clarity and cascade-question surfacing.

For simple changes v84 is overkill — use OpenSpec or spec-kit.
For cascade-heavy multi-role work, v84 is the answer to "what
OpenSpec becomes when you need layered review on cheap local
models."
