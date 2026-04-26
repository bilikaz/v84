"""
plan.py — Iteration plan stage.

Pick the next un-planned top-level task from core.yaml and decompose
it into sub-tasks for this iteration's cycle. The agent emits one of
two shapes:

    Shape A: TASKS      — recursive list of sub-tasks
    Shape B: QUESTIONS  — clarifying questions with suggestions

QUESTIONS are answered via field_editor (each question is a field
with the agent's suggestions as alternatives), then re-fed to the
agent which then emits TASKS. TASKS go through the same accept /
revise-with-comment loop decompose uses.

On accept:
    - sub-tasks are assigned ids (v84-N.M, v84-N.M.K, …) and
      inserted under the parent's `tasks:` field in core.yaml
    - core.yaml's `current_iteration` is set to the parent id
    - iterations/<n>/plan.yaml is written with the iteration number,
      the parent id, and any Q&A from clarification rounds
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

import yaml

from core import coreyaml, iter_status
from core.context import active_roles, roles_block, stack_block
from core.stage import Stage
from core.util import default_log_dir, instruction_path
from llm import LLMConfig, call
from ui import Spinner, detail_list, field_editor, text_input


def plan(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Plan the next un-planned top-level task. Returns plan.yaml path."""
    if cfg is None:
        raise ValueError("LLMConfig required — call via v84.py or pass cfg=")

    data = coreyaml.read(project_dir)
    parent = coreyaml.next_unplanned(data)
    if parent is None:
        raise RuntimeError(
            "no top-level task left to plan — every task already has sub-tasks."
        )

    parent_id = parent["id"]
    iteration_n = _iteration_number(parent_id)

    skill_file = instruction_path("iteration", "plan.md")
    if not skill_file.exists():
        raise FileNotFoundError(f"Instruction not found: {skill_file}")
    system = skill_file.read_text(encoding="utf-8")

    # Stable context — same across every round of this plan call.
    profile_path = project_dir / "v84" / "profile.yaml"
    roles = active_roles(profile_path)
    past_plans = _collect_past_plans(project_dir, iteration_n)

    base_msgs: list[str] = [
        f"## Parent task\n\nid: {parent_id}\n\n{parent['task'].strip()}",
        f"## Active roles\n\n{roles_block(project_dir, roles)}",
        f"## Stack\n\n{stack_block(project_dir, roles)}",
    ]
    if past_plans:
        base_msgs.append(f"## Past iteration plans\n\n{past_plans}")

    qa: list[dict] = []
    attempt = 1
    response = _call_llm(
        cfg, system,
        base_msgs + ["Plan this iteration. Follow your output format exactly."],
        attempt=attempt,
    )

    while True:
        parsed = _parse_response(response)

        if parsed["kind"] == "questions":
            answers = _ask_questions(parsed["questions"], parent)
            if answers is None:
                raise RuntimeError("plan cancelled at clarification step")
            for q, a in zip(parsed["questions"], answers):
                qa.append({"question": q["question"], "answer": a})

            attempt += 1
            response = _call_llm(
                cfg, system,
                base_msgs + [
                    f"## Clarifications\n\n{_qa_block(qa)}",
                    "Now produce sub-tasks (Shape A). Follow your output format.",
                ],
                attempt=attempt,
            )
            continue

        tasks = parsed["tasks"]
        if not tasks:
            raise RuntimeError(
                "agent returned neither tasks nor questions — "
                "check the latest iter-plan-r*.json log"
            )

        choice = _review_tasks(tasks, parent)
        if choice in (None, "accept"):
            break

        comment = text_input(
            prompt="Describe what to change:",
            summary=_summarize_tasks(tasks, parent_id),
        )
        if not comment:
            continue

        attempt += 1
        revision = list(base_msgs)
        if qa:
            revision.append(f"## Clarifications\n\n{_qa_block(qa)}")
        revision.append(f"## Previous proposal\n\n```yaml\n{response}\n```")
        revision.append(f"## User feedback\n\n{comment}")
        revision.append(
            "Revise the sub-task list per the user's feedback. Keep the "
            "same output format. Adjust whatever the comment requests; "
            "leave the rest of the plan intact."
        )
        response = _call_llm(cfg, system, revision, attempt=attempt)

    # Accept path — assign ids, persist core.yaml + plan.yaml.
    coreyaml.assign_subtask_ids(parent_id, tasks)
    parent["tasks"] = tasks
    data["current_iteration"] = parent_id
    coreyaml.write(project_dir, data)

    plan_file = _write_plan_yaml(project_dir, iteration_n, parent_id, qa)

    # Initialise the iteration's status — round 1, draft is up next.
    iter_status.write(project_dir, iteration_n, round=1, next_step="draft")

    print(f"✓ wrote sub-tasks under {parent_id} in core.yaml", file=sys.stderr)
    print(f"✓ wrote {plan_file}", file=sys.stderr)
    return plan_file


# -----------------------------------------------------------------------------
# LLM call wrapper
# -----------------------------------------------------------------------------

def _call_llm(cfg: LLMConfig, system: str, user_msgs: list[str],
              *, attempt: int) -> str:
    with Spinner(f"calling {cfg.model} @ {cfg.url}"):
        return call(
            cfg,
            system=system,
            user_msgs=user_msgs,
            log_name=f"iter-plan-r{attempt}",
            log_dir=default_log_dir(),
        )


# -----------------------------------------------------------------------------
# Parsing — detect TASKS vs QUESTIONS
# -----------------------------------------------------------------------------

def _parse_response(yaml_text: str) -> dict:
    """Return {'kind': 'tasks'|'questions', ...}.

    Tasks shape carries a normalised recursive list under 'tasks'.
    Questions shape carries a list of {question, suggestions} dicts.
    """
    try:
        data = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError:
        return {"kind": "tasks", "tasks": []}
    if not isinstance(data, dict):
        return {"kind": "tasks", "tasks": []}

    if isinstance(data.get("questions"), list):
        out: list[dict] = []
        for q in data["questions"]:
            if not isinstance(q, dict):
                continue
            qtext = q.get("question")
            if not isinstance(qtext, str) or not qtext.strip():
                continue
            sugs = q.get("suggestions") or []
            sug_list = [s.strip() for s in sugs if isinstance(s, str) and s.strip()]
            out.append({"question": qtext.strip(), "suggestions": sug_list})
        if out:
            return {"kind": "questions", "questions": out}

    raw_tasks = data.get("tasks") or []
    return {"kind": "tasks", "tasks": _normalize_tasks(raw_tasks)}


def _normalize_tasks(raw: Any) -> list[dict]:
    """Recursive normalisation: strip prose, keep `tasks:` recursion."""
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for t in raw:
        if not isinstance(t, dict):
            continue
        prose = (t.get("task") or "").strip()
        if not prose:
            continue
        entry: dict = {"task": prose}
        children = _normalize_tasks(t.get("tasks"))
        if children:
            entry["tasks"] = children
        out.append(entry)
    return out


# -----------------------------------------------------------------------------
# UI: ask questions via field_editor
# -----------------------------------------------------------------------------

def _ask_questions(questions: list[dict], parent: dict) -> Optional[list[str]]:
    """Render each question as a field_editor row.

    Returns the list of selected answers (one per question), or None
    if the user cancels with ESC.
    """
    fields: list[dict] = []
    for q in questions:
        sugs = q.get("suggestions") or []
        first = sugs[0] if sugs else ""
        fields.append({
            "label": q["question"],
            "value": first,
            "recommendation": first,
            "alternatives": sugs[1:] if len(sugs) > 1 else [],
            "optional": False,
        })

    sections = [{
        "title": f"Plan clarifications — {parent['id']}",
        "fields": fields,
    }]
    result = field_editor(
        sections,
        prompt=f"Answer planning questions for {parent['id']}:",
        summary=_short(parent["task"], width=120),
    )
    if result is None:
        return None
    return [str(f.get("value") or "") for f in result[0]["fields"]]


# -----------------------------------------------------------------------------
# UI: review the proposed sub-task list (accept / revise)
# -----------------------------------------------------------------------------

def _review_tasks(tasks: list[dict], parent: dict) -> Optional[str]:
    """Flat detail_list of the proposed sub-tasks, with depth indentation."""
    items: list[dict] = []
    parent_id = parent["id"]

    def walk(branch: list[dict], prefix: str, depth: int) -> None:
        for i, t in enumerate(branch):
            tid = f"{prefix}.{i + 1}"
            indent = "  " * depth
            items.append({
                "label": f"{indent}{tid:<10} {_short(t['task'])}",
                "detail": t["task"],
            })
            if t.get("tasks"):
                walk(t["tasks"], tid, depth + 1)

    walk(tasks, parent_id, 0)

    return detail_list(
        items,
        actions=[
            {"name": "accept",
             "label": "Accept this plan",
             "info": f"settle sub-tasks under {parent_id} in core.yaml"},
            {"name": "revise",
             "label": "Revise with a comment",
             "info": "describe changes; AI regenerates"},
        ],
        prompt=f"Iteration plan for {parent_id}:",
        summary=f"Parent: {_short(parent['task'])}",
    )


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _iteration_number(task_id: str) -> int:
    """v84-3 → 3. v84-3.1 → 3 (top-level only). Raises on bad shape."""
    head = task_id.split(".")[0]
    return int(head.split("-")[1])


def _collect_past_plans(project_dir: Path, current_n: int) -> str:
    """Concatenate every prior iterations/<n>/plan.yaml in numeric order."""
    iters = project_dir / "v84" / "iterations"
    if not iters.exists():
        return ""
    nums: list[int] = []
    for p in iters.iterdir():
        if not p.is_dir() or not p.name.isdigit():
            continue
        n = int(p.name)
        if n < current_n:
            nums.append(n)
    nums.sort()

    chunks: list[str] = []
    for n in nums:
        plan_file = iters / str(n) / "plan.yaml"
        if not plan_file.exists():
            continue
        chunks.append(f"### Iteration {n}\n\n{plan_file.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(chunks)


def _qa_block(qa: list[dict]) -> str:
    return "\n".join(f"Q: {x['question']}\nA: {x['answer']}\n" for x in qa)


def _write_plan_yaml(project_dir: Path, n: int,
                     parent_id: str, qa: list[dict]) -> Path:
    iters = project_dir / "v84" / "iterations" / str(n)
    iters.mkdir(parents=True, exist_ok=True)
    out = iters / "plan.yaml"
    body = {
        "iteration": n,
        "parent": parent_id,
        "qa": qa or [],
    }
    out.write_text(
        yaml.safe_dump(
            body,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=10000,
        ),
        encoding="utf-8",
    )
    return out


def _short(text: str, width: int = 80) -> str:
    """First non-empty line, truncated, for picker labels."""
    first = next((ln for ln in text.splitlines() if ln.strip()), "").strip()
    if len(first) > width:
        first = first[: width - 1].rstrip() + "…"
    return first


def _summarize_tasks(tasks: list[dict], parent_id: str) -> str:
    """Flat summary used by text_input painter."""
    lines = [f"Proposed sub-tasks ({_count_tasks(tasks)}):"]
    def walk(branch: list[dict], prefix: str, depth: int) -> None:
        for i, t in enumerate(branch):
            tid = f"{prefix}.{i + 1}"
            indent = "  " * depth
            lines.append(f"  {indent}{tid:<10} {_short(t['task'])}")
            if t.get("tasks"):
                walk(t["tasks"], tid, depth + 1)
    walk(tasks, parent_id, 0)
    return "\n".join(lines)


def _count_tasks(tasks: list[dict]) -> int:
    n = 0
    for t in tasks:
        n += 1
        if t.get("tasks"):
            n += _count_tasks(t["tasks"])
    return n


# -----------------------------------------------------------------------------
# Stage metadata
# -----------------------------------------------------------------------------

def _is_done(project_dir: Path) -> bool:
    """Plan is done for the current iteration when core.yaml's
    `current_iteration` is set. Future cycle-close clears it to
    advance; for now plan is one-shot per project run."""
    data = coreyaml.read(project_dir)
    return data.get("current_iteration") is not None


STAGE = Stage(
    name="plan",
    title="Plan iteration sub-tasks",
    priority=1001,
    produces="iterations/<n>/plan.yaml",
    requires=("decompose",),
    needs_brief=False,
    is_done=_is_done,
    call=plan,
)
