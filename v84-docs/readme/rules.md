# Rules

> One stream for the durable rulings the project lives by. Same
> data shape, same lifecycle, no internal split.

## What a rule is

Rules are durable rulings — pattern-rules ("all DB columns use
snake_case mapping", "every CSS animation respects
`prefers-reduced-motion`") and factual choices ("session timeout =
30 min", "auth uses HS256 signed cookies") alike — settled via the
verdict/raise lifecycle. The earlier conventions-vs-decisions split
was vestigial; in practice both shapes need the same proposal,
verdict, promote, and in-scope reading mechanics, so they share one
store.

A rule is by definition approved. Pending proposals and rejected
proposals live behind their own helpers; the bare term "rule"
implies a record that has cleared its verdict gate.

## Lifecycle (lead-blessed pending until architect)

Rules move through three layers — each layer's verdict is
**provisional** until the next layer up confirms. A rule only
binds (`status: accepted`) once the architect's `lead_validate`
call has explicitly accepted it.

```
1. Writer or reviewer raises a proposal in their `rules` array
   (`{proposal, alternatives}`).
        ↓
2. Harness assigns id, writes to <role>.rules.yaml as
   {status: pending, proposal, alternatives}.
        ↓
3. The verdict call inside `lead_round` (instruction:
   `review_validate.md`) verdicts each pending entry's `rules`:
     - accept → status STAYS `pending`; the lead's preferred
       wording is recorded on the record's `text` field. The
       architect's `lead_validate` makes the final decision.
     - reject → status: rejected (with `reason`,
       `rejected_by: <role>.lead`). Rejected entries stay in
       the file as audit.
        ↓
3b. The raise call inside `lead_round` (instruction: `lead.md`)
    may also raise the lead's OWN role-scoped rules. Same
    `{proposal, alternatives}` shape so the architect sees
    full context (lead's preferred form + considered
    alternatives) at verdict time. These also land
    `status: pending` in `<role>.rules.yaml` with ids
    `v84-N.<role>.lead.rule.<m>` — lead is the role's authority
    on raising, but the architect still rules cross-role.
        ↓
4. The architect stage fires `lead_validate.md` in parallel with
   the raise call. lead_validate votes `accept` or `reject` on
   every role-scoped rule in scope (lead-blessed pending rules
   from this iteration + already-accepted rules from earlier
   rounds). Phase A applies the verdicts:
     - pending + accept → status: accepted; `text` preserved;
       harness synthesizes the rule's `<rule_id>.apply`
       correction in `<role>.corrections.yaml` so patch
       (next round) updates the draft to comply.
     - pending + reject → status: rejected with `rejected_by:
       architect` and `rejection_reason`.
     - accepted + accept → no-op (rule stays binding).
     - accepted + reject → flip to rejected and retract the
       rule's synthetic apply-correction so patch doesn't
       carry a now-rejected rule forward.
        ↓
5. The architect's raise call (`architect.md`) emits its own
   globals into iterations/<n>/global.rules.yaml with
   status: pending. The `architect_validate` stage that runs
   next fans out a per-lead call to vote on every pending
   global from each role's perspective (alongside per-role
   architect-correction voting). Single-veto rule: any reject →
   status: rejected, with `rejected_by: <role>.lead` and a
   `rejection_reason` recorded; otherwise → status: accepted.
   Rejected globals stay in the file (carrying their reason)
   so the next round's architect sees what was shot down and
   why.
        ↓
6. user_review classifies every accepted rule (promote vs
   iteration-only) via the `classify-rules` LLM call, then shows
   them to the user via `review_list`. Ticked entries promote
   on `[c] continue` or `[r] regenerate`:
   - role-scoped → <project>/v84/<role>.rules.yaml
   - global    → <project>/v84/global.rules.yaml
   Choosing `regenerate` clears cycle artefacts and resets to
   round 1 so the new draft pass reads the updated rule set.
```

**Pre-pass parallel**: at the start of an iteration, before
draft, the rule_initial_session pre-pass runs five stages
(`rules_lead` → `rules_architect` → `rules_validate` →
`rules_consolidate` → `user_rules_review`) that produce and
settle the iteration's foundational rules using the same
proposal / verdict shapes described above. See
[rule-initial-session.md](rule-initial-session.md).

## Record shape

Pending / accepted / rejected entries (in iteration files):

```yaml
- id: v84-1.frontend.rule.1            ← harness-assigned
  proposal: |                          ← agent's preferred form
    Wrap CSS animations in @media (prefers-reduced-motion: no-preference).
  alternatives:
    - |
      Single :root toggle for all motion.
    - |
      Always-on with UI pause control.
  status: pending | accepted | rejected
  text: |                              ← only when status: accepted
    <lead's final wording>             ← canonical text used by other agents
```

Promoted entries (in `<project>/v84/{<role>,global}.rules.yaml`)
drop the proposal-time fields and keep just the canonical form:

```yaml
- id: v84-1.frontend.rule.1
  text: |
    <the rule, as the lead/user enacted it>
```

The YAML key is `text`. Prose can still call it "the rule's
wording."

## Id format

Source determines prefix:

| Source                 | Id format                                          |
|------------------------|----------------------------------------------------|
| Writer                 | `v84-<iter>.<role>.rule.<n>`                       |
| Reviewer               | `v84-<iter>.<role>.<reviewer_tag>.rule.<n>`        |
| Lead-authored          | `v84-<iter>.<role>.lead.rule.<n>`                  |
| Architect              | `v84-<iter>.architect.rule.<n>`                    |

Greppable: `[v84-1.frontend` finds everything frontend raised in
iteration 1; `[v84-1.architect` finds architect-imposed.

## Scope

Role-scoped vs global is a function of where the record lives:

- `iterations/<n>/<role>.rules.yaml` — role-scoped to `<role>`.
  Lead-managed.
- `iterations/<n>/global.rules.yaml` — global. Architect-managed,
  lead-validated.
- `<project>/v84/<role>.rules.yaml` — promoted role-scoped.
- `<project>/v84/global.rules.yaml` — promoted global.

## What "in scope" means

`core.context.rules_block(role)` returns active rules in scope for
`role`. It walks four sources in order:

1. `<project>/v84/global.rules.yaml`
2. `<project>/v84/<role>.rules.yaml`
3. `iterations/<n>/global.rules.yaml` filtered to `status: accepted`
4. `iterations/<n>/<role>.rules.yaml` filtered to `status: accepted`

`pending_rules_block(role)` and `rejected_rules_block(role)` are
separate helpers — they only read iteration files. The lead reads
both `rules_block` (active) and `pending_rules_block` (proposals to
verdict); the writer normally reads only `rules_block` (binding
rules already in place).

## "A rule is by definition approved"

The naming reflects the lifecycle:

- `rules_block(role)` returns approved rules only.
- Pending proposals live behind `pending_rules_block`.
- Rejected proposals live behind `rejected_rules_block`.

Root files (`<project>/v84/*.rules.yaml`) carry no `status` field —
records there are definitionally approved (by user_review at
promotion time). Iteration files carry `status` because they hold
proposals at every stage of the lifecycle.

## Architect-proposed globals

The architect can propose globals (cross-cutting rules from
patterns it sees across roles). Path:

1. Architect emits `proposed_rules: [...]`.
2. Harness writes to `iterations/<n>/global.rules.yaml` with
   `status: pending`.
3. The `architect_validate` stage runs cross-lead validation:
   fan-out one parallel call per active role-lead, each lead
   votes `accept | reject` per pending global from its role's
   perspective (alongside per-role architect-correction voting in
   the same call). **Single-veto rule** — any reject sets the
   global to `status: rejected` with `rejected_by: <role>.lead`
   and the lead's `rejection_reason` recorded. Otherwise →
   `status: accepted`.
4. Next round's architect sees rejected globals (with reasons)
   in its context via `rejected_rules_block`, so it doesn't
   re-propose blindly — it can either drop the idea or reword to
   address the rejection reason.
5. user_review at iteration close runs the `classify-rules` LLM
   call to pre-bucket every accepted rule (promote vs
   iteration-only), then shows them via `review_list`. Ticked
   entries promote to the project root.

## Lead-authored role-scoped raises

The lead may also raise its OWN role-scoped rules in the raise
half of `lead_round` (instruction: `lead.md`). These follow a
different path: lead is the role's authority, so the raises
**settle directly accepted** in-iteration — no further verdicting
needed inside the cycle. user_review remains the final gate at
iteration close (user can untick / edit / decline like any other
accepted rule).

The on-disk record carries the same `{proposal, alternatives,
text}` shape as reviewer-raised+lead-accepted records (so
user_review sees full context — preferred form + considered
alternatives). Id format: `v84-N.<role>.lead.rule.<m>`.

## When does the cycle stop?

When **no corrections are pending across any role** at the end of
the `architect_validate` stage. That means:

- Lead rejected or applied every reviewer correction.
- Lead also voted on every architect cross-role correction (and
  accepted ones moved to the punch list, rejected ones moved to
  the rejected file).
- Architect added no cross-role catches the leads then accepted.
- Architect's pending global rule proposals sit in their store but
  don't trigger another round on their own.

At that point `architect_validate` hands off to user_review, the
user gets to promote / edit / decline the iteration's accumulated
rules, and the iteration closes.

See [iteration-loop.md](iteration-loop.md) for the round mechanics
and how `architect_validate`'s check drives the state machine.
