"""
documentation.py — Append finished iteration to per-role docs.

Called from finish.py after verification passes and before
_close_iteration. For each active role, appends the iteration's
parent task + the sub-tasks where the role had actions + the
actions themselves into <project>/documentation/<role>.yaml.

Sub-tasks where the role had zero actions are omitted, so each
role's file stays focused on its own contributions. The full
parent task prose IS duplicated across roles' files — each
role's documentation is meant to be self-contained.

Resulting shape:

    iterations:
      - id: v84-1
        task: |
          <parent task prose>
        tasks:
          - id: v84-1.1
            task: |
              <sub-task prose>
            actions:
              - id: v84-1.1.frontend.1
                action: |
                  <action prose>
                files:
                  - index.html
                depends: []
          - id: v84-1.2
            task: |
              ...
            actions:
              - ...
      - id: v84-2
        ...
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

import yaml

from core import coreyaml


def append_iteration(
    project_dir: Path, iteration_n: int, roles: list[str],
) -> list[Path]:
    """Append the iteration's per-role actions to each role's
    documentation file. Returns the list of files written."""
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    parent = coreyaml.find_by_id(coreyaml.read(project_dir), f"v84-{iteration_n}")
    if parent is None:
        # Shouldn't happen at finish-time, but bail safely.
        return []

    written: list[Path] = []
    for role in roles:
        actions = _read_role_actions(iter_dir / f"{role}.yaml")
        if not actions:
            continue
        entry = _build_iteration_entry(
            parent=parent,
            iteration_n=iteration_n,
            role_actions=actions,
        )
        if not entry["tasks"]:
            # Role had actions but none mapped to recognisable tasks —
            # skip rather than write an empty entry.
            continue
        path = _append_entry(project_dir, role, entry)
        written.append(path)
        print(
            f"  ✓ v84/documentation/{role}.yaml +iteration {iteration_n} "
            f"({sum(len(t['actions']) for t in entry['tasks'])} action(s) "
            f"across {len(entry['tasks'])} task(s))",
            file=sys.stderr,
        )
    return written


# -----------------------------------------------------------------------------
# Build the per-iteration entry for one role
# -----------------------------------------------------------------------------

def _build_iteration_entry(
    *,
    parent: dict,
    iteration_n: int,
    role_actions: list[dict],
) -> dict:
    """One {id, task, tasks: [...]} entry for one iteration of one role.

    Walks the role's actions, groups them by their owning sub-task,
    and pairs each group with the sub-task's prose. Sub-tasks the
    role didn't touch are omitted entirely."""
    grouped, order = _group_by_task(role_actions)

    sub_entries: list[dict] = []
    for task_id in order:
        sub_task = _find_task(parent, task_id)
        sub_prose = (sub_task.get("task") or "").strip() if sub_task else ""
        sub_entries.append({
            "id": task_id,
            "task": sub_prose,
            "actions": [_normalise_action(a) for a in grouped[task_id]],
        })

    return {
        "id": parent.get("id") or f"v84-{iteration_n}",
        "task": (parent.get("task") or "").strip(),
        "tasks": sub_entries,
    }


def _normalise_action(a: dict) -> dict:
    """Strip the action down to the fields documentation cares about,
    in a stable key order. Drops empty `depends`."""
    out: dict[str, Any] = {
        "id": a.get("id"),
        "action": (a.get("action") or "").strip(),
        "files": list(a.get("files") or []),
    }
    depends = a.get("depends") or []
    if depends:
        out["depends"] = list(depends)
    return out


def _group_by_task(
    actions: list[dict],
) -> tuple[dict[str, list[dict]], list[str]]:
    """Return ({task_id: [actions]}, [task_id in first-seen order]).

    Action id format `<task_id>.<role_tag>.<n>` — task_id is the
    first len-2 segments. Falls back to the bare action id if the
    shape doesn't match (defensive)."""
    grouped: dict[str, list[dict]] = {}
    order: list[str] = []
    for a in actions:
        aid = a.get("id") or ""
        parts = aid.split(".")
        task_id = ".".join(parts[:-2]) if len(parts) >= 3 else aid
        if task_id not in grouped:
            grouped[task_id] = []
            order.append(task_id)
        grouped[task_id].append(a)
    return grouped, order


def _find_task(parent: dict, task_id: str) -> Optional[dict]:
    """Recursive lookup of a task by id starting from `parent`."""
    if not isinstance(parent, dict):
        return None
    if parent.get("id") == task_id:
        return parent
    for sub in parent.get("tasks") or []:
        if not isinstance(sub, dict):
            continue
        hit = _find_task(sub, task_id)
        if hit is not None:
            return hit
    return None


# -----------------------------------------------------------------------------
# Per-role file IO — append to documentation/<role>.yaml
# -----------------------------------------------------------------------------

def _append_entry(project_dir: Path, role: str, entry: dict) -> Path:
    """Append `entry` to documentation/<role>.yaml under `iterations:`.

    De-dup by entry id — if an iteration was already documented (e.g.
    finish re-ran after a previous successful pass), replace the old
    entry rather than duplicating."""
    docs_dir = project_dir / "v84" / "documentation"
    docs_dir.mkdir(parents=True, exist_ok=True)
    path = docs_dir / f"{role}.yaml"

    data = _read_doc_file(path)
    iterations = data.get("iterations") or []

    # Replace existing entry with the same id, else append.
    replaced = False
    for i, existing in enumerate(iterations):
        if isinstance(existing, dict) and existing.get("id") == entry["id"]:
            iterations[i] = entry
            replaced = True
            break
    if not replaced:
        iterations.append(entry)

    data["iterations"] = iterations
    path.write_text(_dump(data), encoding="utf-8")
    return path


def _read_doc_file(p: Path) -> dict:
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _read_role_actions(p: Path) -> list[dict]:
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return []
    return [a for a in (data.get("actions") or []) if isinstance(a, dict)]


def _dump(data: Any) -> str:
    return yaml.safe_dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=10000,
    )
