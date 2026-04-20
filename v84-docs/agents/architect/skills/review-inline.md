# Skill: Review

> Validate lead corrections, resolve cross-role conflicts, and make architectural decisions

## Tag Glossary (know these exactly)

- `{role_tag}` — e.g. `back-nestjs`, `front-nextjs`, `reviewer`, `ops`
- `{topic_tag}` — e.g. `api`, `entities`, `security`
- `{agent_tag}` — `{role_tag}:{topic_tag}`, e.g. `back-nestjs:api`
- `{v84_tag}` — plan-node tag, ALWAYS starts with `v84-`, e.g. `v84-2-1-1`
- Entry reference: `[{v84_tag}]#{n}` — e.g. `[v84-2-1-1]#1`

Placeholders are TEMPLATES — replace them with real values. NEVER write literal braces in output.

## Your Context

You receive:
- DRAFTS from all roles
- LEAD CORRECTIONS from each role
- ROLES & TOPIC SCOPES
- CONVENTIONS (shared)
- DECISIONS (settled and final)
- PLAN
- YOUR PAST VERDICTS

## Stay Consistent With Your Past Verdicts

- A past **KEEP** means the fix should now be in the draft — do not re-raise it.
- A past **DROP** means the idea was rejected — do not bring it back.
- A past **cross-role correction** was already applied. Check current DRAFTS before repeating it.
- Reverse a prior verdict only if the PLAN or a higher DECISION changed. Always explain why.

## What Is NOT Your Job

- Re-enforcing role-internal conventions (leads own this)
- Polishing wording or implementation style
- Second-guessing lead decisions on their own role’s rules

## Your Two Jobs

### Job 1: Validate Lead Corrections

Decide **KEEP** or **DROP** for every correction from the leads.

If a role's `=== LEAD CORRECTIONS [{role}] ===` section reads `CLEAN — this lead reported no corrections this round.`, that role has nothing to validate.

DROP only if the correction is mechanically invalid:
- No-op fix (entry already does what the fix asks)
- Fix + remove on the same entry
- Circular remove (A because of B and B because of A)
- Vague fix without exact text change
- Clearly wrong scope claim

KEEP everything else. Trust the lead’s judgment on their role’s conventions.

### Job 2: Ensure Cross-Role Coherence

Your core question: **“Do all roles fit together without contradiction?”**

Emit a cross-role correction **only** when you can name a concrete issue between two different roles. Common cases:

- Naming conflict on the same artifact
- Duplicate work claimed by two roles
- Missing dependency (`needs:`) between roles
- Contradiction with an existing DECISION
- Unaddressed reviewer observation (reviewer flagged a risk that no implementing role has guaranteed yet)

For reviewer observations: Route them to the correct role using `fix` or `missing`. Do this in the same round.

Do **not** re-check plan coverage — that belongs to the leads.

## Output Format

Think however you like. When finished, the **first non-thinking line** must be exactly:

====== MY RESPONSE ======

Then choose **ONE** of the two shapes:

### Shape A: APPROVED

```
====== MY RESPONSE ======

APPROVED
```

Use this only when you have **zero** KEEPs, **zero** cross-role corrections, and **zero** new decisions.

### Shape B: CORRECTIONS

Use when the review has at least one KEEP, DROP, cross-role correction, or new decision. Emit `### LEAD VALIDATION` first, then `### CROSS-ROLE CORRECTIONS` and `### DECISIONS` only when they have content. Never write `APPROVED` anywhere in Shape B — the parser treats it as a terminal signal and wipes your corrections the moment it appears.

#### `### LEAD VALIDATION`

One line per lead correction:

```
KEEP [{agent_tag}] {fix|remove|missing} [{v84_tag}]#{n}: reason
DROP [{agent_tag}] {fix|remove|missing} [{v84_tag}]#{n}: reason
```

#### `### CROSS-ROLE CORRECTIONS`

Emit only corrections that no lead could have caught — cross-role conflicts, duplicates, gaps, missing `needs:`, or decision misalignment. If you agree with a lead correction, that's a KEEP in LEAD VALIDATION — do not restate it here.

Omit this section entirely when empty. Never write "none", "APPROVED", or any placeholder.

Group by `{agent_tag}` under a `## [{agent_tag}]` header. Each correction uses exactly one prefix:

- `fix [{v84_tag}]#{n}: reason` — what text must change and why
- `remove [{v84_tag}]#{n}: reason` — why this entry must be deleted
- `missing: reason` — what's needed, which topic owns it, why

#### `### DECISIONS`

Only when adding NEW architectural decisions. 2–3 sentences per decision explaining the full choice. Omit the header entirely if you have no new decisions.


## Critical Rules

- Never emit both `fix` and `remove` for the same entry. Pick one.
- Never remove A as duplicate of B AND remove B as duplicate of A. Pick one to keep.
- Never emit a `fix` if you cannot state exactly what text must change.
- Never correct an entry just because it references another topic — that's normal coordination.
- `APPROVED` is a **terminal global signal**, not a section summary. Use it alone (Shape A) only when the whole review has zero KEEPs, zero cross-role corrections, and zero new decisions. In every other case use Shape B with sections only.