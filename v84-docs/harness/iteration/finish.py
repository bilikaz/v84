"""
finish.py — Iteration verification + close gate.

Runs after user_review has promoted rules and written
iterations/<n>/tasks.md. The user takes that handoff to an
external implementer (Claude Code, Cursor, a human, …) which
writes the actual code. When the user comes back to v84 and hits
Start, this stage fires.

Job:
    1. Read every action across every active role
       (`iterations/<n>/<role>.yaml`).
    2. For each action, check that every path in `files:` exists
       under the project root.
    3. If any file is missing → write `iterations/<n>/fix.md`
       listing the gaps (action id + file + the action prose).
       Status stays at next_step=finish so the next Start re-checks.
    4. If everything exists → delete any stale fix.md, close the
       iteration (move parent_id from current_iteration to
       completed_iterations, advance next_step → done).

Verification rule (per file):
    A file PASSES if it exists AND its body contains at least one
    tag of any action that lists it. This naturally handles the
    aggregator pattern from tasks.md (a file shared by multiple
    actions only needs ONE related tag — the earliest / primary
    action's tag covers all the others).

Two failure modes per action's file:
    - missing  : file does not exist on disk
    - untagged : file exists, but no `[<related_action_id>]` is
                 present in its body

Both land in fix.md grouped by action, so the external implementer
gets a directed punch list without needing to cross-reference
tasks.md.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

import yaml

from core import coreyaml, iter_status
from core.context import active_roles
from core.stage import Stage
from iteration.documentation import append_iteration as append_documentation


def finish(
    project_dir: Path,
    brief: str,
    *,
    cfg: Any = None,
) -> Path:
    """Verify implementation against the action plan; close on pass."""
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        raise RuntimeError(
            "no current_iteration in core.yaml — finish needs an "
            "in-flight iteration"
        )
    iteration_n = _iteration_number(parent_id)

    profile = project_dir / "v84" / "profile.yaml"
    roles = active_roles(profile)
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)

    # Collect every action across roles; build file → owner-set map
    # so the aggregator pattern works (a file passes if ANY owning
    # action's tag is present).
    all_actions: list[tuple[str, dict]] = []  # (role, action)
    for role in roles:
        for a in _read_actions(iter_dir / f"{role}.yaml"):
            all_actions.append((role, a))
    actions_checked = len(all_actions)

    file_owners: dict[str, set[str]] = {}     # file path → action ids
    for _role, a in all_actions:
        aid = a.get("id")
        if not aid:
            continue
        for f in (a.get("files") or []):
            file_owners.setdefault(f, set()).add(aid)

    # Cache the existence + tag-status check once per file.
    file_status: dict[str, str] = {}   # "ok" | "missing" | "untagged"
    for f, owners in file_owners.items():
        target = project_dir / f
        if not target.exists():
            file_status[f] = "missing"
            continue
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            file_status[f] = "missing"
            continue
        if any(f"[{aid}]" in content for aid in owners):
            file_status[f] = "ok"
        else:
            file_status[f] = "untagged"

    # Per-action gap collection: emit one entry per (action, failed
    # file) so the implementer sees what to do under each action id.
    gaps: list[dict] = []
    for role, a in all_actions:
        for rel_path in (a.get("files") or []):
            status = file_status.get(rel_path)
            if status == "ok":
                continue
            gaps.append({
                "role": role,
                "action_id": a.get("id", "?"),
                "file": rel_path,
                "kind": status or "missing",
                "owners": sorted(file_owners.get(rel_path, set())),
                "action_prose": (a.get("action") or "").strip(),
            })

    fix_file = iter_dir / "fix.md"

    if gaps:
        _write_fix_doc(
            fix_file, iteration_n, gaps, actions_checked,
            project_dir=project_dir,
        )
        n_missing = sum(1 for g in gaps if g["kind"] == "missing")
        n_untagged = sum(1 for g in gaps if g["kind"] == "untagged")
        print(
            f"  ✗ verification failed — {n_missing} missing file(s), "
            f"{n_untagged} untagged file(s) across "
            f"{len(set(g['action_id'] for g in gaps))} action(s). "
            f"See {fix_file}",
            file=sys.stderr,
        )
        # Stay at next_step=finish so the next Start re-checks.
        iter_status.advance_to(project_dir, iteration_n, "finish")
        return fix_file

    # Pristine — drop any stale fix.md, append this iteration's
    # actions to per-role documentation, then close the iteration.
    if fix_file.exists():
        fix_file.unlink()
    append_documentation(project_dir, iteration_n, roles)
    _close_iteration(project_dir, iteration_n, parent_id)
    print(
        f"  ✓ verification passed — {actions_checked} action(s) "
        f"covered. iteration {iteration_n} closed.",
        file=sys.stderr,
    )
    return iter_dir


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _read_actions(p: Path) -> list[dict]:
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return []
    return [a for a in (data.get("actions") or []) if isinstance(a, dict)]


def _write_fix_doc(
    p: Path, iteration_n: int, gaps: list[dict], actions_checked: int,
    *, project_dir: Path,
) -> None:
    """Render a directed punch list of gaps for the external implementer."""
    n_missing = sum(1 for g in gaps if g["kind"] == "missing")
    n_untagged = sum(1 for g in gaps if g["kind"] == "untagged")
    n_actions = len(set(g["action_id"] for g in gaps))

    parts: list[str] = [
        f"# Iteration {iteration_n} — fix list",
        "",
        f"> Verification of `tasks.md` found {n_missing} missing file(s) "
        f"and {n_untagged} untagged file(s) across {n_actions} action(s) "
        f"(of {actions_checked} actions checked). Address each entry "
        f"below, then re-run v84 — the next pass will re-check and "
        f"either close the iteration or update this list.",
        "",
        "## Project root",
        "",
        f"All file paths below are relative to the project root:\n"
        f"\n"
        f"```\n"
        f"{project_dir.resolve()}\n"
        f"```\n"
        f"\n"
        f"Resolve every entry as `<project root>/<file>` — same anchor "
        f"as `tasks.md` uses. Do not interpret paths relative to this "
        f"`fix.md` file's own location.",
        "",
        "## What \"untagged\" means",
        "",
        "A file marked **untagged** exists on disk but has no "
        "`[v84-N.M.role.K]` tag from any action that lists it. The "
        "tag is what ties the file back to the action that requested "
        "it; verification can't pass without one. The aggregator "
        "rule still applies — for a file shared by several actions, "
        "ONE tag at the top from any owning action covers all of "
        "them.",
        "",
        "## Gaps grouped by action",
        "",
    ]

    # Group by action_id, preserving first-seen order.
    by_action: dict[str, list[dict]] = {}
    order: list[str] = []
    for g in gaps:
        aid = g["action_id"]
        if aid not in by_action:
            by_action[aid] = []
            order.append(aid)
        by_action[aid].append(g)

    for aid in order:
        group = by_action[aid]
        role = group[0]["role"]
        prose = group[0]["action_prose"]
        parts.append(f"### {aid}  ({role})")
        parts.append("")
        missing = [g for g in group if g["kind"] == "missing"]
        untagged = [g for g in group if g["kind"] == "untagged"]
        if missing:
            parts.append("**Missing files (create them):**")
            for g in missing:
                parts.append(f"- `{g['file']}`")
            parts.append("")
        if untagged:
            parts.append("**Files exist but no tag from any owning action:**")
            for g in untagged:
                owners = ", ".join(f"`[{o}]`" for o in g["owners"])
                parts.append(f"- `{g['file']}` — expected one of: {owners}")
            parts.append("")
        parts.append("**Action prose:**")
        parts.append("")
        for line in prose.splitlines():
            parts.append(f"> {line}")
        parts.append("")

    parts.append("## Rules for the next pass")
    parts.append("")
    parts.append(
        "- Address every entry above. Each missing file must exist "
        "after the next pass; each untagged file must contain a "
        "`[v84-N.M.role.K]` tag from one of its owning actions.\n"
        "- Honour the original tagging convention from `tasks.md` — "
        "tag every produced block; aggregator files get one tag at "
        "the top.\n"
        "- Do not invent new actions. The actions in `tasks.md` are "
        "the complete set; this list only flags coverage gaps in "
        "that set.\n"
        "- If a file genuinely cannot or should not be created (e.g. "
        "the action turned out to be obsolete after another action "
        "subsumed it), edit `tasks.md` to remove the action and "
        "rerun v84 to regenerate this list."
    )

    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(parts), encoding="utf-8")


def _close_iteration(project_dir: Path, iteration_n: int, parent_id: str) -> None:
    """Move parent_id from current_iteration to completed_iterations,
    advance status next_step → done. Same shape as user_review used
    to do; finish now owns the actual close."""
    data = coreyaml.read(project_dir)
    completed = list(data.get("completed_iterations") or [])
    if parent_id not in completed:
        completed.append(parent_id)
    data["completed_iterations"] = completed
    data["current_iteration"] = None
    coreyaml.write(project_dir, data)
    iter_status.advance_to(project_dir, iteration_n, "done")


def _iteration_number(task_id: str) -> int:
    return int(task_id.split(".")[0].split("-")[1])


# -----------------------------------------------------------------------------
# Stage glue
# -----------------------------------------------------------------------------

def _is_done(project_dir: Path) -> bool:
    """Done when status.yaml says next_step has moved past `finish`
    (i.e. iteration was successfully closed)."""
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        return True   # iteration already closed
    iteration_n = _iteration_number(parent_id)
    return iter_status.stage_is_done(project_dir, iteration_n, "finish")


STAGE = Stage(
    name="finish",
    title="Verify implementation; close iteration when complete",
    priority=1500,
    produces="iterations/<n>/status.yaml#next_step=done",
    requires=("user_review",),
    needs_brief=False,
    is_done=_is_done,
    call=finish,
)
