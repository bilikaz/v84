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

## Stage 2: draft

**When**: round 1 only. `status.yaml.next_step == "draft"`.

**Fan-out**: one parallel writer per active role via the multi tier.

**Per-role inputs**:
- Iteration plan (`plan_block` from core.yaml)
- Role definition (`roles_block(role)`) — reads
  `<project>/v84/structure/roles/<role>.yaml`
- Role's stack slice (`stack_block(role)`)
- Conventions / decisions in scope (`conventions_block(role)` /
  `decisions_block(role)`)
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

The agent may also raise `needs_convention` / `needs_decision`
proposals. The harness:
- Strips them out of the on-disk draft.
- Writes them to `<role>.conventions.yaml` /
  `<role>.decisions.yaml` with harness-assigned ids
  (`v84-<n>.<role>.conv.<m>` / `.dec.<m>`) and `status: pending`.

**Status advance**: `next_step: review`.

## Stage 3: review

**When**: `next_step == "review"`.

**Fan-out**: one parallel call per (role, reviewer_tag). With 2
roles × 4 reviewers = 8 parallel calls. Cap from
`llm.multi.max_concurrency`.

**Per-reviewer inputs**:
- Reviewer definition (its `challenge` question, responsibilities,
  catches) from `structure/roles/<role>.yaml`
- Iteration plan
- Role definition + stack
- Conventions / decisions in scope
- The role's full writer draft
- **Round 2+ only**: `<role>.corrections-applied.yaml` (what
  patch honored — verify, don't re-raise) and
  `<role>.corrections-rejected.yaml` (what the lead/architect
  already dismissed — don't re-raise). Filtered to this
  reviewer's own past suggestions plus role-wide lead/architect
  entries; other reviewers' lens-specific items are excluded so
  four reviewers don't all flag the same other-lens concern.

**Per-reviewer output**:
`iterations/<n>/reviews/<role>.<reviewer_tag>.yaml` —

```yaml
suggestions:
  - id: v84-1.frontend.pages.s.1      ← harness-assigned
    verdict: fix | missing | remove
    action_id: v84-1.2.frontend.1     ← for fix/remove
    task_id: v84-1.3                  ← for missing (under-covered task)
    suggestion: |
      <one short line>
```

`needs_convention` / `needs_decision` from the reviewer get
appended to the same role-scoped pending stores the writer seeded.

**Status advance**: `next_step: lead`.

## Stage 4: lead

**When**: `next_step == "lead"`.

**Fan-out**: one parallel call per active role.

**Per-lead inputs**:
- Iteration plan, role + stack
- The role's writer draft
- Every reviewer's suggestions for this role merged into one list
  (each carrying its harness-assigned id and source `reviewer_tag`)
- **Round 2+ only**: full `<role>.corrections-applied.yaml` and
  full `<role>.corrections-rejected.yaml` (no per-reviewer filter
  — the lead owns the role's whole punch list)
- Every pending convention/decision proposal raised this iteration
  for the role
- Conventions/decisions already in scope

**Lead's response** carries six streams (none required to be
non-empty):

```yaml
suggestion_verdicts:    ← {id, verdict: accept|reject}
corrections:            ← lead's own additions in suggestion shape
                          ({verdict, action_id|task_id, correction})
convention_verdicts:    ← {id, verdict, rule (when accepting)}
decision_verdicts:      ← same shape
needs_convention:       ← lead-authored {rule} — settles instantly
                          accepted (lead is the role's authority)
needs_decision:         ← same shape, one-shot rulings
```

**Harness splits** the response across files:

- `<role>.corrections.yaml` ← every accepted suggestion (echoed
  with id + verdict + action_id|task_id + correction text) plus
  the lead's own corrections (with harness-assigned ids
  `v84-<n>.<role>.lead.c.<m>`).
- `<role>.corrections-rejected.yaml` ← rejected suggestions, full
  text echoed for audit, tagged `rejected_by: lead`.
- `<role>.conventions.yaml` ← `apply_verdicts` updates each pending
  entry's `status` to `accepted` (with the lead's `rule` text) or
  `rejected`.
- `<role>.decisions.yaml` ← same.

**Status advance**: `next_step: architect`.

## Stage 5: architect

**When**: `next_step == "architect"`.

**Single LLM call** (no fan-out).

**Architect's inputs**:
- Iteration plan, full stack, active roles list
- Per-role bundle for every active role:
  - Writer's draft
  - Lead's corrections (`<role>.corrections.yaml`)
  - Lead's rejected corrections (`<role>.corrections-rejected.yaml`)
  - Accepted role conv/dec (filtered status=accepted)
- Active global conv/dec from project root

**Architect's response** has four streams:

```yaml
corrections:                    ← cross-role corrections
                                  same shape as lead's, plus
                                  `for_role` for missing-type
rejected_corrections:           ← list of {id} from any lead's
                                  corrections to override
proposed_conventions:           ← {proposal, alternatives} global
proposed_decisions:             ← same shape
```

**Harness routes**:

- Each `corrections` entry → appended to the relevant role's
  `<role>.corrections.yaml` with id `v84-<n>.architect.c.<m>`.
  Role inferred from `action_id` prefix (fix/remove) or from
  `for_role` (missing).
- Each `rejected_corrections` id → moved from its role's
  `corrections.yaml` to its `corrections-rejected.yaml`, tagged
  `rejected_by: architect`.
- `proposed_conventions` / `proposed_decisions` →
  `iterations/<n>/global.{conventions,decisions}.yaml` with
  harness-assigned ids (`v84-<n>.architect.{conv,dec}.<m>`) and
  `status: pending`.

**Status advance**: `next_step: validate`.

## Stage 6: validate

**When**: `next_step == "validate"`.

Two jobs in order:

**Job 1 — Cross-lead validation of architect's pending globals.**
Skipped when no globals are pending. Otherwise: fan out one
parallel call per active role-lead via the multi tier. Each lead
votes accept/reject on every pending entry in
`iterations/<n>/global.{conventions,decisions}.yaml` from its
role's perspective. Single-veto: any reject → record's status
becomes `rejected` with the rejecting role tagged in `rejected_by`
and the lead's reason stored as `rejection_reason`. Otherwise →
status: accepted. Records that no lead voted on stay pending and
get logged. Next round's architect sees rejected entries in its
context with the rejection reasons so it can reword or drop —
without re-proposing the same idea blindly.

Per-lead inputs: role + stack, conv/dec in scope (role + globals),
the pending global lists. Output: `{convention_verdicts,
decision_verdicts}` with `{id, verdict, reason (when reject)}`.
Instruction: `instructions/iteration/validate-globals.md`.

**Job 2 — Corrections-presence check.** No LLM call.
- Count entries in every `<role>.corrections.yaml` across active
  roles.
- If sum > 0: `iter_status.next_round_to("patch")` → round++,
  `next_step: patch`.
- If sum == 0: `iter_status.advance_to("user_review")`.

## Stage 7: patch (round 2+)

**When**: `next_step == "patch"` (set by validate when corrections
remain).

**Fan-out**: one parallel call per active role with non-empty
corrections.

**Per-role inputs** — same as draft, plus:
- The existing draft (`<role>.yaml`)
- Corrections to apply (`<role>.corrections.yaml`)

**Per-role output**: a patched actions list. Surviving actions
keep their ids; fixed actions get rewritten in place; missing
corrections become new actions following per-task numbering;
removed corrections drop the named action.

**Persistence**:
- New `<role>.yaml` overwrites the prior draft.
- Applied corrections move to `<role>.corrections-applied.yaml`
  (audit; next round's reviewers can verify what was honored).
- `<role>.corrections.yaml` cleared.
- Fresh conv/dec proposals raised by patch use the same prefix as
  round-1 (`v84-<n>.<role>.{conv,dec}`) and continue the numbering
  past the highest existing index so ids don't collide.

**Status advance**: `next_step: review`. The cycle continues from
review onward.

## Stage 8: user_review

**When**: `next_step == "user_review"` (set by validate when no
corrections remain).

**Job**:
1. Read every accepted convention/decision from the iteration —
   per-role + architect-proposed globals — and show them via the
   same `field_editor` UI used by the stack stage. Each entry is
   one field with the lead's chosen rule pre-selected.
2. For each entry the user can: keep as-is, pick an alternative,
   write custom text, or decline (`none`).
3. Promote every non-declined entry to project-root files —
   `<project>/v84/<role>.{conventions,decisions}.yaml` /
   `<project>/v84/global.{conventions,decisions}.yaml` — using
   the user's finalised wording.
4. Decide close-vs-restart by whether any KEPT rule's text changed:
   - **No change** (everything kept as-is, even if some declined)
     → write `iterations/<n>/tasks.md` (the implementer handoff)
     and advance `next_step: finish`. Existing actions still
     satisfy any rules that survived; declines only relax
     constraints.
   - **At least one change** (alt or custom) → clear cycle
     artifacts and reset to `{round: 1, next_step: draft}`. The
     new draft pass reads the updated rule set from project root.

The handoff document (`tasks.md`) bundles plan + roles + active
conv/dec + repo layout + tagging convention + per-role action
list — everything an external implementer (Claude Code, Cursor,
human) needs to translate the actions into actual code on disk.

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
