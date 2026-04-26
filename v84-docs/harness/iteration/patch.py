"""
patch.py — Round 2+ writer (applies corrections).

Replaces draft as the round opener in round 2 and beyond. Each
role's writer reads its existing draft + the corrections that
landed on its punch list and emits a patched actions list. After
persisting the new draft, applied corrections move to
`<role>.corrections-applied.yaml` so the next round's reviewers
can verify what was honored.

Same fan-out shape as draft: one call per active role, parallel
via the multi tier when configured.
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

# Reuse draft's parser + renderer — patch emits the same actions /
# needs_convention / needs_decision shape, harness handles ids the
# same way. Only the per-role context (existing draft + corrections)
# differs, plus the post-success corrections-applied move.
from .draft import _parse, _render_role_output


def patch(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Run patched drafts for every active role in parallel."""
    if cfg is None:
        raise ValueError("LLMConfig required — call via v84.py or pass cfg=")

    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        raise RuntimeError(
            "no current_iteration set in core.yaml — run plan + cycle first"
        )

    parent = coreyaml.find_by_id(data, parent_id)
    if parent is None:
        raise RuntimeError(f"current_iteration {parent_id!r} not found")

    iteration_n = _iteration_number(parent_id)
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    iter_dir.mkdir(parents=True, exist_ok=True)

    profile_path = project_dir / "v84" / "profile.yaml"
    roles = active_roles(profile_path)
    if not roles:
        raise RuntimeError("no active roles in profile.yaml")

    fan_cfg = _fan_out_cfg(project_dir, fallback=cfg)

    # Skip roles whose corrections list is empty — there's nothing
    # for that role's writer to apply, the existing draft stands.
    pending_roles: list[str] = []
    for role in roles:
        corrections = proposals.read_corrections(project_dir, iteration_n, role)
        if corrections:
            pending_roles.append(role)
        else:
            print(
                f"  ↷ {role}: no pending corrections — draft unchanged",
                file=sys.stderr,
            )
    if not pending_roles:
        print("  ✓ all role drafts already current — nothing to patch",
              file=sys.stderr)
        iter_status.advance_to(project_dir, iteration_n, "review")
        return iter_dir

    skill_file = instruction_path("iteration", "patch.md")
    if not skill_file.exists():
        raise FileNotFoundError(f"Instruction not found: {skill_file}")
    system = skill_file.read_text(encoding="utf-8")

    plan = plan_block(parent)

    specs: list[CallSpec] = []
    for role in pending_roles:
        msgs = _build_user_msgs(
            project_dir=project_dir,
            role=role,
            iteration_n=iteration_n,
            plan=plan,
        )
        specs.append(CallSpec(
            system=system,
            user_msgs=msgs,
            log_name=f"iter-{iteration_n}-r"
                     f"{iter_status.read(project_dir, iteration_n).get('round', '?')}"
                     f"-patch-{role}",
        ))

    workers = min(fan_cfg.max_concurrency, len(specs))
    print(f"  patching {len(specs)} role(s) — model {fan_cfg.model} "
          f"@ {fan_cfg.url} (workers: {workers})",
          file=sys.stderr)
    with MultiSpinner(pending_roles) as ms:
        results = call_many(
            fan_cfg, specs,
            log_dir=default_log_dir(),
            progress=ms,
        )

    failed: list[tuple[str, str]] = []
    for spec, role, result in zip(specs, pending_roles, results):
        if result.error is not None:
            failed.append((role, repr(result.error)))
            continue

        parsed = _parse(result.response or "")
        out_file = iter_dir / f"{role}.yaml"
        out_file.write_text(_render_role_output(parsed), encoding="utf-8")
        print(f"  ✓ {out_file} (patched)", file=sys.stderr)

        # Move applied corrections to the audit file so the next
        # round's reviewers can verify what was honored.
        applied = proposals.read_corrections(project_dir, iteration_n, role)
        existing_archive = _read_corrections_applied(project_dir, iteration_n, role)
        _write_corrections_applied(
            project_dir, iteration_n, role,
            existing_archive + applied,
        )
        proposals.write_corrections(project_dir, iteration_n, role, [])
        print(
            f"  ✓ {role}.corrections-applied.yaml +{len(applied)} "
            f"(corrections.yaml cleared)",
            file=sys.stderr,
        )

        # Round-2+ patch may still surface fresh conv/dec proposals.
        # Use the same prefix as the round-1 writer and continue the
        # numbering past existing entries so ids don't collide.
        conv_prefix = f"v84-{iteration_n}.{role}.conv"
        existing_conv = proposals.read_conventions(project_dir, iteration_n, role)
        new_conv = proposals.to_pending_records(
            parsed.get("needs_convention"),
            id_prefix=conv_prefix,
            start_n=proposals.next_index_for_prefix(existing_conv, conv_prefix),
        )
        if new_conv:
            proposals.write_conventions(
                project_dir, iteration_n, role,
                proposals.append_pending(existing_conv, new_conv),
            )
        dec_prefix = f"v84-{iteration_n}.{role}.dec"
        existing_dec = proposals.read_decisions(project_dir, iteration_n, role)
        new_dec = proposals.to_pending_records(
            parsed.get("needs_decision"),
            id_prefix=dec_prefix,
            start_n=proposals.next_index_for_prefix(existing_dec, dec_prefix),
        )
        if new_dec:
            proposals.write_decisions(
                project_dir, iteration_n, role,
                proposals.append_pending(existing_dec, new_dec),
            )

    if failed:
        for role, err in failed:
            print(f"  ✗ {role}: {err}", file=sys.stderr)
        raise RuntimeError(
            f"{len(failed)} role patch(es) failed — re-run to retry"
        )

    iter_status.advance_to(project_dir, iteration_n, "review")
    return iter_dir


# -----------------------------------------------------------------------------
# Per-role context builder — same shape as draft, plus draft + corrections
# -----------------------------------------------------------------------------

def _build_user_msgs(
    *,
    project_dir: Path,
    role: str,
    iteration_n: int,
    plan: str,
) -> list[str]:
    """Multi-message context for one patch call. Cached blocks
    (roles/stack/conv/dec/history) read once per iteration and
    reuse across stages — see core.cache."""
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)

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

    # The current round's draft + corrections — patch's distinct inputs.
    draft_file = iter_dir / f"{role}.yaml"
    if draft_file.exists():
        msgs.append(
            f"## Your existing draft (this iteration)\n\n"
            f"```yaml\n{draft_file.read_text(encoding='utf-8').strip()}\n```"
        )
    corrections = proposals.read_corrections(project_dir, iteration_n, role)
    msgs.append(
        f"## Corrections to apply ({len(corrections)})\n\n"
        f"```yaml\n{_dump(corrections).rstrip()}\n```"
    )

    msgs.append(
        "Apply every correction to your existing draft and emit the "
        "patched actions list. Follow your output format exactly."
    )
    return msgs


def _dump(data: Any) -> str:
    return yaml.safe_dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=10000,
    )


# -----------------------------------------------------------------------------
# corrections-applied audit file
# -----------------------------------------------------------------------------

def _corrections_applied_path(project_dir: Path, n: int, role: str) -> Path:
    return (
        project_dir / "v84" / "iterations" / str(n)
        / f"{role}.corrections-applied.yaml"
    )


def _read_corrections_applied(
    project_dir: Path, n: int, role: str,
) -> list[dict]:
    p = _corrections_applied_path(project_dir, n, role)
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    return [r for r in data if isinstance(r, dict)]


def _write_corrections_applied(
    project_dir: Path, n: int, role: str, records: list[dict],
) -> Path:
    p = _corrections_applied_path(project_dir, n, role)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_dump(records), encoding="utf-8")
    return p




# -----------------------------------------------------------------------------
# Fan-out tier + helpers
# -----------------------------------------------------------------------------

def _fan_out_cfg(project_dir: Path, *, fallback: LLMConfig) -> LLMConfig:
    try:
        return resolve_llm(
            project_dir=project_dir, tier="multi",
            interactive=False,
        )
    except RuntimeError:
        return fallback


def _iteration_number(task_id: str) -> int:
    return int(task_id.split(".")[0].split("-")[1])


# -----------------------------------------------------------------------------
# Stage metadata
# -----------------------------------------------------------------------------

def _is_done(project_dir: Path) -> bool:
    """Done when status.yaml says next_step has moved past `patch`."""
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        return False
    iteration_n = _iteration_number(parent_id)
    return iter_status.stage_is_done(project_dir, iteration_n, "patch")


STAGE = Stage(
    name="patch",
    title="Patch per-role drafts (round 2+ opener)",
    priority=1403,
    produces="iterations/<n>/<role>.yaml (patched)",
    requires=("validate",),
    needs_brief=False,
    is_done=_is_done,
    call=patch,
)
