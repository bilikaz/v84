"""
decompose.py — Stage 3 of init: turn a brief into the settled task list.

Runs AFTER select_roles and suggest_stack so the LLM has the profile
and stack context to produce tasks that match the project's shape.

The user iterates with the LLM via the revise-with-comment loop until
they accept the plan. Acceptance is settlement — the brief becomes
irrelevant from this point on, and the task list (with revisions baked
in) is the authoritative description of what the project is building.

Input:
    <project>/v84/brief.md            the project brief
    <project>/v84/profile.yaml        roles + stack picks (unified)

Output:
    <project>/v84/core.yaml           settled task list + iteration state

The brief is deleted on acceptance — the task list supersedes it.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import json

from core import coreyaml
from core.context import active_roles, project_layout_block, roles_block, stack_block
from core.stage import Stage
from ui import detail_list, text_input
from core.util import default_log_dir, load_instruction
from llm import LLMConfig, call_json


# No tools exposed — when the user wants changes they revise via a
# free-text comment that the LLM consumes on the next round.


def decompose(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Decompose a project brief into a settled task list.

    Parameters
    ----------
    project_dir
        Path to the project root.
    brief
        Free-form project description.
    cfg
        Pre-resolved LLMConfig. Required (v84.py supplies it).

    Returns the path to the written core.yaml.
    """
    brief = brief.strip()
    if not brief:
        raise ValueError("brief is empty")

    system, schema = load_instruction("init", "decompose")

    # Compact context — only what the model needs to decompose. Full
    # profile.yaml carries llm/loop/execution config that's irrelevant
    # to tasks and just adds drift surface.
    v84_dir = project_dir / "v84"
    roles = active_roles(v84_dir / "profile.yaml")

    user_msgs = [
        f"## Project brief\n\n{brief}",
        f"## Active roles\n\n{roles_block(project_dir, roles)}",
        f"## Stack\n\n{stack_block(project_dir, roles)}",
    ]
    layout = project_layout_block(project_dir).strip()
    if layout:
        user_msgs.append(f"## Repo layout\n\n{layout}")
    user_msgs.append(
        "Decompose the brief into a proposed task list. Let the active\n"
        "roles, stack, and layout inform the granularity and flavour of\n"
        "the tasks (e.g. an active mobile role means mobile-specific\n"
        "tasks; a chosen framework shapes what the scaffold task covers;\n"
        "a monorepo layout means tasks reference apps/<name>/ paths,\n"
        "single-app means src/)."
    )

    if cfg is None:
        raise ValueError("LLMConfig required — call via v84.py or pass cfg=")

    # Initial proposal.
    response = _call_llm(cfg, system, schema, user_msgs, attempt=1)

    # Revision loop: user accepts, or feeds a comment back and the LLM
    # produces a new plan. The user never edits the YAML by hand —
    # they describe what to change and the model regenerates.
    attempt = 1
    while True:
        tasks = _parse_tasks(response)
        items = [
            {
                "label": f"{_assigned_id(i):<7} {_short(_task_text(t))}",
                "detail": _task_text(t),
            }
            for i, t in enumerate(tasks)
        ]
        choice = detail_list(
            items,
            actions=[
                {"name": "accept",
                 "label": "Accept this plan",
                 "info": "settle tasks into core.yaml and continue"},
                {"name": "revise",
                 "label": "Revise with a comment",
                 "info": "describe changes; AI regenerates"},
            ],
            prompt="Plan review:",
            summary=f"Proposed plan ({len(tasks)} tasks):",
        )
        if choice in (None, "accept"):
            break

        comment = text_input(
            prompt="Describe what to change:",
            summary=_summarize(response),
        )
        if not comment:
            # ESC or empty input → cancel the revision, ask again.
            continue

        attempt += 1
        revision_msgs = list(user_msgs) + [
            f"## Previous proposal\n\n```json\n{json.dumps(response, indent=2)}\n```",
            f"## User feedback\n\n{comment}",
            "Revise the task list based on the user's feedback. Adjust "
            "whatever the comment requests; leave the rest of the plan "
            "intact.",
        ]
        response = _call_llm(cfg, system, schema, revision_msgs, attempt=attempt)

    final_tasks = _parse_tasks(response)
    if not final_tasks:
        raise RuntimeError(
            "could not parse a tasks list from the final LLM response — "
            "check the latest init-decompose-r*.json log"
        )

    settled = coreyaml.assign_top_level_ids(
        [{"task": _task_text(t)} for t in final_tasks]
    )
    out_file = coreyaml.write(project_dir, {
        "tasks": settled,
        "current_iteration": None,
        "completed_iterations": [],
    })

    # Delete the brief — its purpose ended at acceptance. The task
    # list is now the source of truth; downstream stages should not
    # consult brief.md.
    brief_file = v84_dir / "brief.md"
    if brief_file.exists():
        brief_file.unlink()

    print(f"✓ wrote {out_file}", file=sys.stderr)
    return out_file


def _call_llm(cfg: LLMConfig, system: str, schema: dict,
              user_msgs: list[str], *, attempt: int) -> dict:
    """One round of decompose. Logged with attempt number for audit."""
    return call_json(
        cfg,
        system=system,
        user_msgs=user_msgs,
        response_schema=schema,
        log_name=f"init-decompose-r{attempt}",
        log_dir=default_log_dir(),
    )


def _parse_tasks(response: dict) -> list[dict]:
    """Pull the `tasks` list from the schema-validated response.

    Schema enforces shape upstream — this just unwraps and skips any
    rows the model still managed to produce malformed.
    """
    if not isinstance(response, dict):
        return []
    raw = response.get("tasks") or []
    return [t for t in raw if isinstance(t, dict)]


def _task_text(t: dict) -> str:
    """Extract the prose for a task entry.

    The current shape is `{task: <prose>}`. Earlier shapes used
    `{title, description}` — fall back to a joined form so a re-run
    against an old log doesn't crash.
    """
    if isinstance(t.get("task"), str):
        return t["task"].strip()
    title = (t.get("title") or "").strip()
    desc = (t.get("description") or "").strip()
    if title and desc:
        return f"{title}\n\n{desc}"
    return title or desc


def _assigned_id(index: int) -> str:
    """v84 tag assigned to a task by its 0-based index. Top-level only."""
    return f"v84-{index + 1}"


def _short(text: str, width: int = 80) -> str:
    """First line, truncated, for picker labels."""
    first = next((ln for ln in text.splitlines() if ln.strip()), "").strip()
    if len(first) > width:
        first = first[: width - 1].rstrip() + "…"
    return first


def _summarize(response: dict) -> str:
    """Human-readable summary of the proposed task list."""
    tasks = _parse_tasks(response)
    if not tasks:
        return "  (response carries no tasks)"

    lines = [f"Proposed plan ({len(tasks)} tasks):"]
    for i, t in enumerate(tasks):
        lines.append(f"  {_assigned_id(i):<7} {_short(_task_text(t))}")
    return "\n".join(lines)


# Stage metadata. Runs after roles and stack have produced their files.
STAGE = Stage(
    name="decompose",
    title="Decompose brief into tasks",
    priority=201,
    produces="core.yaml",
    requires=("roles", "stack", "structure"),
    needs_brief=True,
    call=decompose,
)
