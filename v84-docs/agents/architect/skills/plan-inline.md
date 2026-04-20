# Skill: Plan

> Read context and user request, output a hierarchical iteration plan

## Your Context

Everything you need is provided to you — all conventions and plan history of completed iterations.

## Output

Think however you like — analyze, reason, sketch alternatives, check the decomposition rules below. When you're ready to write the final plan, mark the start:

====== MY RESPONSE ======

After the marker, output ONLY the plan content — `## [v84-{n}]` headings with descriptions. No preamble, no commentary, no closing notes.

```
## [v84-{n}]
Big picture description

## [v84-{n}-1]
What needs to happen (product level)

### [v84-{n}-1-1]
Complete deliverable described from user/product perspective

## [v84-{n}-2]
Another piece of work — no sub-levels if already small enough
```

## Decomposition Rules

- Each leaf should be a **complete deliverable** — something a user could see or test when done
- Do NOT split into tiny steps that force reimplementation
- Stop decomposing when each leaf describes one coherent feature or behavior. Topic agents decide how to break it into files and tasks.
- **Every distinct deliverable is its own `### [v84-{n}-x-x]` leaf.** Inline bullet lists inside a group description are NOT a substitute. If the group contains two or more things a user could test independently (e.g. "register + send verify email" and "click verify link + activate account"), each one MUST be its own `###` leaf. A group with multiple deliverables but no `###` leaves is always wrong — find the leaves.
- **A group must have at least 2 leaves, or it must not be a group at all.** Only when a group has a single atomic deliverable should you skip the `###` level and keep the detail inside `[v84-{n}-x]`. Single-leaf groups are otherwise a signal either to merge up, or to find the second leaf you missed (e.g. request + completion, issue + consume, send + receive).
- Describe the product outcome **and** the shared vocabulary — but not the implementation:
  - **Name cross-role contracts in the leaf.** Whenever multiple roles must agree on the same identifier — HTTP routes (`POST /auth/verify-email`), page/component names (`RegisterPage`, `VerifyEmailPage`), key entity fields/flags (`isVerified`, `verificationToken`), event names, queue names — spell them out. That's a contract between roles, not HOW. It stops drift like back-nestjs:api writing `POST /auth/confirm` while front-nextjs:pages wires to `POST /auth/verify-email`.
  - **Leave HOW to the topic agents.** File paths, folder layout, class internals, SQL shape, library picks (e.g. "bcrypt", "passport-local", "react-hook-form") are role decisions. Do not name them in the plan.
- Never split work by role — group by **user outcome**, not by which role implements it. Every role a leaf touches must contribute to the same externally visible feature.
  - ❌ Bad: `[v84-3-1] User Model & Email Infrastructure` — groups "entity fields" and "email templates" because they share no user outcome, only the fact that the backend team writes them.
  - ❌ Bad: `[v84-3-4] Frontend Dashboard & BFF Integration` — groups "user dashboard" and "BFF proxy routes" by layer, not by the user-facing deliverable.
  - ✅ Good: `[v84-3-1] Registration & verification` — registration and verification are one user outcome; every role (entities, services, api, notifications, pages, forms, BFF) contributes to it.

## Rules

- Output plan content only — no explanations, no commentary
- Use `## [v84-{n}]` for top level, `## [v84-{n}-x]` for features, `### [v84-{n}-x-x]` for deliverables
- Check plan history in your context to avoid duplicating past work
