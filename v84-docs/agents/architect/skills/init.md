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
- Web app → Business, Backend Developer, Frontend Developer, DevOps & QA
- Mobile app → Product Owner, API Developer, Mobile Developer, QA & Release
- Construction → Project Manager, Structural Engineer, Site Supervisor, Safety & Compliance
- Data pipeline → Data Analyst, Data Engineer, ML Engineer, Platform & Ops

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
Once all is confirmed, create the full structure. These directories always exist as part of the v84 template — do not attempt to create them: `plan/`, `trees/`, `final/`, `structure/`.

#### structure/ — always overwrite
Read these 3 example files as reference for format and conventions:
- `/v84-docs/structure/example/roles.md`
- `/v84-docs/structure/example/conventions.md`
- `/v84-docs/structure/example/stack.md`

Then write all 3 files (always overwrite — these define the current project):

**structure/roles.md** — Roles table (tag, name, agent path) and topics by role (tag, topic, description). See example.

**structure/conventions.md** — Naming rules, ID strategy, code organization, error handling, logging, styling conventions. See example for full list of categories.

**structure/stack.md** — Project stack table (infrastructure not npm packages), installed packages grouped by app (Package ~ Version ~ Used For ~ Key Methods/Patterns), and monorepo structure.

The example files stay in the repo permanently as a reference — do not delete them.

#### Agent folders — check before creating
For each role, check if the agent already exists:

- If `/v84-docs/agents/{role-tag}/agent.md` does NOT exist → create the full folder structure:
  - `/v84-docs/agents/{role-tag}/agent.md` — identity, skills list referencing shared skills
  - `/v84-docs/agents/{role-tag}/skills/` — folder for any role-specific skills
- If it already exists → skip. Do not overwrite existing agent files.

Agent naming should be specific to the tech: `back-nestjs`, `front-nextjs`, `back-django`, `front-flutter`, etc. This way multiple agents of the same category can coexist if the project grows.

Non-tech roles keep simple names: `business`, `devops-qa`, `safety`, etc.

#### Final files — always create empty
Create all 32 empty files (4 roles × 8 topics):
- `/v84-docs/final/{role-tag}-{topic-tag}.md`

No need to check — this is init, there are no past artifacts. They must be empty.

#### Trees — generate the script
- Write `/v84-docs/trees/generate.sh` — shell script that generates role-specific source trees
- Configure which paths each role cares about based on the confirmed project structure (e.g. backend agent gets `apps/api/src`, frontend gets `apps/web/src` + `packages/ui/src`, devops gets `docker` + `.github`)
- The script outputs `{role-tag}.tree` files plus a `full.tree` for project overview
- Exclude common noise: node_modules, .next, dist, coverage, .git, lock files
- Make the script executable (`chmod +x`)

#### state.md
- Write `/v84-docs/state.md` with `status: idle` (init just completed, ready for first iteration)
- Include `init-request:` with the user's project description from Step 1 — this becomes the input for the first iteration so the user doesn't have to repeat themselves

## Agent Template

Each agent.md should follow this structure:

```
# Agent: {Name}

> {One-line role description}
> Tag: {role-tag}

## Identity

{What this agent represents and its perspective}

## Skills

shared/skills/assess.md ~ Evaluate a plan iteration from this role's perspective
shared/skills/compare.md ~ Compare resolved plan against existing final docs
{any role-specific skills}
```

## What NOT To Do

- Do not dump all questions at once — guide step by step, suggest, wait for confirmation
- Do not assume the user knows architecture — you suggest, they pick
- Do not create shared packages between roles with different boundaries
- Do not skip confirmation — always wait for user approval before generating
- Do not create final files with placeholder content — they must be empty
- Do not overwrite existing agent files — only create missing ones
- Do not re-run init on an already-initialized project — state.md will tell you
- Do not attempt to create plan/, trees/, final/, structure/ directories — they always exist as part of the v84 template

## Output

A fully initialized v84-docs structure ready for the first iteration.
