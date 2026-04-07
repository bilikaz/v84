# Skill: Rollback

> Revert a failed iteration and return to clean state

## When To Use

When the executor fails repeatedly on verify steps and the iteration cannot be completed, or when the output is fundamentally wrong and needs to be redone.

## Steps

1. Check if a branch `v84-{n}` was created — if yes, switch back to the previous branch
2. Remove all source code changes from this iteration using `git checkout .` or `git stash`
3. Keep the v84-docs plan files (plan/{n}.md, assessments, resolved.md) — they represent the thinking and can be reused
4. Clear the execution outputs: remove tasks.md [done] markers, delete generated source files
5. Run `bash v84-docs/trees/generate.sh` to restore trees to pre-iteration state

## Commands

```bash
# If on a v84-{n} branch, go back
git checkout main
git branch -D v84-{n}

# Or if uncommitted, just reset
git checkout -- apps/ packages/ docker/ .github/ e2e/
git clean -fd apps/ packages/ docker/ .github/ e2e/

# Refresh trees
bash v84-docs/trees/generate.sh
```

## What To Keep

- `v84-docs/plan/{n}.md` — the original plan is still valid
- `v84-docs/plan/{n}/` — assessments and resolved.md can be reused
- `v84-docs/final/` — only if publish hasn't run yet; if it has, revert final/ too

## What To Remove

- Source code written by executor (apps/, packages/, docker/, etc.)
- [done] markers from tasks.md
- Branch if created

## After Rollback

You can either:
1. Fix the skills/tasks and re-run from finalize (step 6) if the thinking was good but execution was bad
2. Re-run from assess (step 3) if the role agents made bad decisions
3. Re-run from plan (step 2) if the plan itself was wrong
