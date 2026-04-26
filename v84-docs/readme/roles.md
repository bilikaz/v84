# Roles

> Eight role templates ship with v84. None is required. A project
> activates the 3-6 that fit its shape.

Each role is a complete unit: one writer drafts the role's
actions, four reviewers each interrogate the draft from a single
lens, one lead synthesises. The architect (a separate global
layer, not a role) stitches across roles.

## The eight templates

| Role          | Surface                                     | When to activate                                          |
|---------------|---------------------------------------------|-----------------------------------------------------------|
| backend       | server-side code, APIs, services, entities  | project has a server layer                                |
| frontend      | web client — pages, primitives, state       | project has a web UI                                      |
| mobile        | native / cross-platform mobile app          | iOS, Android, RN, Flutter ship                            |
| devops        | infra, deps, CI/CD, observability           | project deploys beyond a developer's laptop               |
| testing       | the test suite — unit, integration, e2e     | anything beyond a throwaway prototype                     |
| brand         | visual system, voice, copy, consistency     | user-facing product with brand identity                   |
| data          | DB-native logic + analytics pipeline        | enterprise DB territory or first-class analytics          |
| integrations  | deep multi-module external integrations     | 100+ calls, vendor with own data model (ERP, EHR, …)      |

Templates live in `v84-docs/init/roles/<name>.yaml`. At project
init the selected ones are copied into
`<project>/v84/structure/roles/` and become editable per project.

## Per-role anatomy

Every role template carries:

```yaml
name: backend
title: Backend
when_activate: |
  <one-paragraph cue used by the suggest-roles agent>
responsibilities: |
  <multi-paragraph definition of what this role owns>
reviewers:
  - name: entities
    title: Data entities & schemas
    responsibilities: |
      <what this lens covers>
    challenge: |
      <the ONE question this reviewer holds>
    catches:
      - <example failure mode>
      - <…>
  - name: services
    ...
  - name: api
    ...
  - name: security
    ...
```

The **`challenge`** field is load-bearing: it's the single
question each reviewer keeps in mind while reading every action
the writer produced. That's what keeps narrow scope narrow. The
`catches` are framing examples, not an exhaustive list.

## The four-reviewer grid

| Role         | Reviewer 1   | Reviewer 2 | Reviewer 3   | Reviewer 4    |
|--------------|--------------|------------|--------------|---------------|
| backend      | entities     | services   | api          | security      |
| frontend     | primitives   | pages      | services     | api-boundary  |
| mobile       | ui-ux        | services   | entities     | security      |
| devops       | infra        | deps       | ci-cd        | observability |
| testing      | unit         | integration| e2e          | quality       |
| brand        | visual       | voice      | copy         | consistency   |
| data         | schema       | queries    | migrations   | analytics     |
| integrations | contracts    | flows      | resilience   | sync          |

Reviewer addresses are `role.reviewer_tag` — `backend.api`,
`frontend.pages`, `mobile.security`, etc.

Suggestion ids carry the same: `v84-1.frontend.pages.s.1` is "the
first suggestion from frontend's pages reviewer in iteration 1."

## Why four reviewers per role

**Not fewer**: narrow scope per reviewer is empirically the
hallucination-killer. Fewer than four either forces lenses to
combine (losing narrow-scope benefit) or leaves classes of defect
uncovered.

**Not more**: cost per round scales linearly with reviewer count.
Diminishing returns past ~4 lenses per role. Four covers the
major angles of attack without ceremony.

The grid is a recommendation, not a cage. Projects can add a 5th
reviewer when the domain demands it (regulated industries often
add `compliance`); going above four is a deliberate per-project
choice.

## Activating, customising, deactivating

**Activate**: pick the role at init via `roles` stage. The
template gets copied to `structure/roles/<name>.yaml` and the
project's `profile.yaml` adds the role to its `roles:` list.

**Customise**: edit the file in `<project>/v84/structure/roles/`.
Common customisations:

- Rename a reviewer to match project vocabulary
  (`frontend.api-boundary` → `frontend.bff` if the project has a
  real BFF).
- Rewrite a `challenge` to reference project-specific concerns.
- Add project-specific entries to `catches`.
- Remove a reviewer that genuinely doesn't apply (accept the
  coverage gap explicitly).

**Deactivate**: remove the file from `structure/roles/` and from
`profile.yaml`. The original template in `v84-docs/init/roles/`
stays intact — reactivating is a one-file copy.

## Activation examples

| Project shape                     | Typical active roles                       |
|-----------------------------------|--------------------------------------------|
| Backend-only API service          | backend, devops, testing                   |
| Mobile-only offline app           | mobile, testing, brand (if user-facing)    |
| Fullstack web SaaS                | backend, frontend, devops, testing, brand  |
| Data research / analytics platform| data, backend (if APIs), testing           |
| Static marketing site             | frontend, brand, devops                    |
| CLI tool / scripting set          | backend, testing                           |
| Mobile + backend app              | mobile, backend, testing, devops, brand    |

Most projects land at 3-6 active roles. No hard cap; cost scales
linearly.

## Roles are independent

Each role is a complete unit. Activating mobile doesn't require
backend; frontend can talk to a third-party API without backend;
data can stand alone for analytics-only projects.

The architect is the only agent that crosses role boundaries.
Reviewers and leads stay strictly inside their role. See
[four-layer-split.md](four-layer-split.md) for the responsibility
boundaries.
