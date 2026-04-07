# v84 Pipeline — Execution Order

The orchestrator manages the entire pipeline. It reads `state.md` to know where to start/resume, updates it at every step, and handles interruptions automatically.

Users interact with the orchestrator only: `v84-docs/agents/orchestrator/skills/run.md`

## For a new project (once)

```
Step 0: Init
  who: architect
  skill: init.md
  input: conversation with user
  output: structure/, agents/, final/ (32 empty files), plan/, trees/
```

## For each iteration

```
Step 1: Plan
  who: architect
  skill: plan.md
  input: unstructured text from user
  output: plan/{n}.md, plan/{n}/ directory, refreshed trees
  then: trigger step 2

Step 2: Assess
  who: business, back-nestjs, front-nextjs, devops-qa (parallel)
  skill: shared/assess.md
  input: plan/{n}.md + structure/roles.md + structure/conventions.md + trees/{role}.tree
  output: plan/{n}/business.md, plan/{n}/back-nestjs.md, plan/{n}/front-nextjs.md, plan/{n}/devops-qa.md
  then: trigger step 3 when all 4 complete

Step 3: Resolve
  who: architect
  skill: resolve.md
  input: plan/{n}.md + all 4 assess outputs + structure/
  output: plan/{n}/resolved.md
  then: trigger step 4

Step 4: Compare
  who: business, back-nestjs, front-nextjs, devops-qa (parallel)
  skill: shared/compare.md
  input: plan/{n}/resolved.md + final/{role}-{topic}.md files
  output: plan/{n}/business-final.md, plan/{n}/back-nestjs-final.md, plan/{n}/front-nextjs-final.md, plan/{n}/devops-qa-final.md
  then: trigger step 5 when all 4 complete

Step 5: Finalize
  who: architect
  skill: finalize.md
  input: all 4 compare outputs + structure/
  output: plan/{n}/final.md + plan/{n}/tasks.md
  then: trigger step 6

Step 6: Execute
  who: executor
  skill: shared/execute.md
  input: plan/{n}/tasks.md + structure/conventions.md + structure/patterns/
  output: actual source code, config, tests — all tagged with [v84-{n}-x-x]
  verify: each phase must pass before next
  then: trigger step 7 when all phases [done]

Step 7: Publish
  who: architect
  skill: publish.md
  input: plan/{n}/final.md + plan/{n}/tasks.md + final/ files
  output: updated final/{role}-{topic}.md files, refreshed trees
  then: trigger step 8

Step 8: Commit
  who: architect
  skill: commit.md
  input: all changes from this iteration
  output: git branch v84-{n}, pushed to remote
  then: iteration complete — ready for next plan
```

## State Tracking

`state.md` is updated at every step by the orchestrator. It tracks:
- Current status: init / idle / running / failed
- Active iteration and which step is running
- Iterations queue (if request was split into multiple)
- Completed iterations with branch names
- Error details if failed

If the process is interrupted (power loss, token limit, session timeout), the orchestrator reads state.md on next start and resumes from the last incomplete step.

## If something goes wrong

```
Rollback
  who: architect
  skill: rollback.md
  when: executor fails repeatedly, or output is fundamentally wrong
  action: revert source code, keep plan docs, update state.md to failed
```

## Re-run points

If execution failed ~ re-run from step 6 (Execute)
If tasks are wrong ~ re-run from step 5 (Finalize)
If resolve missed something ~ re-run from step 3 (Resolve)
If assessments are bad ~ re-run from step 2 (Assess)
If plan is wrong ~ re-run from step 1 (Plan)
