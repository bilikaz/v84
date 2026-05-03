# Cycle Flow

> What happens at each stage inside one iteration, file by file.

This is the per-stage walkthrough. Round mechanics and the
`status.yaml` state machine are in
[iteration-loop.md](iteration-loop.md). Layer responsibilities are
in [four-layer-split.md](four-layer-split.md).

## Stage 1: plan

**When**: a top-level task in `core.yaml` doesn't yet have
sub-tasks under it.

**Inputs**:
- The parent task (id + prose)
- Active roles + stack (context only — the agent doesn't decide
  which roles fire)
- Past iteration plans (`iterations/*/plan.yaml`)

**LLM call**: single. Two output shapes:
- `tasks: [...]` — recursive sub-task tree.
- `questions: [...]` — clarifying questions with suggested answers
  when the parent task is structurally ambiguous.

If questions, the user answers via a `field_editor` UI; the agent
re-fires with the Q&A as additional context until it produces tasks.

**On accept**:
- Sub-tasks added under the parent in `core.yaml` (recursive).
- `core.yaml`'s `current_iteration` set to the parent task id.
- `iterations/<n>/plan.yaml` written with the iteration number,
  parent id, and any Q&A history.
- `iterations/<n>/status.yaml` written: `{round: 1, next_step: draft}`.

## Stages 1.5: pre-pass (rule initial session)

After `plan` settles the iteration's sub-tasks, five stages run
before drafting begins. They front-load the binding rules so the
first draft reads a user-finalised rule set instead of
discovering conventions through correction churn. Full detail in
[rule-initial-session.md](rule-initial-session.md).

```
plan
  → rules_lead              fan-out per role; 5–7 role-internal
                            rule proposals each, status: accepted
                            (lead is the role's authority)
  → rules_architect         single architect call; 8–12 cross-role
                            global proposals, status: pending,
                            with optional promotes_from when
                            generalising a lead-internal rule
  → rules_validate          fan-out per lead; single-veto vote on
                            architect's pending globals; drift
                            checks against root rules; promotes_from
                            cited rules retired (status: superseded)
                            on accept
  → rules_consolidate       single architect call; vote accept/reject
                            on every surviving lead rule against the
                            now-settled globals (subsumed / drifting /
                            duplicate → reject)
  → user_rules_review       review_list gate; ticked rules promote to
                            <project>/v84/{<role>,global}.rules.yaml;
                            continue → init cycle pipeline; regenerate
                            → reset to rules_lead
```

After `user_rules_review` continue, `next_step` is `cycle` and
the per-role pipeline starts at draft. After regenerate,
`next_step` is `rules_lead` and the pre-pass re-runs against the
newly promoted root rules.

## Stage 2: draft

**When**: round 1 only. `status.yaml.next_step == "draft"`.

**Fan-out**: one parallel writer per active role via the multi tier.

**Per-role inputs**:
- Iteration plan (`plan_block` from core.yaml)
- Role definition (`roles_block(role)`) — reads
  `<project>/v84/structure/roles/<role>.yaml`
- Role's stack slice (`stack_block(role)`)
- Rules in scope (`rules_block(role)`)
- Past iteration drafts for this role (cascade memory)

**Per-role output**: `iterations/<n>/<role>.yaml` —

```yaml
actions:
  - id: v84-1.1.frontend.1            ← agent-emitted, format
                                        <task_id>.<role_tag>.<n>
    action: |
      <one prose line of file-level work>
    files:
      - <path>
    depends:
      - <other action id>             ← optional
```

The agent may also emit a `rules` array with rule proposals. The
harness:
- Strips them out of the on-disk draft.
- Writes them to `<role>.rules.yaml` with harness-assigned ids
  (`v84-<n>.<role>.rule.<m>`) and `status: pending`.

**Status advance**: `next_step: review`.

## Stage 3: review

**When**: `next_step == "review"`.

**Fan-out**: one parallel call per (role, reviewer_tag). With 2
roles × 4 reviewers = 8 parallel calls. Cap from
`llm.multi.max_concurrency`.

**Round-2+ scoping**: only roles named in `status.yaml`'s
`active_roles` are reviewed. `architect_validate` narrows that
list at end of round to roles with pending corrections — others'
drafts didn't change, so re-reviewing them would just produce
identical output.

**Per-reviewer inputs**:
- Reviewer definition (its `challenge` question, responsibilities,
  catches) from `structure/roles/<role>.yaml`
- Iteration plan
- Role definition + stack + role's repo layout
- Rules in scope
- The role's full writer draft
- The role's accumulated implementation history
  (`documentation/<role>.yaml`)
- **Round 2+ only**: `<role>.corrections-applied.yaml` (what
  patch honored — verify, don't re-raise) and
  `<role>.corrections-rejected.yaml` (what the lead / architect
  / architect_validate already dismissed — don't re-raise).

**Per-reviewer output**: corrections (verdict, action_id /
task_id, correction prose) and optional rule proposals. The
harness merges every reviewer's corrections into one per-role
file (`iterations/<n>/<role>.corrections-pending.yaml`) — there
are no per-lens review files anymore. Each reviewer-emitted entry
gets a harness-assigned id of the form
`v84-<iter>.<role>.<reviewer_tag>.c.<n>` so the source is
greppable downstream.

```yaml
# <role>.corrections-pending.yaml after the review fan-out
- id: v84-1.frontend.pages.c.1
  verdict: fix | missing | remove
  action_id: v84-1.2.frontend.1     # for fix / remove
  task_id: v84-1.3                  # for missing (under-covered task)
  correction: |
    <one short line>
```

Rule proposals from any reviewer get appended to the same
role-scoped pending store the writer seeded
(`<role>.rules.yaml`), each with id
`v84-<iter>.<role>.<reviewer_tag>.rule.<n>`.

**Status advance**: `next_step: lead_round`.

## Stage 4: lead_round

**When**: `next_step == "lead_round"`.

**Fan-out**: TWO LLM calls per active role, fired in parallel —
the verdict call (uses `review_validate.md` + schema) and the
raise call (uses `lead.md` + schema). Both calls see the same
pre-vote disk state. With N active roles that's 2N parallel
calls; the verdict call is skipped for roles that have nothing
pending.

**Verdict call (`review_validate`)**:
- **Inputs**: iteration plan, role + stack + layout, the role's
  writer draft, every pending reviewer correction for this role
  (one merged list with reviewer-tagged ids), every pending rule
  proposal raised this iteration for the role, rules already in
  scope.
- **Output**: `corrections` (`{id, verdict: accept|reject,
  reason?}`) and `rules` (`{id, verdict, text? (on accept)}`).

**Raise call (`lead.md`)**:
- **Inputs**: same context as verdict call, plus the
  post-verdict view (the verdict call's accepted set, the
  rejected entries this iteration, rejected globals from the
  architect with reasons). Lead can pick up what the reviewers
  all missed; silence is fine (most lead raises produce nothing).
- **Output**: `corrections` (lead's own additions in correction
  shape — `{verdict, action_id|task_id, correction}`) and
  `rules` (lead-authored `{proposal, alternatives}` — these
  auto-accept since the lead is the role's authority).

**Two-phase write** (sequential, after every LLM call returns):

- **Phase A — apply verdicts** (lead-blessed pending lifecycle):
  accepted reviewer corrections **stay in
  `<role>.corrections-pending.yaml`** (lead-blessed, awaiting
  architect's `lead_validate`); rejected ones move to
  `<role>.corrections-rejected.yaml` with `rejected_by:
  <role>.lead`. For pending rules: accepts keep `status: pending`
  with the lead's preferred wording recorded in `text`; rejects
  flip to `status: rejected`. No synthetic apply-correction is
  generated here — the synth fires later when the architect's
  `lead_validate` transitions a rule to `accepted`.
- **Phase B — apply raises**: lead corrections append to
  `<role>.corrections-pending.yaml` with ids
  `v84-<n>.<role>.lead.c.<m>` (lead-blessed pending); lead rules
  append to `<role>.rules.yaml` as `status: pending` with ids
  `v84-<n>.<role>.lead.rule.<m>`. Both face the architect's
  `lead_validate` for the final accepted/rejected decision.

After lead_round, `<role>.corrections-pending.yaml` holds every
lead-blessed correction in this iteration (reviewer-source the
lead accepted + lead's own raises). `<role>.rules.yaml` holds
pending rules awaiting architect verdict + already-accepted
rules from earlier rounds.

**Status advance**: `next_step: architect`.

## Stage 5: architect

**When**: `next_step == "architect"`.

**Two LLM calls in parallel via `call_many`**: a raise call
(`architect.md`) and a verdict call (`lead_validate.md`). The
verdict call is **gated** — fires only when there is at least
one lead-blessed pending correction (id NOT containing
`architect.c.`) or any role rule in `pending` / `accepted`
status across active roles. When there is nothing to judge,
the architect runs raise-only.

Both calls see the same pre-vote disk state. Multi tier when
configured, else single.

### Raise call (`architect.md`)

Cross-role corrections + global rule proposals. Output:

```yaml
corrections:                    ← cross-role corrections
                                  ({verdict, action_id|task_id,
                                  correction, plus `for_role` for
                                  missing-type})
rules:                          ← {proposal, alternatives} global
                                  proposals
```

### Verdict call (`lead_validate.md`)

Vote `accept` or `reject` on every lead-blessed correction and
every role-scoped rule in scope (lead-blessed pending + still-
accepted from earlier rounds). Output:

```yaml
corrections:                    ← {id, verdict, reason?} per
                                  lead-blessed correction
rules:                          ← {id, verdict, reason?} per
                                  pending or accepted role rule
```

### Two-phase write

After both calls return, harness applies them sequentially.

**Phase A — verdicts**:

- Lead-blessed pending corrections (in
  `<role>.corrections-pending.yaml`, id NOT
  `architect.c.<m>`): accept → move to `corrections.yaml`;
  reject → move to `corrections-rejected.yaml` with
  `rejected_by: architect`.
- Reviewer corrections the lead accepted (already in
  `corrections.yaml`): accept → no-op; reject → move to
  `corrections-rejected.yaml`.
- Pending rules: accept → flip to `accepted` + synthesize
  `<rule_id>.apply` correction in `corrections.yaml`; reject →
  flip to `rejected`.
- Accepted rules: accept → no-op; reject → flip to `rejected`
  AND retract the rule's synthetic apply-correction.

**Phase B — raises**:

- Each cross-role correction → appended to the relevant role's
  `<role>.corrections-pending.yaml` with id
  `v84-<n>.architect.c.<m>` (these will be voted on next by
  `architect_validate`).
- `rules` (globals) → `iterations/<n>/global.rules.yaml` with
  harness-assigned ids (`v84-<n>.architect.rule.<m>`) and
  `status: pending`.

`corrections.yaml` is **architect-blessed only** after Phase A
completes — a clean punch list for patch.

**Status advance**: `next_step: architect_validate`.

## Stage 6: architect_validate

**When**: `next_step == "architect_validate"`.

Two jobs in order; both share a single fan-out.

**Job 1 — Cross-lead validation of architect's outputs.**
Skipped when nothing is pending across globals OR per-role
architect corrections. Otherwise: fan out one parallel call per
active role-lead via the multi tier (instruction:
`instructions/iteration/architect_validate.md`). Each lead votes on
TWO sets of items in the same call:

- **Pending globals** (every lead votes; single-veto). Any reject
  → status becomes `rejected` with `rejected_by: <role>.lead`
  and the lead's `rejection_reason` recorded. Otherwise →
  `status: accepted`. Next round's architect sees rejected
  entries with their reasons so it can reword or drop — without
  re-proposing the same idea blindly.
- **Pending architect corrections targeting this role** (only this
  role's lead votes; verdict is final). Accepted entries move
  from `<role>.corrections-pending.yaml` to
  `<role>.corrections.yaml` (joining the patch punch list);
  rejected move to `<role>.corrections-rejected.yaml` tagged
  `rejected_by: <role>.lead`. The pending file is cleared either
  way.

Per-lead inputs: role + stack, rules in scope (role + globals),
the pending global list, the role's pending architect
corrections. Output schema lives in
`architect_validate.schema.json`: two arrays of
`{id, verdict, reason (when reject)}`.

**Job 2 — Corrections-presence check.** No LLM call.
- Count entries in every `<role>.corrections.yaml` across active
  roles.
- If sum > 0: `iter_status.next_round_to("patch")` → round++,
  `next_step: patch`. Stamps `active_roles` to just the roles
  with pending corrections so review/lead_round/patch skip the
  others next round.
- If sum == 0: `iter_status.advance_to("user_review")`.

## Stage 7: patch (round 2+)

**When**: `next_step == "patch"` (set by architect_validate when
corrections remain).

**Fan-out**: one parallel call per role in `status.yaml`'s
`active_roles` (the roles with pending corrections at the end of
the previous round).

**Per-role inputs** — same as draft, plus:
- The existing draft (`<role>.yaml`)
- Corrections to apply (`<role>.corrections.yaml`)

**Per-role output**: a patched actions list. Surviving actions
keep their ids; fixed actions get rewritten in place; missing
corrections become new actions following per-task numbering;
removed corrections drop the named action.

**Persistence**:
- New `<role>.yaml` overwrites the prior draft (versioned via
  `core.versioning` when `project.logging: true`).
- Applied corrections move to `<role>.corrections-applied.yaml`
  (audit; next round's reviewers can verify what was honored).
- `<role>.corrections.yaml` cleared.
- Fresh rule proposals raised by patch use the same prefix as
  round-1 (`v84-<n>.<role>.rule`) and continue the numbering past
  the highest existing index so ids don't collide.

**Status advance**: `next_step: review`. The cycle continues from
review onward — but only for the roles in `active_roles`.

## Stage 8: user_review

**When**: `next_step == "user_review"` (set by
architect_validate when no corrections remain).

**Job**:
1. Read every accepted rule from the iteration — per-role +
   architect-proposed globals.
2. Run the `classify-rules` LLM call (single call) to pre-bucket
   each rule into `promote` (binds future iterations) or
   `iteration_only` (one-shot scope). Result is cached at
   `iterations/<n>/rule_classifications.yaml`; reused on
   re-entry when the accepted-id set hasn't changed. On
   classifier failure → deterministic defaults (everything →
   promote) so the UI never shows a half-classified list.
3. Show the rules via the `review_list` painter
   (`harness/ui/review_list.py`) — sectioned, ticked-by-default
   for `promote`, drillable into alternatives, inline-editable.
   Bottom action bar offers two terminal commits and one mutate:
   - `[c] promote & continue`
   - `[r] promote & regenerate`
   - `[a] add rule`
4. Each commit fires through `confirm_modal` for slip
   protection. The user picks one of the two terminal actions:
   - **continue** → promote every ticked entry to project-root
     files — `<project>/v84/<role>.rules.yaml` /
     `<project>/v84/global.rules.yaml` — using the user's
     finalised wording. Write `iterations/<n>/tasks.md` (the
     implementer handoff). Advance `next_step: finish`.
   - **regenerate** → promote ticked entries the same way, then
     clear cycle artefacts (drafts, corrections, reviews) and
     reset to `{round: 1, next_step: draft}`. The new draft pass
     reads the updated rule set from project root.

The handoff document (`tasks.md`) bundles plan + roles + active
rules + repo layout + tagging convention + per-role action list —
everything an external implementer (Claude Code, Cursor, human)
needs to translate the actions into actual code on disk.

## Stage 9: finish

**When**: `next_step == "finish"` (set by user_review's pure-accept
path).

**No LLM call.** Pure verification + close.

**Job**:
1. Read every action across active roles
   (`iterations/<n>/<role>.yaml`).
2. For each action's `files:` entry, check the file exists on
   disk AND its body contains a tag from any owning action
   (handles the aggregator pattern — a file shared by multiple
   actions only needs ONE related `[v84-N.M.role.K]` tag).
3. If gaps exist → write `iterations/<n>/fix.md` listing each
   gap by action (kind: `missing` or `untagged`, with the action
   prose for context). Status stays `next_step: finish` so the
   next Start re-checks.
4. If pristine → drop any stale `fix.md`, append the iteration's
   actions to `<project>/v84/documentation/<role>.yaml` per role
   (grouped by sub-task, parent task prose preserved), then close
   the iteration: move parent_id into `completed_iterations`,
   clear `current_iteration`, advance `next_step: done`.

The user runs the external implementer between user_review's
handoff and finish's verification. Re-running v84 after the
implementer's pass triggers finish's check; gaps surface as
`fix.md` for another implementer pass; clean state closes the
iteration.
