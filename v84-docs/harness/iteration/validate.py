"""
validate.py — Iteration cycle-end decider.

Runs after the architect. Two jobs:

    1. Cross-lead validation of architect's pending global proposals.
       For each pending global in iterations/<n>/global.{conventions,
       decisions}.yaml (status: pending), fan out one parallel call
       per active role-lead. Each lead votes accept/reject from its
       role's perspective. Single-veto rule: any reject → status:
       rejected with rejection_reason recorded; otherwise → status:
       accepted. Skipped entirely when no globals are pending.

    2. Decide if another cycle is needed:
       - any role's <role>.corrections.yaml has entries  →
         start a new cycle (round++, next_step=patch).
       - all corrections.yaml are empty                 →
         iteration is converged; next_step=user_review.

Patch will then either run (round 2+) and apply corrections, or
the user-review gate fires to settle conv/dec into the project's
main folder and close the iteration.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

import yaml

from core import coreyaml, iter_status, proposals
from core.context import (
    active_roles,
    conventions_block,
    decisions_block,
    roles_block,
    stack_block,
)
from core.stage import Stage
from core.util import default_log_dir, instruction_path
from llm import CallSpec, LLMConfig, call_many, resolve_llm
from ui import MultiSpinner


def validate(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Cross-lead global validation, then corrections-presence check."""
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        raise RuntimeError(
            "no current_iteration in core.yaml — run plan + cycle first"
        )
    iteration_n = _iteration_number(parent_id)

    profile_path = project_dir / "v84" / "profile.yaml"
    roles = active_roles(profile_path)
    if not roles:
        raise RuntimeError("no active roles in profile.yaml")

    # ---- Cross-lead validation of architect's pending globals ----------
    pending_conv, pending_dec = _read_pending_globals(project_dir, iteration_n)
    if pending_conv or pending_dec:
        if cfg is None:
            raise ValueError(
                "LLMConfig required when pending globals exist — "
                "validate runs cross-lead validation"
            )
        _run_cross_lead_validation(
            project_dir=project_dir,
            iteration_n=iteration_n,
            roles=roles,
            pending_conv=pending_conv,
            pending_dec=pending_dec,
            cfg=cfg,
        )
    else:
        print(
            "  validate: no pending architect globals — skipping cross-lead",
            file=sys.stderr,
        )

    # ---- Cycle-end check: any pending corrections across roles? --------
    counts: dict[str, int] = {}
    total = 0
    for role in roles:
        n = len(proposals.read_corrections(project_dir, iteration_n, role))
        counts[role] = n
        total += n

    summary = ", ".join(f"{r}: {c}" for r, c in counts.items())
    print(f"  validate: corrections per role — {summary}", file=sys.stderr)

    if total > 0:
        iter_status.next_round_to(project_dir, iteration_n, "patch")
        print(
            f"  → {total} correction(s) pending → starting new cycle "
            f"(patch in round "
            f"{iter_status.read(project_dir, iteration_n).get('round')})",
            file=sys.stderr,
        )
    else:
        iter_status.advance_to(project_dir, iteration_n, "user_review")
        print(
            "  ✓ no corrections remaining → iteration converged "
            "(next_step: user_review)",
            file=sys.stderr,
        )

    return iter_status.path(project_dir, iteration_n)


# -----------------------------------------------------------------------------
# Cross-lead validation of architect-proposed globals
# -----------------------------------------------------------------------------

def _read_pending_globals(
    project_dir: Path, iteration_n: int,
) -> tuple[list[dict], list[dict]]:
    """Return (pending_global_conventions, pending_global_decisions)."""
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    conv = _read_pending(iter_dir / "global.conventions.yaml")
    dec = _read_pending(iter_dir / "global.decisions.yaml")
    return conv, dec


def _read_pending(p: Path) -> list[dict]:
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        return []
    return [r for r in data if isinstance(r, dict) and r.get("status") == "pending"]


def _run_cross_lead_validation(
    *,
    project_dir: Path,
    iteration_n: int,
    roles: list[str],
    pending_conv: list[dict],
    pending_dec: list[dict],
    cfg: LLMConfig,
) -> None:
    """Fan out one validation call per lead. Aggregate single-veto:
    any reject → status: rejected (with the first reject's reason);
    otherwise → status: accepted."""
    skill_file = instruction_path("iteration", "validate-globals.md")
    if not skill_file.exists():
        raise FileNotFoundError(f"Instruction not found: {skill_file}")
    system = skill_file.read_text(encoding="utf-8")

    fan_cfg = _fan_out_cfg(project_dir, fallback=cfg)

    specs: list[CallSpec] = []
    labels: list[str] = []
    for role in roles:
        labels.append(role)
        specs.append(CallSpec(
            system=system,
            user_msgs=_build_user_msgs(
                project_dir=project_dir,
                role=role,
                pending_conv=pending_conv,
                pending_dec=pending_dec,
            ),
            log_name=f"iter-{iteration_n}-validate-{role}",
        ))

    workers = min(fan_cfg.max_concurrency, len(specs))
    print(
        f"  validating {len(pending_conv) + len(pending_dec)} "
        f"global(s) across {len(specs)} lead(s) — model {fan_cfg.model} "
        f"@ {fan_cfg.url} (workers: {workers})",
        file=sys.stderr,
    )
    with MultiSpinner(labels) as ms:
        results = call_many(
            fan_cfg, specs,
            log_dir=default_log_dir(),
            progress=ms,
        )

    # Collect verdicts per global id from every lead.
    # by_id[gid] = list of {role, verdict, reason?}
    by_id_conv: dict[str, list[dict]] = {}
    by_id_dec: dict[str, list[dict]] = {}
    failed: list[tuple[str, str]] = []
    for role, result in zip(roles, results):
        if result.error is not None:
            failed.append((role, repr(result.error)))
            continue
        parsed = _parse(result.response or "")
        for v in parsed["convention_verdicts"]:
            by_id_conv.setdefault(v["id"], []).append({"role": role, **v})
        for v in parsed["decision_verdicts"]:
            by_id_dec.setdefault(v["id"], []).append({"role": role, **v})

    if failed:
        for role, err in failed:
            print(f"  ✗ {role}: {err}", file=sys.stderr)
        raise RuntimeError(
            f"{len(failed)} cross-lead validation call(s) failed — re-run to retry"
        )

    # Apply single-veto and update files.
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    _apply_global_verdicts(
        iter_dir / "global.conventions.yaml", pending_conv, by_id_conv,
    )
    _apply_global_verdicts(
        iter_dir / "global.decisions.yaml", pending_dec, by_id_dec,
    )


def _apply_global_verdicts(
    p: Path, pending: list[dict], votes: dict[str, list[dict]],
) -> None:
    """Update each pending record's status based on aggregated lead
    verdicts. Single-veto: any reject → rejected (with first
    reject's reason and the rejecting role recorded); otherwise →
    accepted. Records with no votes stay pending (treat as
    failed coverage and surface)."""
    if not p.exists():
        return
    records = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    if not isinstance(records, list):
        return

    accepted_n = rejected_n = orphan_n = 0
    for rec in records:
        if not isinstance(rec, dict) or rec.get("status") != "pending":
            continue
        rid = rec.get("id")
        cast = votes.get(rid, [])
        if not cast:
            orphan_n += 1
            continue
        rejects = [v for v in cast if v["verdict"] == "reject"]
        if rejects:
            first = rejects[0]
            rec["status"] = "rejected"
            rec["rejected_by"] = f"{first['role']}.lead"
            if first.get("reason"):
                rec["rejection_reason"] = first["reason"]
            rejected_n += 1
        else:
            rec["status"] = "accepted"
            accepted_n += 1

    p.write_text(
        yaml.safe_dump(records, default_flow_style=False, sort_keys=False,
                       allow_unicode=True, width=10000),
        encoding="utf-8",
    )
    print(
        f"  ✓ {p.name} — {accepted_n} accepted, {rejected_n} rejected"
        + (f", {orphan_n} unvoted (left pending)" if orphan_n else ""),
        file=sys.stderr,
    )


# -----------------------------------------------------------------------------
# Per-lead context builder
# -----------------------------------------------------------------------------

def _build_user_msgs(
    *,
    project_dir: Path,
    role: str,
    pending_conv: list[dict],
    pending_dec: list[dict],
) -> list[str]:
    """Multi-message context for one lead's global-validation call."""
    msgs: list[str] = [
        f"## Your role\n\n{roles_block(project_dir, [role])}",
    ]

    stack = stack_block(project_dir, roles=[role]).strip()
    if stack:
        msgs.append(f"## Role stack\n\n{stack}")

    conv = conventions_block(project_dir, role=role).strip()
    if conv:
        msgs.append(f"## Conventions in scope (role + globals)\n\n{conv}")

    dec = decisions_block(project_dir, role=role).strip()
    if dec:
        msgs.append(f"## Decisions in scope (role + globals)\n\n{dec}")

    if pending_conv:
        msgs.append(
            f"## Pending global conventions ({len(pending_conv)})\n\n"
            f"```yaml\n{_dump(pending_conv).rstrip()}\n```"
        )
    if pending_dec:
        msgs.append(
            f"## Pending global decisions ({len(pending_dec)})\n\n"
            f"```yaml\n{_dump(pending_dec).rstrip()}\n```"
        )

    msgs.append(
        "Vote accept/reject on every pending global from your role's "
        "perspective. Follow your output format exactly."
    )
    return msgs


def _dump(items: list[dict]) -> str:
    return yaml.safe_dump(
        items, default_flow_style=False, sort_keys=False,
        allow_unicode=True, width=10000,
    )


# -----------------------------------------------------------------------------
# Response parsing
# -----------------------------------------------------------------------------

_VERDICTS = {"accept", "reject"}


def _parse(yaml_text: str) -> dict:
    """Permissive parse of one lead's validate-globals response."""
    try:
        data = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {
        "convention_verdicts": _norm_verdicts(data.get("convention_verdicts")),
        "decision_verdicts": _norm_verdicts(data.get("decision_verdicts")),
    }


def _norm_verdicts(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for v in raw:
        if not isinstance(v, dict):
            continue
        verdict = v.get("verdict")
        if verdict not in _VERDICTS:
            continue
        rid = v.get("id")
        if not isinstance(rid, str) or not rid.strip():
            continue
        entry: dict[str, Any] = {"id": rid.strip(), "verdict": verdict}
        if verdict == "reject":
            reason = v.get("reason")
            if isinstance(reason, str) and reason.strip():
                entry["reason"] = reason.strip()
        out.append(entry)
    return out


# -----------------------------------------------------------------------------
# LLM tier resolution (mirrors lead/architect pattern)
# -----------------------------------------------------------------------------

def _fan_out_cfg(project_dir: Path, *, fallback: LLMConfig) -> LLMConfig:
    """Resolve the multi tier from profile.yaml, fallback to single."""
    try:
        return resolve_llm(project_dir / "v84" / "profile.yaml", "multi")
    except Exception:
        return fallback


# -----------------------------------------------------------------------------
# Stage glue
# -----------------------------------------------------------------------------

def _iteration_number(task_id: str) -> int:
    return int(task_id.split(".")[0].split("-")[1])


def _is_done(project_dir: Path) -> bool:
    """Done when status.yaml says next_step has moved past `validate`."""
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        return False
    iteration_n = _iteration_number(parent_id)
    return iter_status.stage_is_done(project_dir, iteration_n, "validate")


STAGE = Stage(
    name="validate",
    title="Validate cycle end (cross-lead globals + corrections check)",
    priority=1402,
    produces="iterations/<n>/status.yaml#next_step",
    requires=("architect",),
    needs_brief=False,
    is_done=_is_done,
    call=validate,
)
