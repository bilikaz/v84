"""
context.py — Prompt-context builders.

Reusable string-rendering helpers for the chunks every stage feeds
into its LLM call (roles, stack, tasks, etc.). Centralised so we
don't re-derive how to summarise these artefacts in every stage.

Each builder either reads a project file (profile.yaml, core.yaml)
directly or accepts a parsed structure, and returns a
single string ready to drop into a `user_msgs` list — usually
preceded by its own `## Heading` line by the caller.

Calls accept a `names` / `roles` filter so the same helper produces
both the full-spectrum block and a per-role narrowed view (used by
writers/reviewers when they only need their own slice).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from core.util import v84_docs_root


# -----------------------------------------------------------------------------
# profile.yaml — active roles list
# -----------------------------------------------------------------------------

def active_roles(profile_path: Path) -> list[str]:
    """Pull the project's roles list from profile.yaml.

    Reads the `roles:` key. The legacy `active_roles:` key is also
    accepted for projects initialised before the rename so old
    profile.yaml files keep working.
    """
    data = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    raw = data.get("roles") or data.get("active_roles") or []
    out: list[str] = []
    for entry in raw:
        if isinstance(entry, str):
            out.append(entry)
        elif isinstance(entry, dict) and isinstance(entry.get("name"), str):
            out.append(entry["name"])
    return out


# -----------------------------------------------------------------------------
# roles — title + role_tag + responsibilities, one block per role
# -----------------------------------------------------------------------------

def roles_block(
    project_dir: Path,
    names: Optional[list[str]] = None,
) -> str:
    """Render role responsibilities for a prompt.

    Reads each role's project-level copy from
    `<project_dir>/v84/structure/roles/<name>.yaml`. The project
    owns these copies — users can edit a role's responsibilities,
    reviewers, or charter and those edits flow into every
    downstream prompt.

    Output:

        ### Frontend
        role_tag: frontend

        <responsibilities prose>

    Roles separated by blank lines. Pass `names=None` (default) for
    every role file present under structure/roles/ (i.e. all active
    roles); pass a subset list for a narrowed view (a writer or
    reviewer that only needs its own slice).

    Note: this is the post-selection block — downstream stages need
    to know what each active role *does*. The pre-selection menu
    (used by suggest-roles) lives in `init.roles.build_role_menu`
    and emits `when_activate` instead.
    """
    roles_dir = project_dir / "v84" / "structure" / "roles"
    if names is None:
        names = sorted(f.stem for f in roles_dir.glob("*.yaml"))

    blocks: list[str] = []
    for name in names:
        role_file = roles_dir / f"{name}.yaml"
        if not role_file.exists():
            continue
        role = yaml.safe_load(role_file.read_text(encoding="utf-8")) or {}
        title = role.get("title", name)
        resp = (role.get("responsibilities") or "").strip()
        if resp:
            blocks.append(f"### {title}\nrole_tag: {name}\n\n{resp}")
        else:
            blocks.append(f"### {title}\nrole_tag: {name}")
    return "\n\n".join(blocks)


# -----------------------------------------------------------------------------
# stack — chosen tech picks, optionally filtered to a subset of roles
# -----------------------------------------------------------------------------

def stack_block(
    project_dir: Path,
    roles: Optional[list[str]] = None,
) -> str:
    """Render the project's stack picks as a Markdown block.

    Reads the `stack:` block from `<project_dir>/v84/profile.yaml`
    (the unified project config). Pairs each chosen value with the
    field's description from the source stack template
    (`v84-docs/init/stack/<role>.yaml`) so the consuming model
    understands what each field means, not just what was picked.
    Titles come from the project's role copies under
    `<project_dir>/v84/structure/roles/<role>.yaml`.

    Output shape (one section per role) — header matches roles_block:

        ### Backend
        role_tag: backend

        - **language**: `Python` — Primary language for server code.
        - **runtime**: `Python 3.12` — Process runtime + version.
        - **orm**: `none` — ORM or query builder ...

    Returns an empty string when no `stack:` block is present yet.
    Pass `roles` to filter to a subset of role sections.
    """
    profile_path = project_dir / "v84" / "profile.yaml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    stack_data = profile.get("stack") if isinstance(profile, dict) else None
    if not isinstance(stack_data, dict):
        return ""

    project_stack_dir = project_dir / "v84" / "structure" / "stack"
    fallback_stack_dir = v84_docs_root() / "init" / "stack"
    roles_dir = project_dir / "v84" / "structure" / "roles"
    out: list[str] = []

    for role, picks in stack_data.items():
        if roles is not None and role not in roles:
            continue
        if not isinstance(picks, dict):
            continue

        # Title + role_tag header, mirroring roles_block style.
        title = role
        role_file = roles_dir / f"{role}.yaml"
        if role_file.exists():
            r = yaml.safe_load(role_file.read_text(encoding="utf-8")) or {}
            title = r.get("title", role)

        # Field descriptions come from the project's pinned stack
        # template, with a fallback to the source for projects that
        # were initialised before stack templates started being copied.
        template: dict = {}
        stack_file = project_stack_dir / f"{role}.yaml"
        if not stack_file.exists():
            stack_file = fallback_stack_dir / f"{role}.yaml"
        if stack_file.exists():
            template = yaml.safe_load(stack_file.read_text(encoding="utf-8")) or {}

        if out:
            out.append("")
        out.append(f"### {title}")
        out.append(f"role_tag: {role}")
        out.append("")
        for field, value in picks.items():
            meta = template.get(field) or {}
            desc = (meta.get("description") or "").strip()
            value_str = str(value).strip() or "none"
            line = f"- **{field}**: `{value_str}`"
            if desc:
                line = f"{line} — {desc}"
            out.append(line)

    return "\n".join(out)


# -----------------------------------------------------------------------------
# Iteration plan — parent task + recursive sub-task tree, flat listing
# -----------------------------------------------------------------------------

def plan_block(parent: dict) -> str:
    """Render the iteration's parent task + nested tasks for a prompt.

    Walks the task tree to any depth. Hierarchy is encoded entirely
    in the dotted ids (`v84-2.2.2.1`) so the listing stays flat; no
    visual indentation. Used by every stage that needs to feed the
    iteration plan into an agent (writer, reviewer, lead, architect).

    Output:

        iteration_id: v84-1

        <parent prose>

        ### Sub-tasks

        task_id: v84-1.1
        <prose>
        task_id: v84-1.2
        <prose>
        task_id: v84-1.2.1
        <deeper prose>
    """
    lines = [
        f"iteration_id: {parent.get('id')}",
        "",
        (parent.get("task") or "").strip(),
    ]
    subtasks = parent.get("tasks") or []
    if subtasks:
        lines.append("")
        lines.append("### Sub-tasks")
        lines.append("")
        _walk_plan_subtasks(subtasks, lines)
    return "\n".join(lines)


def _walk_plan_subtasks(branch: list[dict], lines: list[str]) -> None:
    """Append each task flatly, recursing into nested `tasks:`."""
    for t in branch:
        prose = (t.get("task") or "").strip()
        lines.append(f"task_id: {t.get('id')}")
        if prose:
            lines.append(prose)
        children = t.get("tasks") or []
        if children:
            _walk_plan_subtasks(children, lines)


# -----------------------------------------------------------------------------
# Rules — single-file lists, role-scope filtered
# -----------------------------------------------------------------------------

def _load_records(p: Path) -> list[dict]:
    """Read a list of records from a YAML file. Empty if missing."""
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        return []
    return [r for r in data if isinstance(r, dict)]


def _current_iteration_n(project_dir: Path) -> Optional[int]:
    """Iteration number from core.yaml's `current_iteration`, or None."""
    p = project_dir / "v84" / "core.yaml"
    if not p.exists():
        return None
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return None
    parent_id = data.get("current_iteration")
    if not isinstance(parent_id, str):
        return None
    try:
        return int(parent_id.split(".")[0].split("-")[1])
    except (IndexError, ValueError):
        return None


def rules_block(
    project_dir: Path, role: Optional[str] = None,
) -> str:
    """Active rules in scope.

    A rule is by definition approved — root records carry no
    status (they're already user-promoted), and iteration records
    only count when status == accepted. The pending and rejected
    variants live in their own prefixed helpers.

    Sources:
        - v84/global.rules.yaml              (root, global)
        - v84/<role>.rules.yaml              (root, role-scoped)
        - iterations/<n>/global.rules.yaml   (status: accepted)
        - iterations/<n>/<role>.rules.yaml   (status: accepted)
    """
    return _render_records(
        _load_rules(project_dir, role, status="accepted")
    )


def pending_rules_block(
    project_dir: Path, role: Optional[str] = None,
) -> str:
    """Pending rules — current iteration only.

    Sources:
        - iterations/<n>/global.rules.yaml   (status: pending)
        - iterations/<n>/<role>.rules.yaml   (status: pending)
    """
    return _render_records(
        _load_rules(project_dir, role, status="pending")
    )


def rejected_rules_block(
    project_dir: Path, role: Optional[str] = None,
) -> str:
    """Rejected rules — current iteration only.

    Sources:
        - iterations/<n>/global.rules.yaml   (status: rejected)
        - iterations/<n>/<role>.rules.yaml   (status: rejected)
    """
    return _render_records(
        _load_rules(project_dir, role, status="rejected")
    )


def _load_rules(
    project_dir: Path,
    role: Optional[str],
    *,
    status: str,
) -> list[dict]:
    """Load rule records filtered to `status`
    ('accepted' | 'pending' | 'rejected').

    Root files (v84/global.rules.yaml + v84/<role>.rules.yaml) are
    treated as `accepted` (they're already user-approved at promotion
    time). Iteration files use their per-record `status` field.
    """
    out: list[dict] = []
    root = project_dir / "v84"

    if status == "accepted":
        out.extend(_load_records(root / "global.rules.yaml"))
        if role:
            out.extend(_load_records(root / f"{role}.rules.yaml"))

    cur = _current_iteration_n(project_dir)
    if cur is not None:
        iter_dir = root / "iterations" / str(cur)

        global_records = _load_records(iter_dir / "global.rules.yaml")
        out.extend(r for r in global_records if r.get("status") == status)

        if role:
            role_records = _load_records(iter_dir / f"{role}.rules.yaml")
            out.extend(r for r in role_records if r.get("status") == status)

    return out


# -----------------------------------------------------------------------------
# Corrections — round 2+ context for reviewers
# -----------------------------------------------------------------------------

def corrections_applied_block(project_dir: Path, role: str) -> str:
    """Corrections the patch stage applied in the previous round.

    Empty on round 1 (the file is created by patch). On round 2+
    every reader (any reviewer, lead) sees the full set so they
    can avoid re-raising what was already addressed. Ids encode
    source (reviewer / lead / architect) so the reader can tell.
    """
    cur = _current_iteration_n(project_dir)
    if cur is None:
        return ""
    p = (project_dir / "v84" / "iterations" / str(cur)
         / f"{role}.corrections-applied.yaml")
    return _render_corrections(_load_records(p))


def corrections_rejected_block(project_dir: Path, role: str) -> str:
    """Corrections that the lead or architect rejected.

    Round 2+ context — readers avoid re-raising what was already
    dismissed. All sources visible.
    """
    cur = _current_iteration_n(project_dir)
    if cur is None:
        return ""
    p = (project_dir / "v84" / "iterations" / str(cur)
         / f"{role}.corrections-rejected.yaml")
    return _render_corrections(_load_records(p), include_rejected_by=True)


def _render_corrections(
    records: list[dict], *, include_rejected_by: bool = False,
) -> str:
    """Render correction records as compact prose blocks."""
    if not records:
        return ""
    blocks: list[str] = []
    for r in records:
        rid = r.get("id", "?")
        verdict = r.get("verdict", "?")
        ref = r.get("action_id") or r.get("task_id") or "?"
        text = (r.get("correction") or "").strip()
        suffix = ""
        if include_rejected_by and r.get("rejected_by"):
            suffix = f"  (rejected by {r['rejected_by']})"
        blocks.append(f"### {rid}  {verdict} → {ref}{suffix}\n\n{text}")
    return "\n\n".join(blocks)


def _render_records(records: list[dict]) -> str:
    """Render a list of rule records as compact prose blocks.

    For accepted records: id + the rule text. For rejected records:
    id + the proposal text + the rejection reason (so downstream
    layers see WHY this was shot down without re-running the same
    idea). For pending records: id + the proposal text.
    """
    if not records:
        return ""
    blocks: list[str] = []
    for r in records:
        rid = r.get("id", "?")
        # `text` is the canonical field for the active rule text
        # (lead-set on accepted records, also used in main-folder
        # records). `proposal` is the fallback for pending or
        # rejected records (no `text` set).
        body = (r.get("text") or r.get("proposal") or "").strip()
        reason = (r.get("rejection_reason") or "").strip()
        if reason:
            body = f"{body}\n\n**rejected because:** {reason}"
        blocks.append(f"### {rid}\n\n{body}")
    return "\n\n".join(blocks)


# -----------------------------------------------------------------------------
# Role history — accumulated documentation across completed iterations
# -----------------------------------------------------------------------------

def role_history_block(project_dir: Path, role: str) -> str:
    """Render this role's accumulated implementation history.

    Reads <project>/v84/documentation/<role>.yaml — the per-role
    file that finish.py appends to on each successful iteration close.
    Returns empty string when no documentation exists yet (first
    iteration of the project, or this role hasn't shipped anything
    in any prior iteration).

    Output is a markdown block grouped by iteration → sub-task →
    actions, mirroring the on-disk YAML shape so the agent sees
    "what this role has built so far" in one digestible chunk.

    Used by writer/patch (so they don't redo work and respect prior
    decisions), reviewer (so they catch regressions or contradictions
    against past iterations), and lead (so verdicts stay consistent
    with what the role has previously committed to). Plan and
    architect skip this — they operate at a higher abstraction.
    """
    p = project_dir / "v84" / "documentation" / f"{role}.yaml"
    if not p.exists():
        return ""
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return ""
    iterations = data.get("iterations") or []
    if not iterations:
        return ""

    parts: list[str] = []
    for it in iterations:
        if not isinstance(it, dict):
            continue
        iter_id = it.get("id") or "?"
        iter_task = (it.get("task") or "").strip()
        parts.append(f"### Iteration {iter_id}")
        parts.append("")
        if iter_task:
            parts.append(iter_task)
            parts.append("")
        for sub in it.get("tasks") or []:
            if not isinstance(sub, dict):
                continue
            sub_id = sub.get("id") or "?"
            sub_task = (sub.get("task") or "").strip()
            parts.append(f"#### Task {sub_id}")
            if sub_task:
                parts.append("")
                parts.append(sub_task)
            for a in sub.get("actions") or []:
                if not isinstance(a, dict):
                    continue
                aid = a.get("id") or "?"
                files = ", ".join(a.get("files") or []) or "(none)"
                action = (a.get("action") or "").strip()
                parts.append("")
                parts.append(f"- **{aid}**  files: {files}")
                for line in action.splitlines():
                    parts.append(f"  {line}")
            parts.append("")
    return "\n".join(parts).rstrip()


# -----------------------------------------------------------------------------
# Cached wrappers — same blocks under iterations/<n>/cache/<name>.md
# -----------------------------------------------------------------------------
#
# Per-iteration disk cache. Same block (e.g. roles_block.frontend) gets
# rendered once per iteration and reused across draft / review / lead /
# patch calls. Source-file mtimes drive invalidation; cache filename is
# human-readable so `cat iterations/<n>/cache/roles_block.frontend.md`
# reveals what every stage sent for that block.

from core.cache import cached as _cached


def cached_roles_block(project_dir: Path, role: str, iter_dir: Path) -> str:
    """Cached roles_block for a single role."""
    return _cached(
        name=f"roles_block.{role}",
        sources=[project_dir / "v84" / "structure" / "roles" / f"{role}.yaml"],
        render=lambda: roles_block(project_dir, [role]),
        iter_dir=iter_dir,
    )


def cached_stack_block(project_dir: Path, role: str, iter_dir: Path) -> str:
    """Cached stack_block for a single role."""
    return _cached(
        name=f"stack_block.{role}",
        sources=[project_dir / "v84" / "structure" / "stack" / f"{role}.yaml"],
        render=lambda: stack_block(project_dir, roles=[role]),
        iter_dir=iter_dir,
    )


def cached_rules_block(
    project_dir: Path, role: Optional[str], iter_dir: Path,
) -> str:
    """Cached rules_block. Includes globals + role-scoped sources
    from both project root and the current iteration."""
    return _cached(
        name=f"rules_block.{role or 'global'}",
        sources=_rule_sources(project_dir, role),
        render=lambda: rules_block(project_dir, role=role),
        iter_dir=iter_dir,
    )


def cached_role_history_block(
    project_dir: Path, role: str, iter_dir: Path,
) -> str:
    """Cached role_history_block — reads documentation/<role>.yaml.
    The doc file may not exist yet on iteration 1; cache stores the
    empty render and returns it on subsequent calls."""
    return _cached(
        name=f"role_history_block.{role}",
        sources=[project_dir / "v84" / "documentation" / f"{role}.yaml"],
        render=lambda: role_history_block(project_dir, role),
        iter_dir=iter_dir,
    )


def _rule_sources(
    project_dir: Path, role: Optional[str],
) -> list[Path]:
    """Source files rules_block reads, in the same order as
    `_load_rules`. Iteration files are derived from the
    current_iteration in core.yaml."""
    root = project_dir / "v84"
    sources: list[Path] = [root / "global.rules.yaml"]
    if role:
        sources.append(root / f"{role}.rules.yaml")
    cur = _current_iteration_n(project_dir)
    if cur is not None:
        iter_dir = root / "iterations" / str(cur)
        sources.append(iter_dir / "global.rules.yaml")
        if role:
            sources.append(iter_dir / f"{role}.rules.yaml")
    return sources


# -----------------------------------------------------------------------------
# Layout — repo layout type + per-role section paths from profile.yaml
# -----------------------------------------------------------------------------

def layout_block(project_dir: Path, role: str) -> str:
    """Render the repo layout type + this role's named section
    paths. Set at init by the structure stage; lives in
    profile.yaml under `project.layout_type` and `layout.<role>`.

    Output format (markdown the agent reads):

        type: monorepo

        Your sections:

        - app          apps/web              — Next.js app root
        - pages        apps/web/src/pages    — App router pages
        - components   apps/web/src/components

        Place files under the appropriate section. Reference
        sections by name in your action prose; use the path in
        `files:` fields.

    Returns empty string when profile.yaml has no layout block
    (older project, or structure stage not yet run).
    """
    profile = project_dir / "v84" / "profile.yaml"
    if not profile.exists():
        return ""
    try:
        data = yaml.safe_load(profile.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return ""
    layout = data.get("layout") or {}
    if not isinstance(layout, dict):
        return ""
    sections = layout.get(role) or []
    layout_type = ((data.get("project") or {}).get("layout_type") or "").strip()

    if not sections and not layout_type:
        return ""

    parts: list[str] = []
    if layout_type:
        parts.append(f"type: {layout_type}")
        parts.append("")
    if sections:
        parts.append("Your sections:")
        parts.append("")
        # Pad columns so the path column aligns visually.
        name_w = max((len(s.get("name") or "") for s in sections), default=4)
        path_w = max((len(s.get("path") or "") for s in sections), default=4)
        for s in sections:
            if not isinstance(s, dict):
                continue
            name = (s.get("name") or "").ljust(name_w)
            path = (s.get("path") or "").ljust(path_w)
            notes = (s.get("notes") or "").strip().splitlines()
            head = f"- {name}  {path}"
            if notes:
                head += f"  — {notes[0]}"
            parts.append(head)
            for extra in notes[1:]:
                parts.append(" " * (len(head) - len(notes[0]) - 4) + extra)
        parts.append("")
        parts.append(
            "Place files under the appropriate section. Reference "
            "sections by name in your action prose; use the path in "
            "`files:` fields."
        )
    return "\n".join(parts).rstrip()


def cached_layout_block(project_dir: Path, role: str, iter_dir: Path) -> str:
    """Cached layout_block — reads profile.yaml. Same caching pattern
    as the other cached_X helpers."""
    return _cached(
        name=f"layout_block.{role}",
        sources=[project_dir / "v84" / "profile.yaml"],
        render=lambda: layout_block(project_dir, role),
        iter_dir=iter_dir,
    )


def project_layout_block(project_dir: Path) -> str:
    """Render layout_type + every active role's sections in one block.

    Used by stages that operate across roles (decompose for tasks
    that reference paths, handoff for the implementer's reference).
    Returns empty string when no layout block is set in profile.yaml.
    """
    profile = project_dir / "v84" / "profile.yaml"
    if not profile.exists():
        return ""
    try:
        data = yaml.safe_load(profile.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return ""
    layout = data.get("layout") or {}
    if not isinstance(layout, dict) or not layout:
        return ""
    layout_type = ((data.get("project") or {}).get("layout_type") or "").strip()

    parts: list[str] = []
    if layout_type:
        parts.append(f"type: {layout_type}")
        parts.append("")
    # `global` first when present (foundation), then everything else
    # in dict order.
    keys = list(layout.keys())
    if "global" in keys:
        keys.remove("global")
        keys = ["global"] + keys
    for role in keys:
        sections = layout.get(role) or []
        if not isinstance(sections, list):
            continue
        parts.append(f"### {role}")
        parts.append("")
        if not sections:
            parts.append("(no sections)")
            parts.append("")
            continue
        name_w = max((len(s.get("name") or "") for s in sections), default=4)
        path_w = max((len(s.get("path") or "") for s in sections), default=4)
        for s in sections:
            if not isinstance(s, dict):
                continue
            name = (s.get("name") or "").ljust(name_w)
            path = (s.get("path") or "").ljust(path_w)
            notes = (s.get("notes") or "").strip().splitlines()
            head = f"- {name}  {path}"
            if notes:
                head += f"  — {notes[0]}"
            parts.append(head)
        parts.append("")
    return "\n".join(parts).rstrip()


# -----------------------------------------------------------------------------
# Declarative user-message builder
# -----------------------------------------------------------------------------
#
# Each pipeline stage composes its prompt context as an ordered list of
# user messages. Instead of every stage re-implementing that composition
# by hand (one helper per block + manual append), each stage declares
# what it wants via a spec dict and calls `build_user_msgs`.
#
# Spec shape:
#   {
#     "<kind>": <scope>,
#     ...
#   }
#
# Order is preserved (Python 3.7+ dicts). Each entry produces zero or
# more user messages, in spec order. Empty data → block silently
# dropped (no header for an empty list).
#
# Scope semantics:
#   None / False / [] — block skipped (use this to make absences
#                       explicit in the spec — listing every known
#                       key with a value tells the reader exactly
#                       what each stage does and doesn't include)
#   True              — singleton block (e.g. plan, active_roles)
#   "all"             — every active role
#   ["global"]        — just the project-wide global scope (where
#                       supported: layout, rules, and their
#                       pending/rejected variants)
#   [role, ...]       — those roles
#   ["all", "global"] — every active role plus global
#   "<string>"        — for `trailing`: the literal final-line string
#

@dataclass
class _BuildCtx:
    project_dir: Path
    iter_dir: Path
    parent: dict
    iteration_n: int
    all_roles: list[str]
    role: Optional[str] = None  # focal role (writer, lead, reviewer)


_Builder = Callable[["_BuildCtx", Any], list[str]]


def build_user_msgs(
    project_dir: Path,
    parent: dict,
    iteration_n: int,
    spec: dict,
    *,
    role: Optional[str] = None,
) -> list[str]:
    """Compose the stage's user messages from a declarative spec.

    `role` is the focal role for per-role stages (writer, reviewer,
    lead, patch). Cross-role stages (architect) leave it None.
    """
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    profile_path = project_dir / "v84" / "profile.yaml"
    all_roles = active_roles(profile_path)

    ctx = _BuildCtx(
        project_dir=project_dir,
        iter_dir=iter_dir,
        parent=parent,
        iteration_n=iteration_n,
        all_roles=all_roles,
        role=role,
    )

    msgs: list[str] = []
    for kind, scope in spec.items():
        builder = _BUILDERS.get(kind)
        if builder is None:
            raise ValueError(
                f"build_user_msgs: unknown spec key {kind!r}. "
                f"Known keys: {sorted(_BUILDERS)}"
            )
        msgs.extend(builder(ctx, scope))
    return msgs


# ---------- scope resolution -------------------------------------------------

def _resolve_scope(
    scope: Any, all_roles: list[str], *, allow_global: bool = False,
) -> list[str]:
    """Turn a scope spec into a concrete list of role tags / 'global'.

    Items are de-duplicated, order preserved.
    """
    if scope == "all":
        return list(all_roles)
    if isinstance(scope, str):
        scope = [scope]
    if not isinstance(scope, list):
        return []
    out: list[str] = []
    for item in scope:
        if item == "all":
            out.extend(all_roles)
        elif item == "global":
            if allow_global:
                out.append("global")
            # else: silently drop — caller's domain doesn't have a global
        else:
            out.append(item)
    seen: set[str] = set()
    deduped: list[str] = []
    for s in out:
        if s not in seen:
            seen.add(s)
            deduped.append(s)
    return deduped


def _title(role: str) -> str:
    """Pretty-print a role tag for headers: 'frontend' → 'Frontend'."""
    return role.replace("-", " ").replace("_", " ").title()


def _dump_yaml(items: Any) -> str:
    return yaml.safe_dump(
        items,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=10000,
    ).rstrip()


# ---------- block builders ---------------------------------------------------

def _b_plan(ctx: _BuildCtx, scope: Any) -> list[str]:
    if not scope:
        return []
    return [f"## Iteration plan\n\n{plan_block(ctx.parent)}"]


def _b_active_roles(ctx: _BuildCtx, scope: Any) -> list[str]:
    if not scope:
        return []
    return [f"## Active roles\n\n{', '.join(ctx.all_roles)}"]


def _b_stack(ctx: _BuildCtx, scope: Any) -> list[str]:
    out: list[str] = []
    for role in _resolve_scope(scope, ctx.all_roles):
        block = cached_stack_block(ctx.project_dir, role, ctx.iter_dir).strip()
        if block:
            out.append(f"## {_title(role)} stack\n\n{block}")
    return out


def _b_layout(ctx: _BuildCtx, scope: Any) -> list[str]:
    out: list[str] = []
    for s in _resolve_scope(scope, ctx.all_roles, allow_global=True):
        if s == "global":
            block = project_layout_block(ctx.project_dir).strip()
            if block:
                out.append(f"## Repo layout (project)\n\n{block}")
        else:
            block = cached_layout_block(ctx.project_dir, s, ctx.iter_dir).strip()
            if block:
                out.append(f"## {_title(s)} repo layout\n\n{block}")
    return out


def _b_role_definition(ctx: _BuildCtx, scope: Any) -> list[str]:
    """Role definition (responsibilities) — for stages that need to know
    what each role owns (architect, lead)."""
    out: list[str] = []
    for role in _resolve_scope(scope, ctx.all_roles):
        block = cached_roles_block(ctx.project_dir, role, ctx.iter_dir).strip()
        if block:
            out.append(f"## {_title(role)} role\n\n{block}")
    return out


def _b_history(ctx: _BuildCtx, scope: Any) -> list[str]:
    out: list[str] = []
    for role in _resolve_scope(scope, ctx.all_roles):
        block = cached_role_history_block(
            ctx.project_dir, role, ctx.iter_dir,
        ).strip()
        if block:
            out.append(
                f"## {_title(role)} implementation history\n\n"
                f"What this role has shipped in past iterations. Build "
                f"on top, don't redo.\n\n{block}"
            )
    return out


def _b_actions(ctx: _BuildCtx, scope: Any) -> list[str]:
    """Writer's action list per role — `iterations/<n>/<role>.yaml`."""
    out: list[str] = []
    for role in _resolve_scope(scope, ctx.all_roles):
        f = ctx.iter_dir / f"{role}.yaml"
        if f.exists():
            text = f.read_text(encoding="utf-8").strip()
            if text:
                out.append(
                    f"## {_title(role)} writer draft\n\n"
                    f"```yaml\n{text}\n```"
                )
    return out


def _b_corrections(ctx: _BuildCtx, scope: Any) -> list[str]:
    """Lead's accepted corrections per role — `<role>.corrections.yaml`."""
    from core import proposals  # local import — proposals doesn't import context
    out: list[str] = []
    for role in _resolve_scope(scope, ctx.all_roles):
        recs = proposals.read_corrections(
            ctx.project_dir, ctx.iteration_n, role,
        )
        if recs:
            out.append(
                f"## {_title(role)} lead corrections\n\n"
                f"```yaml\n{_dump_yaml(recs)}\n```"
            )
    return out


def _b_corrections_rejected(ctx: _BuildCtx, scope: Any) -> list[str]:
    """Lead/architect rejected corrections — `<role>.corrections-rejected.yaml`."""
    from core import proposals
    out: list[str] = []
    for role in _resolve_scope(scope, ctx.all_roles):
        recs = proposals.read_rejected_corrections(
            ctx.project_dir, ctx.iteration_n, role,
        )
        if recs:
            out.append(
                f"## {_title(role)} rejected corrections\n\n"
                f"```yaml\n{_dump_yaml(recs)}\n```"
            )
    return out


def _b_corrections_applied(ctx: _BuildCtx, scope: Any) -> list[str]:
    """Patch-applied corrections per role (round 2+).

    All sources visible — every reader (any reviewer, lead) sees the
    full set; ids encode source so the reader can tell who raised
    what. Reviewers don't validate the patch; they just avoid
    re-raising what was already raised.
    """
    out: list[str] = []
    for role in _resolve_scope(scope, ctx.all_roles):
        block = corrections_applied_block(ctx.project_dir, role).strip()
        if block:
            out.append(
                f"## {_title(role)} corrections raised previously "
                f"(and applied)\n\n"
                f"Don't re-raise these — already raised in this iteration.\n\n"
                f"{block}"
            )
    return out


def _b_corrections_rejected_history(ctx: _BuildCtx, scope: Any) -> list[str]:
    """Round 2+ context: corrections rejected earlier this iteration.

    Distinct from `corrections_rejected` (current-round file dump) —
    this one is the prose-rendered accumulated history. All sources
    visible; ids encode who raised it.
    """
    out: list[str] = []
    for role in _resolve_scope(scope, ctx.all_roles):
        block = corrections_rejected_block(ctx.project_dir, role).strip()
        if block:
            out.append(
                f"## {_title(role)} corrections raised previously "
                f"(and rejected)\n\n"
                f"Don't re-raise these — already dismissed this iteration.\n\n"
                f"{block}"
            )
    return out


def _b_rules(ctx: _BuildCtx, scope: Any) -> list[str]:
    out: list[str] = []
    for s in _resolve_scope(scope, ctx.all_roles, allow_global=True):
        if s == "global":
            block = rules_block(ctx.project_dir, role=None).strip()
            if block:
                out.append(f"## Active global rules\n\n{block}")
        else:
            block = cached_rules_block(
                ctx.project_dir, s, ctx.iter_dir,
            ).strip()
            if block:
                out.append(
                    f"## {_title(s)} rules in scope\n\n{block}"
                )
    return out


def _b_rules_pending(ctx: _BuildCtx, scope: Any) -> list[str]:
    out: list[str] = []
    for s in _resolve_scope(scope, ctx.all_roles, allow_global=True):
        if s == "global":
            block = pending_rules_block(ctx.project_dir, role=None).strip()
            if block:
                out.append(f"## Pending global rules\n\n{block}")
        else:
            block = pending_rules_block(ctx.project_dir, role=s).strip()
            if block:
                out.append(
                    f"## {_title(s)} pending rule proposals\n\n{block}"
                )
    return out


def _b_rules_rejected(ctx: _BuildCtx, scope: Any) -> list[str]:
    out: list[str] = []
    for s in _resolve_scope(scope, ctx.all_roles, allow_global=True):
        block = rejected_rules_block(
            ctx.project_dir, role=None if s == "global" else s,
        ).strip()
        if block:
            label = "global" if s == "global" else _title(s)
            out.append(
                f"## {label} rules rejected this iteration\n\n"
                f"Don't re-propose without addressing the recorded reason.\n\n"
                f"{block}"
            )
    return out


def _b_corrections_pending(ctx: _BuildCtx, scope: Any) -> list[str]:
    """Pending corrections per role — the lead's verdict input.

    Reads `<role>.corrections-pending.yaml`: every correction
    targeting this role merged from all sources (every reviewer +
    architect), pre-verdict. Lead reads this whole list and
    accept/rejects each entry by id.
    """
    from core import proposals
    out: list[str] = []
    for role in _resolve_scope(scope, ctx.all_roles):
        pending = proposals.read_pending_corrections(
            ctx.project_dir, ctx.iteration_n, role,
        )
        if pending:
            out.append(
                f"## {_title(role)} pending corrections "
                f"({len(pending)})\n\n"
                f"```yaml\n{_dump_yaml(pending)}\n```"
            )
    return out


def _b_trailing(ctx: _BuildCtx, scope: Any) -> list[str]:
    """Final user-facing instruction line — typically a one-liner like
    'Synthesise across roles. Follow your output format exactly.'"""
    if isinstance(scope, str) and scope.strip():
        return [scope.strip()]
    return []


_BUILDERS: dict[str, _Builder] = {
    "plan":                          _b_plan,
    "active_roles":                  _b_active_roles,
    "stack":                         _b_stack,
    "layout":                        _b_layout,
    "role_definition":               _b_role_definition,
    "history":                       _b_history,
    "actions":                       _b_actions,
    "corrections":                   _b_corrections,
    "corrections_rejected":          _b_corrections_rejected,
    "corrections_applied":           _b_corrections_applied,
    "corrections_rejected_history":  _b_corrections_rejected_history,
    "rules":                         _b_rules,
    "rules_pending":                 _b_rules_pending,
    "rules_rejected":                _b_rules_rejected,
    "corrections_pending":           _b_corrections_pending,
    "trailing":                      _b_trailing,
}
