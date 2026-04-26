"""
draft.py — Iteration draft stage (round 1, parallel writers).

Once `current_iteration` is set in core.yaml (plan stage done),
fan one writer call out per active role. Each writer drafts the
concrete tasks for their role given the iteration's sub-task plan.

Per-role output lands at `iterations/<n>/<role>.yaml`. The stage is
done when every active role has produced its file. Fan-out
concurrency follows the multi tier's `max_concurrency` (falls back
to single tier when multi isn't configured).

Reviewer / lead / architect layers come in later phases.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

import yaml

from core import coreyaml, iter_status, proposals
from core.context import (
    active_roles,
    cached_conventions_block,
    cached_decisions_block,
    cached_layout_block,
    cached_role_history_block,
    cached_roles_block,
    cached_stack_block,
    plan_block,
)
from core.stage import Stage
from core.util import default_log_dir, instruction_path
from llm import CallSpec, LLMConfig, call_many, resolve_llm
from ui import MultiSpinner


def draft(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Run round-1 drafts for every active role in parallel."""
    if cfg is None:
        raise ValueError("LLMConfig required — call via v84.py or pass cfg=")

    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        raise RuntimeError(
            "no current_iteration set in core.yaml — run the plan stage first"
        )

    parent = coreyaml.find_by_id(data, parent_id)
    if parent is None:
        raise RuntimeError(f"current_iteration {parent_id!r} not found in core.yaml")

    iteration_n = _iteration_number(parent_id)
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    iter_dir.mkdir(parents=True, exist_ok=True)

    profile_path = project_dir / "v84" / "profile.yaml"
    roles = active_roles(profile_path)
    if not roles:
        raise RuntimeError("no active roles in profile.yaml")

    # Fan-out tier: prefer multi when available, else use single.
    fan_cfg = _fan_out_cfg(project_dir, fallback=cfg)

    # Skip roles whose draft already exists — supports resume after
    # interrupt without paying for completed roles again.
    pending_roles = [
        r for r in roles
        if not (iter_dir / f"{r}.yaml").exists()
    ]
    if not pending_roles:
        print(f"✓ all role drafts already present in {iter_dir}",
              file=sys.stderr)
        return iter_dir

    skill_file = instruction_path("iteration", "draft.md")
    if not skill_file.exists():
        raise FileNotFoundError(f"Instruction not found: {skill_file}")
    system = skill_file.read_text(encoding="utf-8")

    plan = plan_block(parent)

    specs: list[CallSpec] = []
    for role in pending_roles:
        msgs = _build_user_msgs(
            project_dir=project_dir,
            role=role,
            plan=plan,
            iter_dir=iter_dir,
        )
        specs.append(CallSpec(
            system=system,
            user_msgs=msgs,
            log_name=f"iter-{iteration_n}-draft-{role}",
        ))

    workers = min(fan_cfg.max_concurrency, len(specs))
    print(f"  drafting {len(specs)} role(s) — model {fan_cfg.model} "
          f"@ {fan_cfg.url} (workers: {workers})",
          file=sys.stderr)
    with MultiSpinner(pending_roles) as ms:
        results = call_many(
            fan_cfg, specs,
            log_dir=default_log_dir(),
            progress=ms,
        )

    # Persist each role's output. A failure for one role records the
    # error but keeps successful drafts on disk.
    failed: list[tuple[str, str]] = []
    for spec, role, result in zip(specs, pending_roles, results):
        if result.error is not None:
            failed.append((role, repr(result.error)))
            continue
        parsed = _parse(result.response or "")
        out_file = iter_dir / f"{role}.yaml"
        out_file.write_text(_render_role_output(parsed), encoding="utf-8")
        print(f"  ✓ {out_file}", file=sys.stderr)

        # Extract proposals from the writer's response and seed the
        # iteration's role-scoped conv/dec stores. Draft is the first
        # stage to touch these files, so we write fresh — review will
        # append later. Ids are harness-assigned per emit order.
        conv_records = proposals.to_pending_records(
            parsed.get("needs_convention"),
            id_prefix=f"v84-{iteration_n}.{role}.conv",
        )
        proposals.write_conventions(project_dir, iteration_n, role, conv_records)

        dec_records = proposals.to_pending_records(
            parsed.get("needs_decision"),
            id_prefix=f"v84-{iteration_n}.{role}.dec",
        )
        proposals.write_decisions(project_dir, iteration_n, role, dec_records)

    if failed:
        for role, err in failed:
            print(f"  ✗ {role}: {err}", file=sys.stderr)
        raise RuntimeError(
            f"{len(failed)} role draft(s) failed — re-run to retry"
        )

    iter_status.advance_to(project_dir, iteration_n, "review")
    return iter_dir


# -----------------------------------------------------------------------------
# Per-role context builder
# -----------------------------------------------------------------------------

def _build_user_msgs(
    *,
    project_dir: Path,
    role: str,
    plan: str,
    iter_dir: Path,
) -> list[str]:
    """Multi-message context for one writer call.

    Skips empty blocks entirely (no "(none)" placeholders) so the
    model isn't trained to handle noise messages.

    Cached blocks (roles/stack/conv/dec/history) read once per
    iteration and reuse across stages — see core.cache.
    """
    msgs: list[str] = [
        f"## Iteration plan\n\n{plan}",
        f"## Your role\n\n{cached_roles_block(project_dir, role, iter_dir)}",
    ]

    stack = cached_stack_block(project_dir, role, iter_dir).strip()
    if stack:
        msgs.append(f"## Your stack\n\n{stack}")

    layout = cached_layout_block(project_dir, role, iter_dir).strip()
    if layout:
        msgs.append(f"## Your repo layout\n\n{layout}")

    conv = cached_conventions_block(project_dir, role, iter_dir).strip()
    if conv:
        msgs.append(f"## Conventions in scope\n\n{conv}")

    dec = cached_decisions_block(project_dir, role, iter_dir).strip()
    if dec:
        msgs.append(f"## Decisions in scope\n\n{dec}")

    history = cached_role_history_block(project_dir, role, iter_dir).strip()
    if history:
        msgs.append(
            f"## Your role's implementation history\n\n"
            f"Actions this role has shipped in past iterations. Treat "
            f"as the current state of your role's surface — don't redo "
            f"what's already implemented; build on top of it.\n\n"
            f"{history}"
        )

    msgs.append(
        "Draft the concrete actions for this iteration. "
        "Follow your output format exactly."
    )
    return msgs


# -----------------------------------------------------------------------------
# Output normalisation + persistence
# -----------------------------------------------------------------------------

def _render_role_output(parsed: dict) -> str:
    """Render the writer's actions list as the on-disk shape.

    The writer owns its own ids in the form `<task_id>.<role>.<n>`;
    the parent task is encoded in the id itself, so no separate
    `task_id` field is kept. The filename already encodes the role
    so no top-level `role:` key is written. Conv/dec proposals are
    persisted separately by the caller into the iteration's role-
    scoped pending stores; they don't appear here.
    """
    actions = parsed.get("actions", [])
    ordered: list[dict] = []
    for a in actions:
        entry: dict[str, Any] = {}
        if a.get("id"):
            entry["id"] = a["id"]
        entry["action"] = a["action"]
        if a.get("files"):
            entry["files"] = a["files"]
        if a.get("depends"):
            entry["depends"] = a["depends"]
        ordered.append(entry)

    return yaml.safe_dump(
        {"actions": ordered},
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=10000,
    )


def _parse(yaml_text: str) -> dict:
    """Permissive parse of the writer response. Empty dict on failure.

    Accepts the legacy `tasks:` / per-item `task:` shape too — older
    instruction phrasings emitted those keys. Internally normalised
    to `actions:` / `action:` for the harness.
    """
    try:
        data = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError:
        return {}
    if not isinstance(data, dict):
        return {}

    raw_actions = data.get("actions") or data.get("tasks") or []
    actions: list[dict] = []
    for a in raw_actions:
        if not isinstance(a, dict):
            continue
        prose = (a.get("action") or a.get("task") or "").strip()
        if not prose:
            continue
        entry: dict[str, Any] = {"action": prose}
        aid = a.get("id")
        if isinstance(aid, str) and aid.strip():
            entry["id"] = aid.strip()
        files = a.get("files")
        if isinstance(files, list):
            entry["files"] = [str(f).strip() for f in files if f]
        depends = a.get("depends")
        if isinstance(depends, list):
            entry["depends"] = [str(d).strip() for d in depends if d]
        actions.append(entry)

    out: dict[str, Any] = {"actions": actions}

    out["needs_convention"] = _parse_proposals(
        data.get("needs_convention"))
    out["needs_decision"] = _parse_proposals(
        data.get("needs_decision"))
    if not out["needs_convention"]:
        del out["needs_convention"]
    if not out["needs_decision"]:
        del out["needs_decision"]

    return out


def _parse_proposals(raw: Any) -> list[dict]:
    """Normalise needs_convention / needs_decision entries.

    Both share the {id, proposal, alternatives} shape; alternatives
    is a list of strings. Entries with no proposal text are skipped.
    """
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        proposal = str(r.get("proposal") or "").strip()
        if not proposal:
            continue
        entry: dict[str, Any] = {}
        rid = r.get("id")
        if isinstance(rid, str) and rid.strip():
            entry["id"] = rid.strip()
        entry["proposal"] = proposal
        alts = r.get("alternatives")
        if isinstance(alts, list):
            cleaned = [str(a).strip() for a in alts if str(a).strip()]
            if cleaned:
                entry["alternatives"] = cleaned
        out.append(entry)
    return out


# -----------------------------------------------------------------------------
# Fan-out tier resolution
# -----------------------------------------------------------------------------

def _fan_out_cfg(project_dir: Path, *, fallback: LLMConfig) -> LLMConfig:
    """Use the multi tier if configured; else stay on the resolved single."""
    try:
        return resolve_llm(
            project_dir=project_dir, tier="multi",
            interactive=False,
        )
    except RuntimeError:
        return fallback


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _iteration_number(task_id: str) -> int:
    """v84-3 → 3. v84-3.1 → 3."""
    return int(task_id.split(".")[0].split("-")[1])


# -----------------------------------------------------------------------------
# Stage metadata
# -----------------------------------------------------------------------------

def _is_done(project_dir: Path) -> bool:
    """Done when status.yaml says next_step has moved past `draft`."""
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        return False
    iteration_n = _iteration_number(parent_id)
    return iter_status.stage_is_done(project_dir, iteration_n, "draft")


STAGE = Stage(
    name="draft",
    title="Draft per-role iteration tasks",
    priority=1101,
    produces="iterations/<n>/<role>.yaml",
    requires=("plan",),
    needs_brief=False,
    is_done=_is_done,
    call=draft,
)
