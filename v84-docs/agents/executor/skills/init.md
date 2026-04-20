# Skill: Init

> Set up the entire v84 documentation structure for a new project through a guided conversation with the user

## When To Use

When starting a new project from scratch. The user has no v84-docs structure yet.

## Conversation Flow

This is a guided wizard. The user may be a vibe coder with no architecture knowledge. You suggest, they confirm or tweak. Never dump all questions at once — go step by step.

### Step 1: Understand the project
Ask: "What are you building? Describe it in your own words."
Let them describe freely. Don't ask about tech yet.

### Step 2: Suggest 4 roles
Based on what they described, suggest 4 roles that make sense for their project. Explain briefly why each role matters.

Examples:
- Web app → Reviewer, Backend Developer, Frontend Developer, Ops
- Mobile app → Reviewer, API Developer, Mobile Developer, Ops
- Construction → Reviewer, Structural Engineer, Site Supervisor, Ops
- Data pipeline → Reviewer, Data Engineer, ML Engineer, Ops

Present your suggestion and ask: "Do these 4 roles work for you, or would you change any?"

Wait for confirmation before proceeding.

### Step 3: Suggest 8 topics per role
For each confirmed role, suggest 8 topics that cover the most important areas. Keep descriptions short.

Present all 4 roles' topics together and ask: "Do these topics cover what matters? Anything to add or swap?"

Wait for confirmation before proceeding.

### Step 4: Suggest tech stack and tooling
Read `/v84-docs/structure/suggestions.md` and all suggestion files in `/v84-docs/structure/suggestions/`. Apply any matching suggestion rules to your recommendations.

Based on the project description, suggest:
- Tech stack (frameworks, database, language)
- Dev environment (Docker, local, cloud)
- Testing approach
- CI/CD
- Any other tooling that fits

Present as a table and ask: "Does this stack work? Anything you'd prefer differently?"

Wait for confirmation before proceeding.

### Step 5: Generate everything
Once all is confirmed, create the full structure. These directories always exist as part of the v84 template — do not attempt to create them: `plan/`, `trees/`, `final/`, `structure/`, `scripts/`.

#### structure/ — always overwrite
Read the full example tree as reference for format and the level of detail that produces usable conventions:
- `/v84-docs/structure/example/roles.md`
- `/v84-docs/structure/example/conventions.md`
- `/v84-docs/structure/example/conventions/{role}.md` — one file per role

The example is a complete sample project (NestJS API + Next.js web + ops + reviewer). Treat it as a shape guide, not a prescription — adapt names, rules, and topic choices to whatever the user is actually building.

Then write these files (always overwrite — they define the current project):

**structure/roles.md** — Roles table (tag, name, description) + topics by role (tag, topic, scope, NOT-yours) per the shared example format.

**structure/conventions.md** — Shared rules loaded into every agent's system message: project stack, monorepo layout, naming, IDs, migrations, testing philosophy, brand.

**structure/conventions/{role}.md** — One file per role with role-specific rules (folder structure, per-topic naming, patterns). Only loaded into that role's agents + the architect. Create one per role defined in `roles.md`.

Installed npm packages are auto-extracted per role by `build-context.sh` from each workspace's `package.json` — do NOT maintain a manual package list.

The example tree stays in the repo permanently as a reference — do not delete it.

#### Agent folders — check before creating
For each role, check if the agent already exists:

- If `/v84-docs/agents/{role-tag}/agent.md` does NOT exist → create it
- If it already exists → skip. Do not overwrite existing agent files.

Agent naming should be specific to the tech: `back-nestjs`, `front-nextjs`, `back-django`, `front-flutter`, etc. This way multiple agents of the same category can coexist if the project grows.

Non-tech roles keep simple names: `reviewer`, `ops`, `safety`, etc.

#### Executor agent — embed code patterns
The executor agent at `/v84-docs/agents/executor/agent.md` needs code patterns embedded directly in it. After confirming the tech stack, write patterns for each major package (ORM, framework, Docker, etc.) into the executor's "Embedded Knowledge" section. These become part of the system message — the executor never reads separate pattern files.

#### Final files — always create empty
Create all 32 empty files (4 roles × 8 topics):
- `/v84-docs/final/{role-tag}-{topic-tag}.md`

No need to check — this is init, there are no past artifacts. They must be empty.

#### Trees — generate the script
- Write `/v84-docs/scripts/generate-trees.sh` — shell script that generates role-specific source trees
- Configure which paths each role cares about based on the confirmed project structure (e.g. backend agent gets `apps/api/src`, frontend gets `apps/web/src` + `apps/storybook`, ops gets `docker` + `.github`)
- The script outputs `{role-tag}.tree` files plus a `full.tree` for project overview
- Exclude common noise: node_modules, .next, dist, coverage, .git/, lock files
- Make the script executable (`chmod +x`)

#### Scripts — already exist
The scripts directory (`v84-docs/scripts/`) is part of the v84 template — do not recreate or modify it. It contains: `build-context.sh`, `generate-trees.sh`, `generate-missing.sh`, `detect-llm.sh`, `llm-api.sh`, and the subfolders `architect/`, `agents/`, `leads/`, `cycle/`, `executor/`, `dev/`, `tests/`. See `v84-docs/readme/running-scripts.md` for what each does.

#### Initial context
Run `bash v84-docs/scripts/build-context.sh 1` after creating structure files. This generates `v84-docs/context/` with bundled conventions so topic agents and the architect can each read one file for iteration 1.

## Agent Template

Each agent.md should follow this structure:

```
# Agent: {Name}

> {One-line role description}
> Tag: {role-tag}

## Identity

{What this agent represents and its perspective}

## Skills

shared/skills/draft.md ~ Read plan + topic history, write tagged entries
shared/skills/patch.md ~ Apply architect corrections to flagged entries
{any role-specific skills}
```

The executor agent has an additional "Embedded Knowledge" section with code patterns — see the existing executor agent for the format.

## What NOT To Do

- Do not dump all questions at once — guide step by step, suggest, wait for confirmation
- Do not assume the user knows architecture — you suggest, they pick
- Do not create shared packages between roles with different boundaries
- Do not skip confirmation — always wait for user approval before generating
- Do not create final files with placeholder content — they must be empty
- Do not overwrite existing agent files — only create missing ones
- Do not re-run init on an already-initialized project — check if structure/ and agents/ exist
- Do not attempt to create plan/, trees/, final/, structure/, scripts/ directories — they always exist as part of the v84 template
- Do not create separate pattern files — code patterns are embedded in the executor agent

## Output

A fully initialized v84-docs structure ready for the first iteration.
