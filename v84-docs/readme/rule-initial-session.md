# Rule Initial Session (Pre-Pass)

> Front-load the iteration's binding rules before any actions are
> drafted. Five stages between `plan` and `cycle` settle a fresh
> convention pack so every writer reads the user-finalised rule
> set on first draft.

## Why a pre-pass

In v84's cycle, rules emerge organically from writer drafts and
review corrections — by the end of round 1 the team has often
discovered the conventions every writer should have followed on
first draft. The pre-pass surfaces those conventions *upfront*
so the cycle doesn't waste a round drifting into and correcting
them.

For iteration 1 (no inherited rules) the pre-pass is mandatory
and produces 5–7 role-internal rules per role plus 8–12
cross-role globals. For later iterations it still runs, but
typically yields smaller sets — most conventions already live in
the project root from prior iterations.

## The five pre-pass stages

```
plan
  → rules_lead              fan-out per active role
  → rules_architect         single architect call (cross-role)
  → rules_validate          fan-out per lead (single-veto on globals)
  → rules_consolidate       single architect call (dedup + drift)
  → user_rules_review       user gate (review_list)
  → cycle (draft starts)
```

### rules_lead (per role, fan-out)

Each active role's lead reads its plan slice, role definition,
stack slice, repo layout, role history, and any rules already
promoted at the project root. It proposes **5–7 starting rules**
covering:

1. File and folder conventions
2. Naming patterns
3. Stack-driven best practices
4. Structural patterns (layers / phases / tiers)
5. Role-internal contracts

Each proposal binds to one of: the plan, role definition, stack
slice, repo layout, or role history. Lead is the role's
authority — proposals land in
`iterations/<n>/<role>.rules.yaml` as `status: accepted` with
`text` set to the proposal. They later face the architect's
coherence pass in `rules_consolidate`.

### rules_architect (cross-role, single call)

The architect reads the plan, full stack, full repo layout,
every active role's lead pack from `rules_lead`, and any
inherited root globals. It proposes **8–12 cross-role globals**
covering:

1. Inter-role contracts (data shapes, ID schemes, error formats)
2. Shared file ownership (`.env.example`, root configs, compose)
3. Environment variable conventions
4. Cross-role dependency conventions (package manager, pinning)
5. Cross-role artifact paths

Globals may carry an optional `promotes_from: [<lead_rule_id>…]`
list — when the architect generalises a role-internal rule to
cross-role scope, the cited lead rules are retired
(`status: superseded`, `superseded_by: <global_id>`) once the
global is accepted.

Globals land in `iterations/<n>/global.rules.yaml` as
`status: pending`.

### rules_validate (per lead, fan-out)

Each active role's lead votes `accept` or `reject` on every
pending global from its perspective. Reject only with a concrete
cross-role break:

- Drift against a root rule (project global or this role's
  promoted role rule). Cite the conflicting root rule id.
- Stack / layout reality cannot honor the global. Name the
  contract gap.
- A `promotes_from` cites this role's lead rule but the global's
  wording doesn't fully cover that rule's scope. Name the gap.

Single-veto: any reject → `status: rejected` with `rejected_by:
<role>.lead` and `rejection_reason`. Otherwise →
`status: accepted` with `text` set to the proposal, and any
`promotes_from` cited rules retired.

### rules_consolidate (single architect call)

After globals settle, the architect votes `accept` or `reject`
on every surviving lead rule from `rules_lead`. Reject when:

- Conflicts with a settled global from this iteration.
- Conflicts with a root-promoted rule.
- Subsumed by a settled global (the global's wording covers the
  lead rule's full scope).
- Same-scope duplicate of another role's lead rule.

Accept = lead rule keeps `status: accepted`. Reject = flips to
`status: rejected` with `rejected_by: architect` and
`rejection_reason`.

### user_rules_review (user gate)

Mirrors the iter-close `user_review`. Same `review_list`
painter, same `classify-rules` LLM pre-bucket (promote vs
iteration_only), same per-rule edit / pick alternatives. Two
terminal actions through `confirm_modal`:

- **`[c] continue`** — promote ticked rules to project root
  (`<project>/v84/{<role>,global}.rules.yaml`), initialise the
  cycle pipeline (round 1, every active role parked at draft),
  advance to `cycle`.
- **`[r] regenerate`** — promote ticked rules the same way, clear
  the iteration's pre-pass artifacts (per-role rules +
  iteration-level globals + classifications cache), reset
  `next_step` to `rules_lead`. The next pre-pass round reads the
  freshly promoted root rules as binding context.

## File lifecycle

```
iterations/<n>/
├── <role>.rules.yaml           ← rules_lead writes (status: accepted)
│                                  rules_consolidate may flip to
│                                  rejected; promotes_from retirements
│                                  set status: superseded
├── global.rules.yaml            ← rules_architect writes (pending);
│                                  rules_validate flips to accepted /
│                                  rejected
├── rule_classifications.yaml    ← user_rules_review pre-bucket cache
└── status.yaml                  ← next_step progresses through:
                                    plan → rules_lead → rules_architect
                                    → rules_validate → rules_consolidate
                                    → user_rules_review → cycle
```

After `user_rules_review` continue, ticked rules end up at
`<project>/v84/{<role>,global}.rules.yaml` exactly like
iter-close `user_review` does. Pre-pass-promoted rules are
binding from round 1's draft.

## Promotion mechanic

When `rules_architect` emits a global with
`promotes_from: ["v84-N.<role>.lead.rule.M"]`, it asserts that
the global's wording fully subsumes the cited lead rule's
scope. If `rules_validate` accepts the global, the harness:

1. Sets the global's `status: accepted` with `text`.
2. Walks each cited lead rule, flips its status to `superseded`,
   adds `superseded_by: <global_id>`.

The lead rule stays on disk for audit. `rules_consolidate` does
not see superseded records (they're filtered by status). The
user_rules_review screen shows only `accepted` records, so
superseded rules don't appear for the user.

If `rules_validate` rejects the global, the cited lead rules
stay accepted. `rules_consolidate` then evaluates them on their
own merits.

## When pre-pass fires

- **Iteration 1**: mandatory. The rule pool is empty; pre-pass
  produces the project's foundational conventions.
- **Iteration N ≥ 2**: runs by default. Lead packs and architect
  globals propose only what's genuinely additive given the
  inherited root rule set. Empty packs are legal; the user gate
  asks whether to add anything before drafting.

## Resume semantics

Each pre-pass stage uses the standard
`next_step != stage_name` done check from `iter_status`.
Killing the run mid-pre-pass and re-running picks up at the
pending stage. The regenerate path resets to `rules_lead` and
re-runs the full pre-pass against the just-promoted root rule
set.

## Counts and concurrency

| Profile             | Roles | rules_lead | rules_validate | Pre-pass calls (max) |
|---------------------|-------|------------|----------------|----------------------|
| Backend API service |   3   |     3      |       3        |        8             |
| Fullstack web SaaS  |   5   |     5      |       5        |       12             |
| Fullstack + mobile  |   6   |     6      |       6        |       14             |

Pre-pass total = `rules_lead` (per role, parallel) + 1
(rules_architect) + `rules_validate` (per role, parallel) + 1
(rules_consolidate) = `2N + 2`. Concurrency caps from
`profile.yaml`'s `llm.<tier>.max_concurrency` apply.
