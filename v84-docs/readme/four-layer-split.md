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
| **Writer**  | one role's full surface        | drafting / patching the role's actions                          | plan, role, stack, conv/dec in scope, past iter drafts                 |
| **Reviewer**| one lens within one role       | suggestions from a single angle of attack                       | plan, role, stack, conv/dec, the role's writer draft                   |
| **Lead**    | one role, role-internal only   | accepting / rejecting suggestions; setting role-scoped conv/dec | plan, role, stack, conv/dec, draft, all the role's reviewer suggestions |
| **Architect**| cross-role                    | catching what no single lead saw; emitting global conv/dec      | plan, stack, all roles' bundles (drafts + corrections + accepted rules) |

## Writer

**Inputs**: iteration plan, role definition, role's stack slice,
conventions/decisions in scope (`conventions_block(role=...)`),
past iteration drafts for the role.

**Output (round 1)**: `iterations/<n>/<role>.yaml` — an `actions`
list. Each action carries `id` (`<task_id>.<role_tag>.<n>`),
`action` prose, `files`, optional `depends`. May also raise
`needs_convention` / `needs_decision` proposals.

**Output (round 2+)**: same shape, but the writer is the **patch**
stage rather than draft — applies the lead/architect corrections
to the existing draft, surviving actions keep their ids.

**Does not**: see other roles' work. Review its own output. Make
cross-cutting judgements.

## Reviewer

**Inputs**: its reviewer definition (a single `challenge` question),
the iteration plan, the role definition + stack, conventions/
decisions in scope, the **role's full draft** (every action). On
round 2+ also receives `<role>.corrections-applied.yaml` (what
the patch honored — verify, don't re-raise) and
`<role>.corrections-rejected.yaml` (what the lead/architect
already dismissed — don't re-raise). Both are filtered to the
reviewer's own past suggestions plus role-wide lead/architect
entries; other reviewers' lens-specific items are excluded.

**Output**: `iterations/<n>/reviews/<role>.<reviewer_tag>.yaml` —
a `suggestions` list, each entry carrying `verdict`
(`fix`/`missing`/`remove`), the appropriate id reference
(`action_id` for `fix`/`remove`, `task_id` for `missing`), and one
short `suggestion` line. Reviewer may also raise needs_convention /
needs_decision proposals.

The harness assigns each suggestion an id
(`v84-<n>.<role>.<reviewer_tag>.s.<m>`) so downstream layers can
reference suggestions cleanly.

**Does not**: synthesise across lenses. Look at other roles. Decide
whether its concern is important enough to act on. Answer questions
outside its single lens.

## Lead

**Inputs**: iteration plan, role definition, role's stack, role's
draft, **every reviewer suggestion for this role merged into one
list** (with harness-assigned ids and source reviewer_tag), every
pending convention/decision proposal raised this iteration for the
role, conventions/decisions already in scope. On round 2+ also
receives the **full** `<role>.corrections-applied.yaml` and
`<role>.corrections-rejected.yaml` — no per-reviewer filter, since
the lead owns the role's whole punch list and needs to track which
items were already honored or already dismissed.

**Output**: a verdict + raises response that the harness splits
across files. Lead can both verdict pending raises AND author its
own role-scoped conv/dec which settle directly accepted (lead is
the role's authority — no higher layer to verdict role-scoped
rules). Splits as follows:

- `<role>.corrections.yaml` — accepted reviewer suggestions
  (echoed verbatim with their ids) plus the lead's own
  corrections (harness-assigned ids `v84-<n>.<role>.lead.c.<m>`).
- `<role>.corrections-rejected.yaml` — rejected suggestions tagged
  `rejected_by: lead`, with the original suggestion text echoed
  for audit.
- `<role>.conventions.yaml` / `<role>.decisions.yaml` — pending
  entries get their `status` updated in place to `accepted` (with
  the lead's `rule` text) or `rejected`.

**Does not**: see other roles. Override the architect's globals.
Look at corrections from other roles. Touch conv/dec marked global.

The lead exists so the architect's context stays small. Each lead
handles their role's per-suggestion accept/reject and per-role
conv/dec verdicts; the architect deals only with cross-role concerns.

## Architect

**Inputs**: iteration plan, full stack, every active role's
**bundle** (writer's draft + lead's corrections + lead's rejected
corrections + accepted role-scoped conv/dec), active global
conv/dec from the project root.

**Output**: a response that the harness routes per field:

- `corrections` — cross-role catches. Same shape as a lead's
  correction but tagged `for_role` for missing-type entries since
  `task_id` alone doesn't encode role. Routed into the relevant
  role's `<role>.corrections.yaml` with id
  `v84-<n>.architect.c.<m>`.
- `rejected_corrections` — list of correction ids from any lead
  that the architect overrides. Each gets moved from its role's
  corrections file to its rejected file, tagged
  `rejected_by: architect`.
- `proposed_conventions` / `proposed_decisions` — global proposals
  the architect would enact. Land in
  `iterations/<n>/global.{conventions,decisions}.yaml` with
  `status: pending` (cross-lead validation in Phase B will
  validate them; user_review will then promote accepted ones to
  `<project>/v84/global.{conventions,decisions}.yaml`).

**Does not**: write actions. Review from one lens. Override
conventions in-cycle. Re-litigate per-role decisions the leads
made.

After architect runs, validate fires (no LLM call) — counts
pending corrections across roles and either triggers a new cycle
(round++, next_step=patch) or hands off to user_review.

## Why this shape

An earlier version of v84 had three layers (writer / reviewer /
architect). The architect's context grew unbounded — every reviewer
suggestion across every role had to fit, and the architect ended
up doing per-suggestion accept/reject work that was conceptually
role-internal. Adding the lead layer compresses each role's
reviewer output into a focused punch list before it reaches the
architect.

A "lead per role" also gives the architect a clean per-role unit
to reason about: one writer's draft + one lead's corrections =
one role's contribution. The architect synthesises across those
contributions instead of synthesising raw reviewer suggestions.

## Scaling the counts

The shape stays; the numbers vary with active roles:

| Profile                | Roles | Reviewers | Leads | Architect |
|------------------------|-------|-----------|-------|-----------|
| CLI tool               |   2   |     8     |   2   |     1     |
| Backend API service    |   3   |    12     |   3   |     1     |
| Fullstack web SaaS     |   5   |    20     |   5   |     1     |
| Fullstack + mobile     |   6   |    24     |   6   |     1     |

A single iteration on the smallest profile is 2 + 8 + 2 + 1 = 13
LLM calls per round; on the largest it's 6 + 24 + 6 + 1 = 37.
Concurrency caps from `profile.yaml`'s `llm.<tier>.max_concurrency`
control how many fire in parallel. See
[iteration-loop.md](iteration-loop.md) for round mechanics and how
many rounds typically run.
