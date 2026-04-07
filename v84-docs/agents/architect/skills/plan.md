# Skill: Plan

> Receive unstructured input and decompose it into a hierarchical iteration plan

## When To Use

When you receive a text description from a person about what needs to be done. The text can be vague or detailed — you decide the scope and depth.

## Steps

1. Read `/v84-docs/structure/roles.md` to understand which role agents to invoke after
2. Scan `/v84-docs/plan/` to determine the last iteration number `{n}`
3. Read the input text and decide: is this an epic, a feature, or already a task?
4. Create `/v84-docs/plan/{n+1}.md` with hierarchical breakdown
5. Create the directory `/v84-docs/plan/{n+1}/` for role agent outputs
6. Run `bash v84-docs/trees/generate.sh` to regenerate role-specific source trees

## Hierarchical Numbering

Everything follows the pattern `[v84-{n}]` with sub-levels separated by `-`:

```
[v84-{n}]         ← top level: big picture of what is going on
├── [v84-{n}-1]   ← first breakdown
│   ├── [v84-{n}-1-1]  ← smallest task unit (~4-5h)
│   ├── [v84-{n}-1-2]
│   └── [v84-{n}-1-3]
├── [v84-{n}-2]
│   ├── [v84-{n}-2-1]
│   └── [v84-{n}-2-2]
└── [v84-{n}-3]         ← might not need further breakdown
```

## Decomposition Rules

- You decide the depth — keep breaking down until each leaf is a ~4-5h task
- Some branches go deeper than others — that's expected
- Some items need no sub-levels if they're already small enough
- Do not use fixed labels like "epic/feature/story" — the numbering itself defines the hierarchy
- Describe WHAT needs to happen from a product/user perspective, not HOW
- Never specify technology choices per role — roles decide their own approach
- Never split work by role (no "backend task" / "frontend task") — describe the feature, each role figures out their part
- Mono repo is always assumed
- Keep descriptions concise but complete enough for role agents to assess impact

## Output Format

Write to `/v84-docs/plan/{n+1}.md`:

```
## [v84-{n+1}]
Big picture description of what is going on

## [v84-{n+1}-1]
What needs to happen (product level)

### [v84-{n+1}-1-1]
Smallest actionable thing described from user/product perspective

### [v84-{n+1}-1-2]
Another thing

## [v84-{n+1}-2]
Another piece of work

## [v84-{n+1}-3]
Already small enough — no sub-levels needed
```
