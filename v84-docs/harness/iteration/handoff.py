"""
handoff.py — Render the iteration's tasks document for an external
implementer.

v84 produces the spec; another harness (Claude Code, Cursor, a
human, …) writes the actual code. This module bundles everything
that external implementer needs into one self-contained markdown
file at iterations/<n>/tasks.md:

    - The iteration's plan (what's being built and why)
    - Active rules in scope (project root globals + per-role)
    - Role definitions (what each role owns + boundaries)
    - The tagging convention (so produced code can be traced back
      to the action that requested it)
    - Every action, grouped by role, in dependency order

No LLM calls here — pure rendering. Called from user_review.py's
close path so the document lands on disk before the iteration is
finalised.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

from core import coreyaml
from core.context import (
    active_roles,
    plan_block,
    project_layout_block,
    roles_block,
    rules_block,
)


def write_handoff(project_dir: Path, iteration_n: int) -> Path:
    """Render iterations/<n>/tasks.md and return its path."""
    profile = project_dir / "v84" / "profile.yaml"
    roles = active_roles(profile)
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)

    # Look up parent by iteration number, not by `current_iteration`.
    # The task id of a top-level task is always `v84-<n>`, so we can
    # always find it whether the iteration is in-flight, just-closed,
    # or already completed.
    data = coreyaml.read(project_dir)
    parent = coreyaml.find_by_id(data, f"v84-{iteration_n}")

    parts: list[str] = [
        f"# Iteration {iteration_n} — implementation tasks",
        "",
        _intro_blurb(),
        "",
        "## Project root",
        "",
        _project_root_section(project_dir),
        "",
        "## Context",
        "",
        plan_block(parent) if parent else "(no plan available)",
        "",
        "## Roles in scope",
        "",
        roles_block(project_dir, roles).strip() or "(no roles)",
        "",
        "## Repo layout",
        "",
        project_layout_block(project_dir).strip() or "(no layout set)",
        "",
        "## Active rules",
        "",
        _rules_section(project_dir, roles),
        "",
        "## Tagging convention",
        "",
        _tagging_section(),
        "",
        "## Actions",
        "",
        _actions_section(iter_dir, roles, parent),
        "",
        "## Rules for the implementer",
        "",
        _implementer_rules(),
        "",
    ]

    out_path = iter_dir / "tasks.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="utf-8")
    print(
        f"  ✓ tasks document written → {out_path}",
        file=sys.stderr,
    )
    return out_path


# -----------------------------------------------------------------------------
# Section builders
# -----------------------------------------------------------------------------

def _intro_blurb() -> str:
    return (
        "> This file is the complete handoff for iteration "
        "implementation. v84 produced the rules, role split, and "
        "per-action plan; your job is to translate "
        "the actions below into actual code. Tag what you write so "
        "the produced source is traceable back to the action that "
        "requested it (see the tagging convention)."
    )


def _project_root_section(project_dir: Path) -> str:
    """Tell the implementer where to anchor all `files:` paths.

    Without this, agents that read tasks.md from inside
    `iterations/<n>/` tend to interpret paths like `index.html`
    relative to the doc's own directory, looking for files in
    `iterations/<n>/index.html` instead of `<project_root>/index.html`.
    """
    return (
        f"All `files:` paths in this document are relative to the "
        f"project root:\n"
        f"\n"
        f"```\n"
        f"{project_dir.resolve()}\n"
        f"```\n"
        f"\n"
        f"Resolve every entry as `<project root>/<files entry>`. "
        f"Do **not** interpret them relative to this `tasks.md` "
        f"file's own location under `v84/iterations/<n>/` — that "
        f"would point at the wrong directory. Existing files at the "
        f"project-root paths must be read first; missing ones are "
        f"created."
    )


def _rules_section(
    project_dir: Path, roles: list[str],
) -> str:
    """Globals first, then each role's section. Each entry: id + text."""
    parts: list[str] = []

    globals_text = rules_block(project_dir, role=None).strip()
    if globals_text:
        parts.append("### Global")
        parts.append("")
        parts.append(globals_text)
        parts.append("")

    for role in roles:
        # `rules_block(role=...)` would return globals + role merged.
        # We want only the role-scoped slice here, so read the root
        # role file directly.
        role_text = _render_role_rules(project_dir, role)
        if role_text:
            parts.append(f"### {role.capitalize()}")
            parts.append("")
            parts.append(role_text)
            parts.append("")

    if not parts:
        return "(none)"
    return "\n".join(parts).rstrip()


def _render_role_rules(project_dir: Path, role: str) -> str:
    """Render only the role-scoped rules from the project root file."""
    p = project_dir / "v84" / f"{role}.rules.yaml"
    if not p.exists():
        return ""
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        return ""
    blocks: list[str] = []
    for r in data:
        if not isinstance(r, dict):
            continue
        rid = r.get("id", "?")
        text = (r.get("text") or "").strip()
        if text:
            blocks.append(f"### {rid}\n\n{text}")
    return "\n\n".join(blocks)


def _tagging_section() -> str:
    return (
        "When writing or editing source, tag the produced block with "
        "the action id that requested it. Place the tag as a comment "
        "directly above the function / class / config block, in the "
        "syntax of the language:\n"
        "\n"
        "```typescript\n"
        "// [v84-1.1.frontend.1]\n"
        "function pageShell() { ... }\n"
        "```\n"
        "\n"
        "```yaml\n"
        "# [v84-1.3.devops.1]\n"
        "services:\n"
        "  api:\n"
        "    build: ./api.Dockerfile\n"
        "```\n"
        "\n"
        "Rules:\n"
        "- Tag every distinct block (function, class, component, "
        "config block) with the action id that produced it.\n"
        "- Aggregator files (barrels like `index.ts`, composed pages "
        "that re-export many things) get **one tag at the top of the "
        "file**, picked from the earliest action that touches them. "
        "Don't sprinkle per-line tags through aggregators.\n"
        "- Tag format is exactly `[v84-N.M.role.K]` — the dotted id "
        "of the action that's responsible. Greppable with "
        "`grep -r '\\[v84-1\\.1\\.frontend' .`."
    )


def _actions_section(iter_dir: Path, roles: list[str], parent: Any) -> str:
    """Render every role's actions, grouped by parent task. Within a
    role, actions are listed in the order the writer/patch emitted
    them (already topologically reasonable since writers respect
    plan order and `depends:`)."""
    parts: list[str] = []
    for role in roles:
        actions = _read_actions(iter_dir / f"{role}.yaml")
        if not actions:
            continue
        parts.append(f"### Role: {role}")
        parts.append("")
        # Group by task_id prefix so the implementer sees actions
        # under their owning sub-task.
        by_task = _group_by_task(actions)
        for task_id, group in by_task:
            task_title = _task_title(parent, task_id) if parent else ""
            heading = f"#### Task `{task_id}`"
            if task_title:
                heading += f" — {task_title}"
            parts.append(heading)
            parts.append("")
            for a in group:
                parts.append(_render_action(a))
                parts.append("")
        parts.append("")
    if not parts:
        return "(no actions on disk for this iteration — check "\
               "iterations/<n>/<role>.yaml files)"
    return "\n".join(parts).rstrip()


def _render_action(a: dict) -> str:
    aid = a.get("id", "?")
    files = a.get("files") or []
    depends = a.get("depends") or []
    action = (a.get("action") or "").strip()
    verify_lines = _verify_lines(a.get("verify"))

    lines = [f"- **{aid}**"]
    if files:
        lines.append(f"  - files: {', '.join(files)}")
    if depends:
        lines.append(f"  - depends: {', '.join(depends)}")
    lines.append("")
    # Indent the prose so it nests under the bullet visually.
    for prose_line in action.splitlines():
        lines.append(f"  {prose_line}")
    # Inline verify rows directly under the action so the implementer
    # reads observable assertions in the same context as the action's
    # prose. Separating them into a back-of-doc section drops the
    # context that ties each assertion to the change that produces it.
    if verify_lines:
        lines.append("")
        lines.append("  Verify:")
        for ln in verify_lines:
            lines.append(f"    - {ln}")
    return "\n".join(lines)


_SENTENCE_TERMINATORS = (".", "!", "?")


def _verify_lines(raw: Any) -> list[str]:
    """Normalise an action's `verify:` field to a list of assertions.

    Tolerant of YAML list shape (each item is one assertion) and
    block-scalar string shape. For strings: an assertion ends at a
    sentence terminator (`.`, `!`, `?`) or a blank line. Lines that
    don't end with a terminator are joined to the next line — writers
    line-wrap long assertions and we shouldn't bullet each wrap as
    its own row.

    Falls back to per-line splitting when no terminator is found
    anywhere (the writer is using bullet-style fragments without
    periods)."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [s for s in (str(item).strip() for item in raw) if s]
    if not isinstance(raw, str):
        return []

    text = raw.replace("\r\n", "\n")
    # If no terminator anywhere, treat each non-empty line as its own
    # assertion (writer is using fragment-style listing).
    if not any(ch in text for ch in _SENTENCE_TERMINATORS):
        return [ln.strip() for ln in text.splitlines() if ln.strip()]

    out: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        ln = line.strip()
        if not ln:
            if current:
                out.append(" ".join(current))
                current = []
            continue
        current.append(ln)
        if ln.endswith(_SENTENCE_TERMINATORS):
            out.append(" ".join(current))
            current = []
    if current:
        out.append(" ".join(current))
    return out


def _implementer_rules() -> str:
    return (
        "- Apply only the actions listed above. Do not invent extra "
        "work beyond what the actions request.\n"
        "- Do not modify files outside each action's `files:` list. "
        "Cross-file effects are the writer's responsibility — they "
        "decompose into multiple actions.\n"
        "- Honour every active rule. They are "
        "binding: if your implementation would violate one, surface "
        "the conflict back to v84 (next iteration can refine the "
        "rule) rather than silently breaking the rule.\n"
        "- Respect `depends:` — a dependency must be implemented "
        "(and tagged) before its dependents.\n"
        "- Aggregator files get one tag at the top, not per-line. "
        "Standalone blocks (functions, classes, config blocks) get "
        "their own tag.\n"
        "- If an action is ambiguous, prefer the most faithful "
        "interpretation of the action prose plus the rules in scope. "
        "Don't improvise or polish."
    )


# -----------------------------------------------------------------------------
# Per-role action helpers
# -----------------------------------------------------------------------------

def _read_actions(p: Path) -> list[dict]:
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return []
    actions = data.get("actions") or []
    return [a for a in actions if isinstance(a, dict)]


def _group_by_task(actions: list[dict]) -> list[tuple[str, list[dict]]]:
    """Return [(task_id, [actions])] preserving first-seen order.
    The action id is `<task_id>.<role>.<n>`, so task_id is the id
    minus the last two segments (role + index)."""
    grouped: dict[str, list[dict]] = {}
    order: list[str] = []
    for a in actions:
        aid = a.get("id") or ""
        parts = aid.split(".")
        # `<task_id>.<role>.<n>` → task_id = first len-2 segments
        task_id = ".".join(parts[:-2]) if len(parts) >= 3 else aid
        if task_id not in grouped:
            grouped[task_id] = []
            order.append(task_id)
        grouped[task_id].append(a)
    return [(tid, grouped[tid]) for tid in order]


def _task_title(parent: Any, task_id: str) -> str:
    """Return the first prose line of the task with `task_id` from
    the parent's task tree, or empty string if not found."""
    if not isinstance(parent, dict):
        return ""
    found = _find_task(parent, task_id)
    if found is None:
        return ""
    prose = (found.get("task") or "").strip().splitlines()
    return prose[0] if prose else ""


def _find_task(parent: dict, task_id: str) -> Any:
    if parent.get("id") == task_id:
        return parent
    for sub in parent.get("tasks") or []:
        if not isinstance(sub, dict):
            continue
        hit = _find_task(sub, task_id)
        if hit is not None:
            return hit
    return None
