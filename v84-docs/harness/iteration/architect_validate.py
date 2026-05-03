"""
validate.py — Iteration cycle-end decider.

Runs after the architect. Three jobs:

    1. Cross-lead validation of architect's pending global proposals.
       For each pending global in iterations/<n>/global.rules.yaml
       (status: pending), every active role-lead
       votes accept/reject. Single-veto rule: any reject → status:
       rejected with rejection_reason recorded; otherwise → status:
       accepted.

    2. Lead validation of architect's pending per-role corrections.
       The architect appended cross-role corrections into each
       affected role's <role>.corrections-pending.yaml. The role's
       OWN lead votes accept/reject. Accepted entries move to
       <role>.corrections.yaml (joining the patch punch list);
       rejected move to <role>.corrections-rejected.yaml with
       `rejected_by: <role>.lead`. Pending file cleared either way.

    Jobs 1 and 2 share a single per-lead LLM call: each lead sees
    pending globals (everyone votes) AND their own role's pending
    corrections (only they vote on those). Skipped when neither
    has anything pending.

    3. Decide if another cycle is needed:
       - any role's <role>.corrections.yaml has entries  →
         start a new cycle (round++, next_step=patch).
       - all corrections.yaml are empty                 →
         iteration is converged; next_step=user_review.

Patch will then either run (round 2+) and apply corrections, or
the user-review gate fires to settle rules into the project's
main folder and close the iteration.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

import yaml

from core import coreyaml, iter_status, proposals
from core.context import active_roles, build_user_msgs
from core.stage import Stage
from core.util import default_log_dir, load_instruction
from llm import CallSpec, LLMConfig, call_many, resolve_llm


def architect_validate(
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

    # ---- Cross-lead validation: globals + per-role architect corrections
    pending_rules = _read_pending_globals(project_dir, iteration_n)
    pending_corrs_by_role: dict[str, list[dict]] = {
        role: proposals.read_pending_corrections(project_dir, iteration_n, role)
        for role in roles
    }
    has_globals = bool(pending_rules)
    has_role_corrs = any(pending_corrs_by_role.values())

    if has_globals or has_role_corrs:
        if cfg is None:
            raise ValueError(
                "LLMConfig required when pending architect items exist — "
                "validate runs cross-lead validation"
            )
        _run_cross_lead_validation(
            project_dir=project_dir,
            iteration_n=iteration_n,
            roles=roles,
            pending_rules=pending_rules,
            pending_corrs_by_role=pending_corrs_by_role,
            cfg=cfg,
        )
    else:
        print(
            "  validate: nothing pending from architect — skipping cross-lead",
            file=sys.stderr,
        )

    # ---- Cycle-end check: any pending corrections across roles? --------
    counts: dict[str, int] = {}
    next_active: list[str] = []   # roles with pending corrections
    total = 0
    for role in roles:
        n = len(proposals.read_corrections(project_dir, iteration_n, role))
        counts[role] = n
        total += n
        if n > 0:
            next_active.append(role)

    summary = ", ".join(f"{r}: {c}" for r, c in counts.items())
    print(f"  validate: corrections per role — {summary}", file=sys.stderr)

    if total > 0:
        # Next round's pipeline only runs for roles with pending
        # corrections. Stamp them into the roles map at `patch` (the
        # round-2+ entry step); roles with no pending corrections are
        # omitted, which marks them as inactive for this round.
        iter_status.next_round_to(
            project_dir, iteration_n, iter_status.STEP_CYCLE,
            roles={r: iter_status.STEP_PATCH for r in next_active},
        )
        skipped = [r for r in roles if r not in next_active]
        msg = (
            f"  → {total} correction(s) pending across {len(next_active)} "
            f"role(s) → starting new cycle (patch in round "
            f"{iter_status.read(project_dir, iteration_n).get('round')})"
        )
        if skipped:
            msg += f"; skipping {', '.join(skipped)} (no corrections)"
        print(msg, file=sys.stderr)
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
) -> list[dict]:
    """Return pending global rule proposals from
    iterations/<n>/global.rules.yaml."""
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    return _read_pending(iter_dir / "global.rules.yaml")


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
    pending_rules: list[dict],
    pending_corrs_by_role: dict[str, list[dict]],
    cfg: LLMConfig,
) -> None:
    """Fan out one validation call per lead. Each lead votes on:
      - pending globals (every lead votes; single-veto aggregated)
      - their own role's pending architect corrections (only this
        lead's verdict counts; accepted move to corrections.yaml,
        rejected move to corrections-rejected.yaml).
    """
    system, schema = load_instruction("iteration", "architect_validate")

    fan_cfg = _fan_out_cfg(project_dir, fallback=cfg)

    specs: list[CallSpec] = []
    labels: list[str] = []
    for role in roles:
        labels.append(role)
        specs.append(CallSpec(
            system=system,
            user_msgs=build_user_msgs(
                project_dir,
                {},  # validate doesn't need parent task — no plan block
                iteration_n,
                {
                    "plan":                          None,
                    "active_roles":                  None,
                    "stack":                         [role],
                    "layout":                        None,
                    "role_definition":               [role],
                    "history":                       None,
                    "actions":                       None,
                    "corrections":                   None,
                    "corrections_pending":           [role],
                    "corrections_rejected":          None,
                    "corrections_applied":           None,
                    "corrections_rejected_history":  None,
                    "rules":                         [role],
                    "rules_pending":                 ["global"],
                    "rules_rejected":                None,
                    "trailing": (
                        "Vote accept/reject on every pending item from "
                        "your role's perspective."
                    ),
                },
                role=role,
            ),
            response_schema=schema,
            log_name=f"iter-{iteration_n}-architect_validate-{role}",
        ))

    workers = min(fan_cfg.max_concurrency, len(specs))
    n_corrs_total = sum(len(c) for c in pending_corrs_by_role.values())
    print(
        f"  validating {len(pending_rules)} global rule(s) "
        f"+ {n_corrs_total} per-role correction(s) across "
        f"{len(specs)} lead(s) — model {fan_cfg.model} @ {fan_cfg.url} "
        f"(workers: {workers})",
        file=sys.stderr,
    )
    results = call_many(fan_cfg, specs, log_dir=default_log_dir())

    # Collect verdicts per id from every lead.
    by_id_rule: dict[str, list[dict]] = {}
    # correction verdicts are per-role (only that lead's vote counts):
    # corr_verdicts_by_role[role] = list of {id, verdict, reason?}
    corr_verdicts_by_role: dict[str, list[dict]] = {role: [] for role in roles}
    failed: list[tuple[str, str]] = []
    for role, result in zip(roles, results):
        if result.error is not None:
            failed.append((role, repr(result.error)))
            continue
        parsed = _parse(result.response or {})
        for v in parsed["rule_verdicts"]:
            by_id_rule.setdefault(v["id"], []).append({"role": role, **v})
        corr_verdicts_by_role[role].extend(parsed["correction_verdicts"])

    if failed:
        for role, err in failed:
            print(f"  ✗ {role}: {err}", file=sys.stderr)
        raise RuntimeError(
            f"{len(failed)} cross-lead validation call(s) failed — re-run to retry"
        )

    # Apply global rule verdicts (single-veto across leads).
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    accepted_globals = _apply_global_verdicts(
        iter_dir / "global.rules.yaml", pending_rules, by_id_rule,
    )

    # Fan synthetic apply-corrections out to every active role for any
    # global rule that just landed accepted. Patch picks them up via
    # the role's corrections.yaml — collapses raise→apply from three
    # rounds to two.
    parent_task_id = f"v84-{iteration_n}"
    for rec in accepted_globals:
        rid = rec.get("id")
        if not rid:
            continue
        rule_text = rec.get("text") or rec.get("proposal") or ""
        synth = proposals.synthesize_apply_correction(
            rule_id=rid,
            rule_text=rule_text,
            parent_task_id=parent_task_id,
            scope="global",
        )
        for role in roles:
            if proposals.append_synthetic_correction(
                project_dir, iteration_n, role, synth,
            ):
                print(
                    f"  ✓ {role}.corrections.yaml +1 synthetic "
                    f"(global rule {rid} → apply)",
                    file=sys.stderr,
                )

    # Apply per-role architect-correction verdicts: accepted entries
    # join the role's punch list (corrections.yaml); rejected go to
    # corrections-rejected.yaml; pending file is cleared either way.
    # No rejection_reason — corrections are imperatives, not proposals
    # to negotiate; the architect re-judges fresh next round from the
    # current state.
    for role in roles:
        pending = pending_corrs_by_role.get(role, [])
        if not pending:
            continue
        verdicts = {v["id"]: v for v in corr_verdicts_by_role[role]}
        accepted, rejected = [], []
        for rec in pending:
            v = verdicts.get(rec.get("id"))
            if v is None or v["verdict"] == "reject":
                rec_out = dict(rec)
                rec_out["rejected_by"] = f"{role}.lead"
                rejected.append(rec_out)
            else:
                accepted.append(rec)

        if accepted:
            existing = proposals.read_corrections(project_dir, iteration_n, role)
            proposals.write_corrections(
                project_dir, iteration_n, role, existing + accepted,
            )
        if rejected:
            existing_rej = proposals.read_rejected_corrections(
                project_dir, iteration_n, role,
            )
            proposals.write_rejected_corrections(
                project_dir, iteration_n, role, existing_rej + rejected,
            )
        proposals.clear_pending_corrections(project_dir, iteration_n, role)
        print(
            f"  ✓ {role}: architect corrections — "
            f"{len(accepted)} accepted, {len(rejected)} rejected",
            file=sys.stderr,
        )


def _apply_global_verdicts(
    p: Path, pending: list[dict], votes: dict[str, list[dict]],
) -> list[dict]:
    """Update each pending record's status based on aggregated lead
    verdicts. Single-veto: any reject → rejected (with first
    reject's reason and the rejecting role recorded); otherwise →
    accepted. Records with no votes stay pending (treat as
    failed coverage and surface).

    Returns the list of records that just transitioned to `accepted`
    in this call so the caller can synthesise apply-corrections
    for them (fan-out to every active role).
    """
    if not p.exists():
        return []
    records = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    if not isinstance(records, list):
        return []

    just_accepted: list[dict] = []
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
            just_accepted.append(rec)

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
    return just_accepted


# -----------------------------------------------------------------------------
# Response parsing
# -----------------------------------------------------------------------------

_VERDICTS = {"accept", "reject"}


def _parse(data: dict) -> dict:
    """Pull rule and correction verdicts from the schema-validated
    response. Both arrays already have their canonical shapes — just
    normalise field whitespace and rename to internal canonical keys.
    """
    if not isinstance(data, dict):
        return {"rule_verdicts": [], "correction_verdicts": []}

    correction_verdicts: list[dict] = []
    for v in data.get("corrections") or []:
        if not isinstance(v, dict):
            continue
        rid = v.get("id")
        verdict = v.get("verdict")
        if not isinstance(rid, str) or not rid.strip():
            continue
        if verdict not in _VERDICTS:
            continue
        entry: dict[str, Any] = {"id": rid.strip(), "verdict": verdict}
        reason = v.get("reason")
        if isinstance(reason, str) and reason.strip():
            entry["reason"] = reason.strip()
        correction_verdicts.append(entry)

    rule_verdicts: list[dict] = []
    for v in data.get("rules") or []:
        if not isinstance(v, dict):
            continue
        rid = v.get("id")
        verdict = v.get("verdict")
        if not isinstance(rid, str) or not rid.strip():
            continue
        if verdict not in _VERDICTS:
            continue
        entry = {"id": rid.strip(), "verdict": verdict}
        reason = v.get("reason")
        if isinstance(reason, str) and reason.strip():
            entry["reason"] = reason.strip()
        rule_verdicts.append(entry)

    return {
        "rule_verdicts": rule_verdicts,
        "correction_verdicts": correction_verdicts,
    }


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
    """Done when status.yaml says next_step has moved past
    `architect_validate`."""
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        return False
    iteration_n = _iteration_number(parent_id)
    return iter_status.stage_is_done(
        project_dir, iteration_n, "architect_validate",
    )


STAGE = Stage(
    name="architect_validate",
    title="Architect-validate (cross-lead globals + per-role architect corrections + cycle-end check)",
    priority=1402,
    produces="iterations/<n>/status.yaml#next_step",
    requires=("architect",),
    needs_brief=False,
    is_done=_is_done,
    call=architect_validate,
)
