# The Iteration Loop

> Adding small things breaks big things. The loop surfaces the
> breakages before code is written.

A single iteration is one task from `core.yaml`. The cycle inside
that iteration loops until validate finds nothing left to apply.

## Why a loop

Real software change is rarely one-shot. Adding a feature to an
existing system raises questions elsewhere — almost always:

- Adding 2FA → session timeout needs review, audit logging needs
  a new event type.
- Adding a background worker → Docker compose needs a new service,
  alerting needs the new worker.
- Adding an export endpoint → rate-limit tiers need re-thinking,
  PII classification of exported fields needs review.

These are *second-order consequences* — questions only visible
after the first-order change is drafted. The loop is the mechanism
for surfacing them before code lands.

## The shape

```
Round 1
├── plan        →  decompose this iteration's task into sub-tasks
├── draft       →  per-role writer drafts actions (parallel)
├── review      →  per-role-per-lens reviewer suggestions (parallel)
├── lead        →  per-role lead synthesises (parallel)
├── architect   →  cross-role single call
└── validate    →  cross-lead vote on architect's pending globals
                   (single-veto, with rejection_reason captured),
                   then count pending corrections:
                   YES  →  round++, start patch (round 2)
                   NO   →  hand off to user_review

Round 2 (or any later)
├── patch       →  per-role writer applies corrections (parallel)
├── review      →  re-evaluate the patched draft
├── lead        →  re-synthesise
├── architect   →  re-stitch cross-role
└── validate    →  same checks; loop or close

After last validate (corrections empty)
├── user_review →  user reviews accepted conv/dec, promotes to root,
│                  writes tasks.md handoff, advances to finish.
│                  (If user changed any rule's text → cycle restart
│                   instead, back to draft with new rule set.)
├── (external implementer runs: writes code from tasks.md)
└── finish      →  verify file existence + tag presence per action;
                   gaps → write fix.md, stay at finish for re-run;
                   pristine → append to documentation/<role>.yaml,
                   close iteration.
```

Round 1 starts with `draft` (writer drafts from scratch). Round 2+
starts with `patch` (writer applies the corrections that landed in
the prior round's lead + architect output).

## status.yaml drives everything

Every iteration carries one tracking file:

```yaml
# iterations/<n>/status.yaml
round: 2
next_step: patch
```

- Created by `plan` once the iteration's sub-task plan settles
  (`{round: 1, next_step: draft}`).
- Each stage's `is_done` reads `status.yaml`: a stage is done when
  its name no longer matches `next_step`.
- After running, each stage advances `next_step` to whatever comes
  next.
- Absence of `status.yaml` means the iteration hasn't started yet
  (only `plan` is ready).

The transitions:

| After stage | Transition                                                          |
|-------------|---------------------------------------------------------------------|
| plan        | `iter_status.write(round=1, next_step="draft")`                     |
| draft       | `iter_status.advance_to("review")`                                  |
| review      | `iter_status.advance_to("lead")`                                    |
| lead        | `iter_status.advance_to("architect")`                               |
| architect   | `iter_status.advance_to("validate")`                                |
| validate    | corrections pending → `iter_status.next_round_to("patch")` (round++)|
|             | corrections empty   → `iter_status.advance_to("user_review")`       |
| patch       | `iter_status.advance_to("review")`                                  |
| user_review | no change → `iter_status.advance_to("finish")` (after promote + handoff)|
|             | any rule edited → `_restart_cycle` → `{round: 1, next_step: draft}` |
| finish      | gaps → write fix.md, stay at `finish` for re-run                    |
|             | pristine → close iteration, `iter_status.advance_to("done")`        |

The round counter ticks at the validate→patch transition. That's
when "we're starting a new cycle" semantically. Validate itself
sits in the round it ends.

## What the cycle stops on

The architect's job is cross-role synthesis. When it has nothing
to add — no corrections, no rejections, no global proposals — and
no lead corrections remain pending, validate counts zero corrections
and routes to user_review.

That's the stopping signal: **no corrections left to apply
anywhere.** Not a checklist going green. Not a maximum round
cap (we don't have one). Convergence happens when the cascade of
questions raised by the original change has stabilised.

Early rounds usually have many corrections (the obvious second-
order questions surface). Later rounds have few (third-order
tweaks). For focused changes, convergence usually lands in 2-3
rounds.

## The role of each cycle layer

See [four-layer-split.md](four-layer-split.md) for layer detail.
Briefly:

- **Writers** produce concrete actions in parallel per role.
- **Reviewers** pass single-lens critiques in parallel per role
  per lens.
- **Leads** synthesise per role: accept/reject suggestions, settle
  role-scoped conv/dec.
- **Architect** stitches across roles: catches cross-role conflicts,
  promotes patterns to global, rejects lead corrections that create
  cross-role problems.
- **Validate** counts what's left. **Patch** opens the next round.

## What survives across rounds

- `<role>.conventions.yaml` / `<role>.decisions.yaml` carry status
  changes (pending → accepted / rejected) across rounds. Lead's
  prior verdicts are preserved.
- `<role>.corrections-rejected.yaml` carries history — both lead-
  rejected and architect-rejected entries with `rejected_by` tags.
- `<role>.corrections-applied.yaml` is the audit trail: when patch
  applies a correction, it moves from `corrections.yaml` to here so
  the next round's reviewers can verify it was honored.

The writer's `<role>.yaml` gets overwritten each round (round 1
draft, then patched in round 2+). Prior rounds' drafts live in
LLM call logs (`.v84-logs/`).

## Concurrency

Stages that fan out (draft, review, lead, patch) use `call_many`
against the multi tier when configured (falls back to single if
not). The tier's `max_concurrency` from `profile.yaml` caps
in-flight calls:

```yaml
llm:
  single:
    url: ...
    model: ...
    max_concurrency: 1
  multi:
    url: ...
    model: ...
    max_concurrency: 4
```

Architect always runs as a single call.

## Failure handling

- Per-call failure (one role's writer raised an exception):
  preserved in the `CallResult`; other roles' calls finish
  normally. The stage raises with the count of failed calls;
  re-running the stage retries those that didn't have output.
- Stage outputs are persisted before status advances, so an
  interrupt mid-stage leaves the previous status; re-running the
  stage rewrites its outputs.
- `status.yaml` is the only state-of-truth read by `next_pending`,
  so dropping it (or editing it) lets the user replay or skip
  steps.

## Looking ahead

Phase B fills in:
- **patch**'s actual implementation (round-2+ writer with
  `instructions/iteration/patch.md` already in place).
- **user_review** UI gate that promotes accepted conv/dec to the
  project root and closes the iteration.
- **Cross-lead validation** of architect-proposed globals inside
  validate (currently validate is a pure corrections-count check).
