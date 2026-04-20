# Skill: Run

> Drive the full v84 pipeline from the user's description through promoted code

## When To Use

First skill you invoke each session. The user describes what they want to build or change; you execute the pipeline end-to-end by calling the scripts in `v84-docs/scripts/`.

## Check state first

List `v84-docs/plan/` and decide where to resume:

- No `plan/{n}.md` that isn't already promoted to `final/plan.md` → start a new iteration. Assign the next unused integer as `{n}`.
- `plan/{n}.md` exists but `plan/{n}/` is empty → resume from Cycle.
- `plan/{n}/{role}/*.md` drafts exist, no `plan/{n}/approved.md` → resume from Cycle.
- `plan/{n}/approved.md` exists, no `plan/{n}/tasks.md` → resume from Extract.
- `plan/{n}/tasks.md` exists, source is partly untagged per `generate-missing.sh` → resume from Implement.
- Everything tagged, `final/plan.md` missing an iteration entry for `{n}` → resume from Promote.

Always finish an in-progress iteration before starting a new one.

## Ask the user if the intent isn't clear

If the user has already described the work, use it. Otherwise ask: "What would you like to build or change?"

If the description would realistically need more than ~5–6 plan nodes or bundles multiple unrelated features, split into sequential iterations. Present the split, wait for confirmation, then proceed one iteration at a time.

## Pipeline steps

All scripts read LLM provider + model from env (`LLM_API_URL`, `LLM_PROVIDER`, `LLM_MODEL`). Set them once per session — see `v84-docs/readme/running-scripts.md` for detection rules.

### 1. Plan

```
v84-docs/scripts/architect/run.sh plan {n} "<user description>"
```

Writes `plan/{n}.md` + empty `plan/{n}/` working directory.

### 2. Cycle until approved

```
v84-docs/scripts/cycle/run.sh {n} 15
```

Loops draft → lead → architect review until `plan/{n}/approved.md` appears (or the max-rounds cap, default 10; pass 15–20 for safety). Do not invoke `agents/`, `leads/`, or `architect/` scripts directly — `cycle/run.sh` already handles parallelism, patches, and verdict parsing.

### 3. Extract tasks

```
v84-docs/scripts/executor/extract.sh {n}
```

Writes `plan/{n}/tasks.md`.

### 4. Implement

Hand off to the `execute.md` skill with `plan/{n}/tasks.md` as input. That skill owns code writing, tagging, migration generation (using `v84-docs/scripts/dev/run.sh` for the lifecycle around it), and testing (via `v84-docs/scripts/tests/run.sh`).

### 5. Promote

```
v84-docs/scripts/executor/finish.sh {n}
```

If earlier plan drafts were hand-edited after-the-fact, replay the whole history instead:

```
v84-docs/scripts/executor/finish-all.sh
```

## Rules

- One script per step — never improvise parallel LLM calls, per-role runs, or direct agent dispatch. If a step lacks a script, that's a bug in the pipeline, not a reason to hand-roll.
- If a script fails, surface the error with its log path and stop. Don't patch around it by calling another script.
- Never skip straight from Plan to Implement — the cycle's corrections are what keep drafts aligned with conventions.
- Don't write files outside what `execute.md` allows. Pipeline scripts own `plan/`, `context/`, `trees/`, `final/`; you only touch `apps/`, `docker/`, `e2e/`, `brand/` during Step 4.
