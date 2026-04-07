# Skill: Commit

> Create a git branch for the iteration and push the work

## When To Use

After publish is complete and the 32 final files are updated.

## Steps

1. Create a branch named `v84-{n}` from the current HEAD
2. Stage all changes: source code, v84-docs (plan/, final/, trees/), config files
3. Create a commit with a conventional commit message summarizing the iteration
4. Push the branch to remote

## Commit Message Format

Use Conventional Commits. The v84 tag is the scope:

```
feat(v84-{n}): {one-line summary of what this iteration delivered}

Tasks completed:
- [v84-{n}-1] {description}
- [v84-{n}-2] {description}
- ...
```

Example:
```
feat(v84-1): secret message storage with pirate theme

Tasks completed:
- [v84-1-1] Initial project setup (NestJS + Next.js + Docker)
- [v84-1-2] Leave-a-message flow (POST /messages, returns key)
- [v84-1-3] Retrieve-a-message flow (GET /messages/:key)
- [v84-1-4] Pirate-themed UI (treasure chest hero, gold/brown palette)
```

## Commands

```bash
git checkout -b v84-{n}
git add .
git commit -m "feat(v84-{n}): {summary}"
git push -u origin v84-{n}
```

## What NOT To Do

- Do not commit to main/master directly — always create a branch
- Do not force push
- Do not commit node_modules, .env, dist, .next (verify .gitignore covers these)
- Do not commit if verify steps in tasks.md failed — all phases must be [done]
