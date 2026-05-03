# The Iteration Loop

> Adding small things breaks big things. The loop surfaces the
> breakages before code is written.

A single iteration is one task from `core.yaml`. The cycle inside
that iteration loops until `architect_validate` finds nothing
left to apply.

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
├── plan          →  decompose this iteration's task into sub-tasks
├── draft         →  per-role writer drafts actions (parallel)
├── review        →  per-role-per-lens reviewer corrections
│                    (parallel) → merged into <role>.corrections-pending.yaml
├── lead_round    →  TWO calls per role in parallel:
│                    review_validate (verdicts on pending corrections
│                    + rule proposals) AND lead.md (optional raises);
│                    two-phase write applies verdicts then raises.
├── architect     →  cross-role single call. Cross-role corrections
│                    land in each affected role's pending file (NOT
│                    directly in corrections.yaml); rules → globals.
└── architect_validate
                  →  one call per active lead, voting on:
                       • pending architect globals (single-veto)
                       • pending architect corrections targeting
                         this role (only this lead's vote counts)
                     Then count pending corrections in
                     <role>.corrections.yaml across roles:
                       YES  → round++, start patch (round 2),
                              narrow active_roles to roles with
                              pending corrections
                       NO   → hand off to user_review

Round 2 (or any later — only the active_roles set runs)
├── patch         →  per-role writer applies corrections (parallel)
├── review        →  re-evaluate the patched draft
├── lead_round    →  re-synthesise
├── architect     →  re-stitch cross-role
└── architect_validate
                  →  same checks; loop or close

After last architect_validate (corrections empty)
├── user_review   →  classify accepted rules (promote vs iteration-only),
│                    user ticks/picks/edits via review_list, picks one of:
│                       • continue   → promote, write tasks.md, advance
│                                      to finish
│                       • regenerate → promote, clear cycle artefacts,
│                                      reset to round 1 / draft
├── (external implementer runs: writes code from tasks.md)
└── finish        →  verify file existence + tag presence per action;
                     gaps → write fix.md, stay at finish for re-run;
                     pristine → append to documentation/<role>.yaml,
                     close iteration.
```

Round 1 starts with `draft` (writer drafts from scratch). Round 2+
starts with `patch` (writer applies the corrections that landed in
the prior round's lead_round + architect_validate output).

## status.yaml drives everything

Every iteration carries one tracking file:

```yaml
# iterations/<n>/status.yaml
round: 2
next_step: patch
active_roles: [frontend, backend]   # optional; narrowed by architect_validate
```

- Created by `plan` once the iteration's sub-task plan settles
  (`{round: 1, next_step: draft}`).
- Each stage's `is_done` reads `status.yaml`: a stage is done when
  its name no longer matches `next_step`.
- After running, each stage advances `next_step` to whatever comes
  next.
- Absence of `status.yaml` means the iteration hasn't started yet
  (only `plan` is ready).
- `active_roles` is the per-round role set. Round 1 sees every
  active role; `architect_validate` writes a narrowed list at
  end-of-round so the next round's stages skip roles with no
  pending corrections.

The transitions:

| After stage          | Transition                                                              |
|----------------------|-------------------------------------------------------------------------|
| plan                 | `iter_status.write(round=1, next_step="draft")`                         |
| draft                | `iter_status.advance_to("review")`                                      |
| review               | `iter_status.advance_to("lead_round")`                                  |
| lead_round           | `iter_status.advance_to("architect")`                                   |
| architect            | `iter_status.advance_to("architect_validate")`                          |
| architect_validate   | corrections pending → `iter_status.next_round_to("patch", active_roles=...)` |
|                      | corrections empty   → `iter_status.advance_to("user_review")`           |
| patch                | `iter_status.advance_to("review")`                                      |
| user_review (continue)| `iter_status.advance_to("finish")` (after promote + handoff)           |
| user_review (regen)  | `_restart_cycle` → `{round: 1, next_step: draft}`                       |
| finish               | gaps → write fix.md, stay at `finish` for re-run                        |
|                      | pristine → close iteration, `iter_status.advance_to("done")`            |

The round counter ticks at the architect_validate→patch
transition. That's when "we're starting a new cycle" semantically.
`architect_validate` itself sits in the round it ends.

## What the cycle stops on

The architect's job is cross-role synthesis. When it has nothing
to add — no corrections, no rejections, no global proposals — and
no lead corrections remain pending after architect_validate's
per-role lead vote, the corrections-presence check counts zero
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

- **Writers** produce concrete actions in parallel per role
  (`draft` round 1, `patch` round 2+).
- **Reviewers** pass single-lens critiques in parallel per role
  per lens. Their corrections merge into one
  `<role>.corrections-pending.yaml`.
- **Leads** are split across two parallel calls per role under
  `lead_round`: `review_validate` votes accept/reject on
  pending reviewer corrections + rule proposals; `lead.md` adds
  the lead's own raises on top.
- **Architect** stitches across roles: catches cross-role
  conflicts (deposited into each affected role's pending file),
  promotes patterns to global, rejects lead corrections that
  create cross-role problems.
- **architect_validate** is the cycle-end gate: each lead votes
  on architect-proposed globals (single-veto) AND on architect's
  cross-role corrections targeting that role (only that lead's
  vote counts). Then it counts what's left. **Patch** opens the
  next round.

## What survives across rounds

- `<role>.rules.yaml` carries status changes (pending → accepted /
  rejected) across rounds. Lead's prior verdicts are preserved.
- `<role>.corrections-rejected.yaml` carries history — both lead-
  rejected and architect-rejected entries with `rejected_by` tags.
- `<role>.corrections-applied.yaml` is the audit trail: when patch
  applies a correction, it moves from `corrections.yaml` to here so
  the next round's reviewers can verify it was honored.

The writer's `<role>.yaml` gets overwritten each round (round 1
draft, then patched in round 2+). Prior rounds' drafts live in
LLM call logs (`.v84-logs/`).

## Concurrency

Stages that fan out (draft, review, lead_round, patch,
architect_validate) use `call_many` against the multi tier when
configured (falls back to single if not). The tier's
`max_concurrency` from `profile.yaml` caps in-flight calls:

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

## What's still rough

The pipeline is end-to-end now; rough edges are about tuning
rather than missing stages:

- **Round 2+ active-roles narrowing** can cause re-introductions:
  if a corrected role's patch revives a cross-role concern that
  no longer reaches the architect (because the other role is
  skipped), the catch lands in a future round. Cheap, but
  mentioned for honesty.
- **Classifier defaults** for `user_review` are conservative
  (everything → promote on classifier failure). Worth tuning
  per-project once we've seen more rule-promotion churn.
- **fix.md re-runs** rely on the user manually invoking the
  external implementer; no auto-loop.
