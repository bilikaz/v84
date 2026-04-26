# Conventions and Decisions

> Two stores for two kinds of rule. Both flow through the same
> lifecycle.

## The distinction

- **Conventions** are durable rules that apply across this and
  future iterations ("all DB columns use snake_case mapping",
  "every CSS animation respects `prefers-reduced-motion`").
- **Decisions** are one-shot rulings for this iteration only
  ("session timeout stays at 30 min for the add-2fa scope").

Same data shape, same lifecycle, different intent. Stored in
parallel files (`*.conventions.yaml` + `*.decisions.yaml`) so each
flow is greppable independently.

## Lifecycle

```
1. Writer or reviewer raises a proposal in `needs_convention` /
   `needs_decision`.
        ↓
2. Harness assigns id, writes to <role>.conventions.yaml as
   {status: pending, proposal, alternatives}.
        ↓
3. Lead verdicts each pending entry: accept → status: accepted +
   `rule` (the lead's final wording); reject → status: rejected.
   Rejected entries stay in the file as audit.
        ↓
3b. Lead may also raise its OWN role-scoped rules via
    `needs_convention` / `needs_decision`. Same `{proposal,
    alternatives}` shape as writer/reviewer raises so user_review
    sees the full context (lead's preferred form + considered
    alternatives) at promotion time. In-iteration these auto-promote
    to status: accepted (lead is the role's authority — no further
    verdicting needed inside the cycle); the harness sets `rule`
    to the proposal text. Id format:
    `v84-N.<role>.lead.{conv,dec}.<m>`.
        ↓
4. Architect emits its own globals into iterations/<n>/global.*
   with status: pending. The validate stage that runs next fans
   out a per-lead call to vote on every pending global from each
   role's perspective. Single-veto rule: any reject → status:
   rejected, with `rejected_by: <role>.lead` and a `rejection_reason`
   recorded; otherwise → status: accepted. Rejected globals stay
   in the file (carrying their reason) so the next round's
   architect sees what was shot down and why.
        ↓
5. user_review (Phase B) prompts the user to confirm everything
   accepted across the iteration. Accepted records get promoted:
   - role-scoped → <project>/v84/<role>.conventions.yaml
   - global    → <project>/v84/global.conventions.yaml
   Edits trigger an iteration restart.
```

## Record shape

Pending / accepted / rejected entries (in iteration files):

```yaml
- id: v84-1.frontend.conv.1            ← harness-assigned
  proposal: |                          ← agent's preferred form
    Wrap CSS animations in @media (prefers-reduced-motion: no-preference).
  alternatives:
    - |
      Single :root toggle for all motion.
    - |
      Always-on with UI pause control.
  status: pending | accepted | rejected
  rule: |                              ← only when status: accepted
    <lead's final wording>             ← canonical text used by other agents
```

Promoted entries (in `<project>/v84/{role,global}.{conventions,decisions}.yaml`)
drop the proposal-time fields and keep just the canonical form:

```yaml
- id: v84-1.frontend.conv.1
  rule: |
    <the rule, as the lead/user enacted it>
```

## Id format

Source determines prefix:

| Source                 | Id format                                                |
|------------------------|----------------------------------------------------------|
| Writer                 | `v84-<iter>.<role>.{conv,dec}.<n>`                       |
| Reviewer               | `v84-<iter>.<role>.<reviewer_tag>.{conv,dec}.<n>`        |
| Architect              | `v84-<iter>.architect.{conv,dec}.<n>`                    |

Greppable: `[v84-1.frontend` finds everything frontend raised in
iteration 1; `[v84-1.architect` finds architect-imposed.

## Scope

Role-scoped vs global is a function of where the record lives:

- `iterations/<n>/<role>.conventions.yaml` — role-scoped to
  `<role>`. Lead-managed.
- `iterations/<n>/global.conventions.yaml` — global. Architect-
  managed.
- `<project>/v84/<role>.conventions.yaml` — promoted role-scoped
  (Phase B).
- `<project>/v84/global.conventions.yaml` — promoted global
  (Phase B).

## What "in scope" means

`core.context.conventions_block(role)` returns active conventions
in scope for `role`. It walks four sources in order:

1. `<project>/v84/global.conventions.yaml`
2. `<project>/v84/<role>.conventions.yaml`
3. `iterations/<n>/global.conventions.yaml` filtered to
   `status: accepted`
4. `iterations/<n>/<role>.conventions.yaml` filtered to
   `status: accepted`

Same trio for decisions.

`pending_conventions_block(role)` and
`rejected_conventions_block(role)` are separate helpers — they
only read iteration files. The lead reads both `conventions_block`
(active) and `pending_conventions_block` (proposals to verdict);
the writer normally reads only `conventions_block` (binding rules
already in place).

## "A convention is by definition approved"

The naming reflects the lifecycle:

- `conventions_block(role)` returns approved conventions only.
- Pending proposals live behind `pending_conventions_block`.
- Rejected proposals live behind `rejected_conventions_block`.

Root files (`<project>/v84/*.yaml`) carry no `status` field —
records there are definitionally approved (by user_review at
promotion time). Iteration files carry `status` because they hold
proposals at every stage of the lifecycle.

## Architect-proposed globals

The architect can propose globals (cross-cutting rules from
patterns it sees across roles). Path:

1. Architect emits `proposed_conventions: [...]` /
   `proposed_decisions: [...]`.
2. Harness writes to `iterations/<n>/global.{conventions,decisions}.yaml`
   with `status: pending`.
3. The `validate` stage runs cross-lead validation: fan-out one
   parallel call per active role-lead, each lead votes
   `accept | reject` per pending global from its role's
   perspective. **Single-veto rule** — any reject sets the global
   to `status: rejected` with `rejected_by: <role>.lead` and the
   lead's `rejection_reason` recorded. Otherwise → `status:
   accepted`.
4. Next round's architect sees rejected globals (with reasons)
   in its context via `rejected_conventions_block` /
   `rejected_decisions_block`, so it doesn't re-propose blindly
   — it can either drop the idea or reword to address the
   rejection reason.
5. user_review at iteration close promotes accepted globals to
   the project root via the same field_editor flow as role-scoped
   accepted rules.

## Lead-authored role-scoped raises

The lead may also raise its OWN role-scoped conv/dec via
`needs_convention` / `needs_decision`. These follow a different
path: lead is the role's authority, so the raises **settle
directly accepted** in-iteration — no further verdicting needed
inside the cycle. user_review remains the final gate at iteration
close (user can edit / decline like any other accepted rule).

The on-disk record carries the same `{proposal, alternatives,
rule}` shape as reviewer-raised+lead-accepted records (so user_review
sees full context — preferred form + considered alternatives).
Id format: `v84-N.<role>.lead.{conv,dec}.<m>`.

## When does the cycle stop?

When **no corrections are pending across any role** at the end of
the validate stage. That means:

- Lead rejected or applied every reviewer suggestion.
- Architect added no cross-role catches.
- Architect's pending global proposals sit in their store but
  don't trigger another round on their own.

At that point validate hands off to user_review, the user gets to
promote / edit / reject the iteration's accumulated rules, and the
iteration closes.

See [iteration-loop.md](iteration-loop.md) for the round mechanics
and how validate's check drives the state machine.
