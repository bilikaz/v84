# The Four-Layer Split

> Writer owns a role. Reviewer owns a lens. Lead synthesises one
> role. Architect stitches across roles.

One layer, one job. The split exists because **ownership ambiguity
is the main failure mode of multi-agent pipelines**: when two
agents could plausibly own the same concern, both defer to the
other and gaps appear. v84 fixes responsibilities at four levels
with strict scopes.

## The four layers

| Layer       | Scope                          | Owns                                                            | Sees                                                                  |
|-------------|--------------------------------|-----------------------------------------------------------------|------------------------------------------------------------------------|
| **Writer**  | one role's full surface        | drafting / patching the role's actions                          | plan, role, stack, rules in scope, past iter drafts                    |
| **Reviewer**| one lens within one role       | corrections from a single angle of attack                       | plan, role, stack, rules, the role's writer draft                      |
| **Lead**    | one role, role-internal only   | accepting / rejecting reviewer corrections; raising own ones; setting role-scoped rules; voting on architect items targeting the role | plan, role, stack, rules, draft, all the role's reviewer corrections, post-verdict state for the raise call |
| **Architect**| cross-role                    | catching what no single lead saw; emitting global rules; final accept/reject on every lead-blessed correction and rule | plan, stack, full layout, all roles' bundles (drafts + lead-blessed corrections + lead-blessed rules), rejected globals from this iteration |

The lead's work runs across two LLM stages:
**`review_validate`** (verdicts on every pending reviewer
correction + rule proposal) and **`lead.md`** (optional own raises
on top). Both fire in parallel under the `lead_round` stage; the
harness applies verdicts first (Phase A), then raises (Phase B).
The lead's verdicts are **provisional** — accepted reviewer
items stay in `corrections-pending.yaml` and accepted rules stay
`status: pending`; the architect's `lead_validate` makes the
final binding call.

The architect's work also runs across two parallel LLM stages
under the `architect` stage: **`architect.md`** (raise: cross-
role corrections + global rule proposals) and
**`lead_validate.md`** (verdict: accept/reject on every lead-
blessed correction and rule in scope). The verdict call is gated
to fire only when scope is non-empty. Phase A applies verdicts
(transitions pending → final), Phase B applies raises. The
architect also fires once more during `architect_validate` (per-
lead vote) for cross-lead validation of its own globals + cross-
role corrections.

## Writer

**Inputs**: iteration plan, role definition, role's stack slice,
rules in scope (`rules_block(role=...)`), past iteration drafts
for the role.

**Output (round 1)**: `iterations/<n>/<role>.yaml` — an `actions`
list. Each action carries `id` (`<task_id>.<role_tag>.<n>`),
`action` prose, `files`, optional `depends`. The response may
also carry a `rules` array of proposals
(`{proposal, alternatives}`) — the harness strips those out of
the on-disk draft and lands them in `<role>.rules.yaml` with
`status: pending`.

**Output (round 2+)**: same shape, but the writer is the **patch**
stage rather than draft — applies the lead/architect corrections
to the existing draft, surviving actions keep their ids.

**Does not**: see other roles' work. Review its own output. Make
cross-cutting judgements.

## Reviewer

**Inputs**: its reviewer definition (a single `challenge` question),
the iteration plan, the role definition + stack + the role's repo
layout, rules in scope, the **role's full draft** (every action),
and the role's accumulated implementation history. On round 2+
also receives `<role>.corrections-applied.yaml` (what
the patch honored — verify, don't re-raise) and
`<role>.corrections-rejected.yaml` (what the lead / architect /
architect_validate already dismissed — don't re-raise).

**Output**: a `corrections` list and an optional `rules` list.
Each correction carries `verdict` (`fix`/`missing`/`remove`),
the appropriate id reference (`action_id` for `fix`/`remove`,
`task_id` for `missing`), and one short `correction` line.

The harness merges every reviewer's corrections for one role into
**one** file — `<role>.corrections-pending.yaml` — and assigns
each entry a harness-controlled id
(`v84-<n>.<role>.<reviewer_tag>.c.<m>`) so downstream layers can
reference them cleanly. There are no per-lens review files
anymore.

**Does not**: synthesise across lenses. Look at other roles. Decide
whether its concern is important enough to act on. Answer questions
outside its single lens.

## Lead

The lead's work runs across two LLM stages, executed in parallel
under `lead_round`:

### Verdict call — `review_validate`

**Inputs**: iteration plan, role definition + stack + layout,
role's draft, every pending correction in
`<role>.corrections-pending.yaml` (reviewer corrections from this
round; for round 2+ this file is reset before review fires), every
pending rule proposal raised this iteration for the role, rules
already in scope.

**Output**: `corrections` (`{id, verdict: accept|reject, reason?}`)
+ `rules` (`{id, verdict, text? on accept}`).

**Harness applies (Phase A — lead-blessed pending lifecycle)**:
accepted reviewer corrections **stay in
`<role>.corrections-pending.yaml`** (lead-blessed, awaiting
the architect's `lead_validate`); rejected ones move to
`<role>.corrections-rejected.yaml` with `rejected_by:
<role>.lead`. For pending rules: accepts keep `status: pending`
with the lead's preferred wording recorded in `text`; rejects
flip to `status: rejected`. No synthetic apply-correction is
generated here — the synth fires later when the architect's
`lead_validate` transitions a rule to `accepted`.

### Raise call — `lead.md`

**Inputs**: same context as the verdict call, plus the
post-verdict view (the verdict call's accepted set, rejected
entries this iteration, rejected globals from architect with
reasons). Sees this even though it fires in parallel: both calls
read the SAME pre-vote disk state and the raise call is told
which concerns the verdicts are about to settle so it doesn't
duplicate them.

**Output**: `corrections` (lead's own additions in correction
shape) + `rules` (lead-authored `{proposal, alternatives}`).

**Harness applies (Phase B)**: lead corrections append to
`<role>.corrections-pending.yaml` with ids
`v84-<n>.<role>.lead.c.<m>` (lead-blessed, awaiting the
architect's `lead_validate`); lead rules append to
`<role>.rules.yaml` as `status: pending` with ids
`v84-<n>.<role>.lead.rule.<m>`. The architect's verdict makes
the final accepted/rejected decision in its Phase A.

**Lead does not**: see other roles. Override the architect's
globals. Look at corrections from other roles. Touch rules marked
global.

### Architect-validate vote

The lead also fires once more during `architect_validate` to vote
on architect-proposed globals (every lead votes, single-veto)
AND on architect cross-role corrections targeting this role
(only this lead's vote counts).

The lead exists so the architect's context stays small. Each lead
handles their role's per-correction accept/reject and per-role
rule verdicts; the architect deals only with cross-role concerns.

## Architect

The architect runs across TWO parallel LLM calls under the
`architect` stage — a raise call (`architect.md`) and a
verdict call (`lead_validate.md`). Both see the same pre-vote
state. The verdict call is gated to fire only when scope is
non-empty.

### Raise call — `architect.md`

**Inputs**: iteration plan, full stack, every active role's
bundle (writer's draft + lead-blessed corrections + lead-
blessed rules), active global rules from the project root,
globals rejected earlier this iteration.

**Output** (two required arrays — each may be empty):

- `corrections` — cross-role catches. Same shape as a lead's
  correction but tagged `for_role` for missing-type entries
  since `task_id` alone doesn't encode role. Routed into the
  relevant role's `<role>.corrections-pending.yaml` (NOT
  directly into `corrections.yaml` — `architect_validate` asks
  the affected role's lead to vote first) with id
  `v84-<n>.architect.c.<m>`.
- `rules` — global proposals the architect would enact. Land
  in `iterations/<n>/global.rules.yaml` with
  `status: pending` (`architect_validate` runs cross-lead
  voting; `user_review` then promotes ticked-as-promote
  entries to `<project>/v84/global.rules.yaml`).

### Verdict call — `lead_validate.md`

**Inputs**: same bundle as the raise call.

**Output** (two required arrays — each may be empty):

- `corrections` — `{id, verdict, reason?}` per lead-blessed
  correction in scope (excludes architect cross-role
  corrections, which are voted on by `architect_validate`).
- `rules` — `{id, verdict, reason?}` per role-scoped rule in
  scope (lead-blessed pending + already-accepted from earlier
  rounds).

Phase A of the architect stage applies these verdicts:
accepts move pending corrections to `corrections.yaml` and
flip pending rules to `accepted` (with synth apply-correction);
rejects move corrections to `corrections-rejected.yaml` and
flip rules to `rejected` (retracting any prior synth
apply-correction).

**Does not**: write actions. Review from one lens. Re-litigate
per-role rulings the leads already verdicted on rejected items.

After architect runs, `architect_validate` fires — one fan-out
LLM call per active lead voting on the architect's pending
globals + cross-role corrections, followed by a corrections-count
check that either triggers a new cycle (round++, next_step=patch,
narrowed `active_roles`) or hands off to user_review.

## Why this shape

An earlier version of v84 had three layers (writer / reviewer /
architect). The architect's context grew unbounded — every
reviewer correction across every role had to fit, and the
architect ended up doing per-correction accept/reject work that
was conceptually role-internal. Adding the lead layer compresses
each role's reviewer output into a focused punch list before it
reaches the architect.

A "lead per role" also gives the architect a clean per-role unit
to reason about: one writer's draft + one lead's corrections =
one role's contribution. The architect synthesises across those
contributions instead of synthesising raw reviewer corrections.

The lead's split into two LLM calls (verdict + raise) was added
when leads that did both in one call routinely skipped the
verdicts after raising lots of additions, or vice versa. Two
narrow calls beat one wide call empirically.

## Scaling the counts

The shape stays; the numbers vary with active roles:

| Profile                | Roles | Reviewers | Lead calls (verdict+raise) | Architect | architect_validate |
|------------------------|-------|-----------|----------------------------|-----------|--------------------|
| CLI tool               |   2   |     8     |       up to 4              |     1     |        2           |
| Backend API service    |   3   |    12     |       up to 6              |     1     |        3           |
| Fullstack web SaaS     |   5   |    20     |       up to 10             |     1     |        5           |
| Fullstack + mobile     |   6   |    24     |       up to 12             |     1     |        6           |

A single round on the smallest profile is up to
2 (writer) + 8 (review) + 4 (lead_round = 2 per role) +
1 (architect) + 2 (architect_validate) = 17 LLM calls; on the
largest it's up to 6 + 24 + 12 + 1 + 6 = 49. The verdict half of
`lead_round` is skipped for roles with nothing pending, and
`architect_validate` is skipped entirely when neither globals nor
per-role architect corrections are pending — typical mid-cycle
rounds run lighter than the maximum.

Concurrency caps from `profile.yaml`'s `llm.<tier>.max_concurrency`
control how many fire in parallel. See
[iteration-loop.md](iteration-loop.md) for round mechanics and how
many rounds typically run.
