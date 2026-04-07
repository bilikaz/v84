# Skill: Run

> Check project state, resume if interrupted, execute the full pipeline

## When To Use

Every time the user starts a conversation. You are the first and only agent the user interacts with.

## Flow

### 1. Check state

Read `/v84-docs/state.md` first:
- If `status: init` → project needs setup. Run architect init skill (guided conversation with user). After init completes, update state to `status: idle`.
- If `status: idle` → ready for new work, go to step 2
- If `status: running` → previous run was interrupted. Read the state to find where it stopped and resume from that step.
- If `status: failed` → previous run failed. Tell the user what failed and ask if they want to retry or rollback.

### 2. Ask the user what they want

If state.md contains `init-request:` (set during init), use that as the first iteration input — the user already described the project. Clear it from state.md after reading.
If the user already provided input in this conversation (e.g. "I want to add user authentication"), use that.
Otherwise ask: "What would you like to build or change?"

### 3. Evaluate scope and split if needed

Before passing to the architect, evaluate if the request is too large for a single iteration. Signs it's too large:
- Multiple unrelated features ("add auth AND real-time chat AND payment processing")
- Would produce more than ~5-6 plan nodes at the top level
- Touches every part of the system simultaneously
- Would generate a tasks.md that exceeds what one executor pass can handle reliably

If too large, split into sequential iterations:
1. Break the request into self-contained chunks that can be built one after another
2. Present the split to the user: "This is a big one. I'd break it into 3 iterations: (1) user auth, (2) real-time chat, (3) payments. Each builds on the last. Sound good?"
3. Wait for confirmation
4. Write the iteration queue to state.md

If small enough for one iteration, proceed directly.

### 4. Run the pipeline (per iteration)

Before each step, update state.md with current progress. After each step completes, mark it done in state.md.

```
Step 1: Plan
  → architect plan skill
  → produces plan/{n}.md + plan/{n}/ directory + refreshed trees

Step 2: Assess (parallel)
  → 4 role agents run assess skill simultaneously
  → produces plan/{n}/{role-tag}.md

Step 3: Resolve
  → architect resolve skill
  → produces plan/{n}/resolved.md

Step 4: Compare (parallel)
  → 4 role agents run compare skill simultaneously
  → produces plan/{n}/{role-tag}-final.md

Step 5: Finalize
  → architect finalize skill
  → produces plan/{n}/final.md + plan/{n}/tasks.md

Step 6: Execute
  → executor agent runs execute skill
  → writes code, runs commands, verifies each phase
  → marks phases [done] in tasks.md

Step 7: Publish
  → architect publish skill
  → updates final/{role-tag}-{topic-tag}.md files + refreshes trees

Step 8: Commit
  → architect commit skill
  → creates branch v84-{n}, commits, pushes
```

### 5. Report completion

Tell the user:
- What was built (summary from tasks.md)
- The git branch name(s)
- If split into multiple iterations, summarize each
- Any issues encountered during verify steps

Update state.md to `status: idle`.

## How To Update state.md

Update state.md at every significant moment. The format:

### When starting a new run:
```
## Current Run

status: running
started: {date}
request: {what the user asked for}
iterations: {n} through {m} (or just {n} if single)

## Active Iteration

iteration: {n}
step: plan
step-status: running
```

### When a step completes:
```
step: plan
step-status: done
```
Then update step to the next one with `step-status: running`.

### When execute step is running — track phases:
```
## Active Iteration

iteration: {n}
step: execute
step-status: running
phase: 3-backend
phase-status: running
phases-done: 1-scaffold, 2-infrastructure
```

Update `phase` and `phases-done` as executor progresses. This allows resume to the exact phase if interrupted. Phase names: `1-scaffold`, `2-infrastructure`, `3-backend`, `4-frontend`, `5-database`, `6-tests`, `7-polish`.

### When split into multiple iterations:
```
## Iterations Queue

1 ~ v84-{n} ~ user authentication ~ pending
2 ~ v84-{n+1} ~ real-time chat ~ pending
3 ~ v84-{n+2} ~ payment processing ~ pending
```

Mark each as `running` then `done` as they complete.

### When an iteration completes:
```
## Completed Iterations

v84-{n} ~ user authentication ~ done ~ branch: v84-{n}
```

### When everything is done:
```
## Current Run

status: idle
started: -
iterations: -
```

### When something fails:
```
## Current Run

status: failed
started: {date}
request: {what the user asked for}
iterations: v84-{n}

## Active Iteration

iteration: {n}
step: execute
step-status: failed
phase: 5-database
phase-status: failed
phases-done: 1-scaffold, 2-infrastructure, 3-backend, 4-frontend
error: Phase 5 failed — migration:generate failed, db container not running
```

## How To Resume After Interruption

When you read state.md and see `status: running`:

1. Read which step was running
2. Check if that step's output files exist:
   - plan/{n}.md exists → plan is done
   - plan/{n}/{role-tag}.md files exist → assess is done
   - plan/{n}/resolved.md exists → resolve is done
   - plan/{n}/{role-tag}-final.md files exist → compare is done
   - plan/{n}/final.md + tasks.md exist → finalize is done
   - state.md phases-done lists all 7 phases → execute is done
   - final/ files updated for this iteration → publish is done
3. If interrupted during execute, check `phase` and `phases-done` in state.md:
   - Resume executor with `resume-from:` set to the incomplete phase number
   - Tell the user: "Interrupted during execution, Phase {n} ({name}). Phases 1-{n-1} completed. Resuming from Phase {n}."
4. For all other steps, resume from the first incomplete step
5. Tell the user: "Looks like we were interrupted during {step}. Resuming from there."

## How To Determine Iteration Number

Scan `/v84-docs/plan/` for existing `{n}.md` files. The next iteration is `max(n) + 1`. If no plans exist, start at 1.

## How To Handle Errors

- If a verify step fails during execute → let the executor fix it (it retries automatically)
- If the executor fails repeatedly → update state.md to failed, run architect rollback skill, tell the user what went wrong, ask if they want to retry or rollback
- If an assess agent produces hallucinations → resolve will catch them, no action needed from you

## What NOT To Do

- Do not ask the user to run specific pipeline steps — you handle everything
- Do not expose pipeline internals — the user doesn't need to know about assess/resolve/compare
- Do not skip steps — even if the change seems small, run the full pipeline
- Do not modify files yourself — delegate to the appropriate agent/skill
- Do not forget to update state.md — it's the recovery mechanism
