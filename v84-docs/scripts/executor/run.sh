#!/bin/bash

# Executor: write code for all tasks in plan/{n}/tasks.md.
#
# STATUS: not implemented as a bash script — requires an AI agent with tool
# access (Write, Edit, Bash for running tests). Run this step via:
#
#   - Claude Code: invoke the executor agent interactively, pointing at tasks.md
#   - Claude Agent SDK: build a harness that reads tasks.md and calls the API
#     with tool use enabled to write files
#
# Usage (when implemented):
#   ./v84-docs/scripts/executor/run.sh <iteration>
#
# What the executor must do:
#   1. Read plan/{n}/tasks.md top-to-bottom
#   2. For each task, honor depends: ordering — skip tasks whose deps aren't done
#   3. Read conventions, tree, packages from context/ for the task's role
#   4. Write code to files listed in files: field
#   5. Tag each touched file with a comment: [v84-{n}-x-x][role:topic]
#   6. Run tests/build/lint after each phase to catch regressions
#   7. If stuck, leave the task and continue — don't block the whole iteration
#
# Sibling scripts (deterministic, no AI needed):
#   extract.sh  — pulls task: entries into plan/{n}/tasks.md
#   finish.sh   — promotes plan/{n}/ to final/, appends plan history

echo "executor/run.sh is a stub — run the executor agent via Claude Code or a harness"
echo "Input:  v84-docs/plan/${1:-<iteration>}/tasks.md"
echo "Output: source code under apps/"
exit 1
