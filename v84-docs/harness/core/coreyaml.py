"""
coreyaml.py — Read, mutate, and write <project>/v84/core.yaml.

core.yaml carries the project's task list (recursive: each task
can have a `tasks:` list of sub-tasks under it) plus iteration
state (`current_iteration`, `completed_iterations`).

This module owns the YAML render so every stage emits the same
shape, comments, and ordering. Stages call:

    read(project_dir)            → dict
    write(project_dir, data)     → Path
    next_unplanned(data)         → first top-level task without sub-tasks
    insert_subtasks(data, parent_id, subtasks) → mutates `data` in place

All ID assignment lives here too — the LLM never emits IDs, the
harness assigns v84-N for top-level and v84-N.M (recursively) for
sub-tasks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml


# -----------------------------------------------------------------------------
# Literal-string dumper: any value wrapped in _Lit emits as `|` block scalar.
# Keeps the prose-heavy `task:` fields readable in core.yaml.
# -----------------------------------------------------------------------------

class _Lit(str):
    """Marker subclass so the YAML dumper renders this string with `|`."""


def _lit_repr(dumper, data):
    return dumper.represent_scalar(
        "tag:yaml.org,2002:str", data, style="|",
    )


yaml.add_representer(_Lit, _lit_repr, Dumper=yaml.SafeDumper)


# -----------------------------------------------------------------------------
# Path
# -----------------------------------------------------------------------------

def path(project_dir: Path) -> Path:
    return project_dir / "v84" / "core.yaml"


# -----------------------------------------------------------------------------
# Read / write
# -----------------------------------------------------------------------------

def read(project_dir: Path) -> dict:
    """Load core.yaml as a dict. Returns {} if missing."""
    p = path(project_dir)
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


_HEADER = (
    "# core.yaml — settled task list and iteration state.\n"
    "#\n"
    "# Source of truth for what this project is building. Each top-level\n"
    "# task has an id (v84-N matching the iteration tag) and a `task:`\n"
    "# prose body. Sub-tasks land under each task's `tasks:` field when\n"
    "# the plan stage runs at iteration time. The original brief was\n"
    "# deleted at settlement and is not consulted downstream.\n"
    "\n"
)


def write(project_dir: Path, data: dict) -> Path:
    """Render the dict as core.yaml and write it to disk.

    Recursively wraps every `task:` value in _Lit so the literal
    block-scalar style survives the round-trip — readable diffs,
    no escape soup.
    """
    out = path(project_dir)
    out.parent.mkdir(parents=True, exist_ok=True)

    rendered = {
        "tasks": [_render_task(t) for t in data.get("tasks", [])],
        "current_iteration": data.get("current_iteration"),
        "completed_iterations": data.get("completed_iterations") or [],
    }

    body = yaml.safe_dump(
        rendered,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=10000,
        indent=2,
    )
    out.write_text(_HEADER + body, encoding="utf-8")
    return out


def _render_task(t: dict) -> dict:
    """Prepare one task entry for safe_dump — wraps prose with _Lit, recurses."""
    rendered: dict = {"id": t.get("id", "")}
    rendered["task"] = _Lit((t.get("task") or "").strip())
    if t.get("tasks"):
        rendered["tasks"] = [_render_task(c) for c in t["tasks"]]
    return rendered


# -----------------------------------------------------------------------------
# ID assignment — harness-owned. The LLM never emits IDs.
# -----------------------------------------------------------------------------

def assign_top_level_ids(tasks: list[dict]) -> list[dict]:
    """Assign v84-1, v84-2, … to top-level tasks in listed order.

    Mutates each entry's `id` in place and returns the list.
    """
    for i, t in enumerate(tasks):
        t["id"] = f"v84-{i + 1}"
    return tasks


def assign_subtask_ids(parent_id: str, subtasks: list[dict]) -> list[dict]:
    """Assign <parent_id>.1, <parent_id>.2, … recursively.

    Mutates entries in place and returns the list.
    """
    for i, t in enumerate(subtasks):
        t["id"] = f"{parent_id}.{i + 1}"
        if t.get("tasks"):
            assign_subtask_ids(t["id"], t["tasks"])
    return subtasks


# -----------------------------------------------------------------------------
# Lookups
# -----------------------------------------------------------------------------

def next_unplanned(data: dict) -> Optional[dict]:
    """Return the first top-level task that hasn't been planned yet.

    "Planned" means the task has a non-empty `tasks:` list. This is
    used by the plan stage to pick the next iteration to work on.
    Returns None if every top-level task already has sub-tasks.
    """
    for t in data.get("tasks", []):
        if not t.get("tasks"):
            return t
    return None


def find_by_id(data: dict, task_id: str) -> Optional[dict]:
    """Recursive lookup of a task by id anywhere in the tree."""
    def walk(items):
        for t in items:
            if t.get("id") == task_id:
                return t
            child = t.get("tasks")
            if child:
                hit = walk(child)
                if hit is not None:
                    return hit
        return None
    return walk(data.get("tasks", []))
