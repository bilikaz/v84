# Skill: Resolve

> Review all role assessments, merge them into the plan with prefixed tags, resolve contradictions inline

## When To Use

After all 4 role agents have completed their assessments for iteration `{n}`.

## Steps

1. Read the plan file at `/v84-docs/plan/{n}.md`
2. Read all role assessments at `/v84-docs/plan/{n}/{role-tag}.md`
3. Read `/v84-docs/structure/roles.md` for roles and topics, `/v84-docs/structure/conventions.md` for naming rules, `/v84-docs/structure/stack.md` for package references
4. Merge all role content into the plan using `{role-tag}-{topic-tag}` prefixed tags
5. Resolve contradictions INLINE where they appear — not in a separate section
6. Normalize names — scan for the same concept called different things across roles and pick one canonical name
7. Flag and remove hallucinated content that isn't grounded in the plan or structure.md
8. Write the merged version to `/v84-docs/plan/{n}/resolved.md` — do not modify the original `{n}.md`
8. Do not create directories — they already exist

## How To Merge

- Keep the existing `[v84-{n}-x-x]` hierarchy from the original plan
- Copy each role's topic items into the plan under the matching `[v84-{n}-x-x]` node
- Rename topic tags to `{role-tag}-{topic-tag}` format: `- [back-nestjs-entities]`, `- [front-nextjs-components]`, `- [devops-qa-security]`, etc.
- Copy the content as the role agent wrote it — do not rewrite or summarize

## How To Resolve Contradictions

Contradictions MUST be resolved inline where the items appear, NOT in a separate section at the bottom.

When two roles disagree (e.g. backend says UUID v4, devops says nanoid 21 chars):
- Keep the winning item as-is
- Mark the losing item with `[rejected]` before its content
- Add a `resolved:` line immediately after explaining the decision
- Do NOT use markdown formatting like `~~strikethrough~~` or `> blockquotes` — IDEs corrupt these

Example:
```
## [v84-1-1]
Create initial project setup

- [back-nestjs-entities] Message: key (varchar(36), UUID v4)
- [devops-qa-security] [rejected] Key must be nanoid 21+ chars for 128 bits entropy
  resolved: UUID v4 provides 122 bits which is sufficient. Native NestJS/Node support, no extra dependency.
```

## How To Handle Hallucinations

If a role agent added requirements not grounded in the plan or structure.md:
- Remove the hallucinated item entirely
- Do not include it with [rejected] — it was never a valid proposal, just noise
- Examples of hallucinations: adding JWT/auth when the plan says no auth, adding encryption when not mentioned, referencing libraries not in the project stack, mitigating attack vectors that don't apply

## How To Normalize Names

After merging all roles, scan for fields, columns, endpoints, or components that refer to the same thing with different names (e.g. one role says `content`, another says `body`, another says `message` — all meaning the stored message text).

- Pick the simplest, most descriptive name
- Apply it consistently across ALL role items in the merged output
- Where you change a name, add inline: `resolved: renamed from {old} to {new} for consistency`
- The first role to define something sets the baseline — other roles align to it unless there's a good reason not to
- This applies to: entity columns, API field names, endpoint paths, component names, env variable names

Example:
```
- [back-nestjs-entities] Message: content (text, max 5000)
- [front-nextjs-forms] Zod schema: { content: z.string().max(5000) }
  resolved: renamed from body to content — aligning to backend entity name
```

## Adding Missing Work

If assessments revealed work genuinely implied by the plan but not explicitly stated, add new `[v84-{n}-x]` entries.

## Output

`/v84-docs/plan/{n}/resolved.md` — the merged, resolved version with all role content included and contradictions resolved inline. The original `{n}.md` stays untouched.

Do NOT include a "Resolved contradictions" section at the bottom — everything is resolved where it appears in the plan hierarchy.

## What You Do NOT Do

- Do not rewrite or summarize role content — copy it as-is (except hallucinations which are removed)
- Do not put contradictions in a separate section — resolve them inline
- Do not pick sides based on preference — resolve based on what makes technical sense
- Do not allow shared code/types/packages between roles that have different boundaries (e.g. backend and frontend). The API contract is the boundary. UI components shared within the frontend world (e.g. packages/ui/) are fine.
- Do not create directories — they already exist
