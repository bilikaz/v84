"""
rules_validate.py — Pre-pass: per-lead voting on architect's pending
globals.

Fires after rules_architect. Fan out one call per active lead;
each lead votes accept/reject on every pending global, checking:

    - drift against root-promoted rules (project-wide globals
      and the role's promoted role rules)
    - stack-fit for the role's reality
    - coherence against the role's own pending lead pack
    - completeness of any `promotes_from` claim that cites the
      role's lead rule

Single-veto rule: any reject from any lead → status: rejected with
`rejected_by: <role>.lead` and `rejection_reason` recorded;
otherwise → status: accepted.

After voting, for every newly-accepted global with a
`promotes_from: [...]` list, the cited lead-rule ids are retired
in their role files (status: superseded, superseded_by =
<global_id>) so no duplicate survives.

Advances next_step → rules_consolidate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

from core import coreyaml, iter_status, proposals
from core.context import active_roles, build_user_msgs
from core.stage import Stage
from core.util import default_log_dir, load_instruction
from llm import CallSpec, LLMConfig, call_many, resolve_llm
from ui import spinner


def rules_validate(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Cross-lead validation of pre-pass globals."""
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        raise RuntimeError(
            "no current_iteration in core.yaml — run plan + rules_lead "
            "+ rules_architect first"
        )
    parent = coreyaml.find_by_id(data, parent_id)
    iteration_n = _iteration_number(parent_id)

    profile_path = project_dir / "v84" / "profile.yaml"
    roles = active_roles(profile_path)
    if not roles:
        raise RuntimeError("no active roles in profile.yaml")

    pending_globals = _read_pending_globals(project_dir, iteration_n)
    if not pending_globals:
        spinner.log(
            "  rules_validate: nothing pending — skipping cross-lead vote"
        )
        iter_status.advance_to(
            project_dir, iteration_n, iter_status.STEP_RULES_CONSOLIDATE,
        )
        return iter_status.path(project_dir, iteration_n)

    if cfg is None:
        raise ValueError(
            "LLMConfig required when pending globals exist — "
            "rules_validate runs cross-lead voting"
        )

    fan_cfg = _fan_out_cfg(project_dir, fallback=cfg)
    system, schema = load_instruction("iteration", "rules_validate")

    specs: list[CallSpec] = []
    for role in roles:
        specs.append(CallSpec(
            system=system,
            user_msgs=build_user_msgs(
                project_dir, parent, iteration_n,
                {
                    "stack":           [role],
                    "layout":          [role],
                    "role_definition": [role],
                    # Promoted root rules + this role's just-accepted
                    # lead pack (both render via the rules builder).
                    "rules":           [role],
                    # Architect's pending globals, awaiting this lead's vote.
                    "rules_pending":   ["global"],
                    "trailing": (
                        "Vote accept or reject on every pending global "
                        "from your role's perspective. Reject only when "
                        "you can name a concrete conflict — drift vs a "
                        "root rule, your stack/layout cannot honor it, "
                        "or it contradicts your own pending lead rule."
                    ),
                },
                role=role,
            ),
            response_schema=schema,
            log_name=f"iter-{iteration_n}-rules_validate-{role}",
        ))

    workers = min(fan_cfg.max_concurrency, len(specs))
    spinner.log(
        f"  rules_validate: {len(pending_globals)} global(s) across "
        f"{len(specs)} lead(s) — model {fan_cfg.model} @ {fan_cfg.url} "
        f"(workers: {workers})"
    )
    results = call_many(fan_cfg, specs, log_dir=default_log_dir())

    # Aggregate verdicts per global id.
    by_id: dict[str, list[dict]] = {}
    failed: list[tuple[str, str]] = []
    for role, result in zip(roles, results):
        if result.error is not None:
            failed.append((role, repr(result.error)))
            continue
        for v in _parse_verdicts(result.response or {}):
            by_id.setdefault(v["id"], []).append({"role": role, **v})

    if failed:
        for role, err in failed:
            spinner.log(f"  ✗ {role}: {err}")
        raise RuntimeError(
            f"{len(failed)} rules_validate call(s) failed — re-run to retry"
        )

    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    accepted = _apply_global_verdicts(
        iter_dir / "global.rules.yaml", pending_globals, by_id,
    )

    # For each accepted global with promotes_from, retire the cited
    # lead rules so no duplicate survives.
    to_retire: dict[str, str] = {}
    for rec in accepted:
        gid = rec.get("id")
        if not gid:
            continue
        for lead_id in rec.get("promotes_from") or []:
            if isinstance(lead_id, str) and lead_id.strip():
                to_retire[lead_id.strip()] = gid

    if to_retire:
        n_moved = proposals.retire_lead_rules(
            project_dir, iteration_n, to_retire,
        )
        not_found = len(to_retire) - n_moved
        spinner.log(
            f"  ✓ retired {n_moved} lead rule(s) via promotes_from"
            + (f"; {not_found} cited id(s) not found" if not_found else "")
        )

    iter_status.advance_to(
        project_dir, iteration_n, iter_status.STEP_RULES_CONSOLIDATE,
    )
    return iter_status.path(project_dir, iteration_n)


# -----------------------------------------------------------------------------
# Voting + verdict application
# -----------------------------------------------------------------------------

def _read_pending_globals(
    project_dir: Path, iteration_n: int,
) -> list[dict]:
    p = project_dir / "v84" / "iterations" / str(iteration_n) / "global.rules.yaml"
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        return []
    return [r for r in data if isinstance(r, dict) and r.get("status") == "pending"]


def _apply_global_verdicts(
    p: Path, pending: list[dict], votes: dict[str, list[dict]],
) -> list[dict]:
    """Single-veto: any reject → status: rejected with rejected_by /
    rejection_reason from the first rejecting lead. Otherwise →
    status: accepted. Returns records that just transitioned to
    accepted so the caller can act on promotes_from."""
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
            # Set canonical text so downstream consumers (consolidate,
            # user_rules_review, draft) read a stable wording.
            rec["text"] = rec.get("proposal") or ""
            accepted_n += 1
            just_accepted.append(rec)

    p.write_text(
        yaml.safe_dump(records, default_flow_style=False, sort_keys=False,
                       allow_unicode=True, width=10000),
        encoding="utf-8",
    )
    spinner.log(
        f"  ✓ {p.name} — {accepted_n} accepted, {rejected_n} rejected"
        + (f", {orphan_n} unvoted (left pending)" if orphan_n else "")
    )
    return just_accepted


# -----------------------------------------------------------------------------
# Response parsing
# -----------------------------------------------------------------------------

_VERDICTS = {"accept", "reject"}


def _parse_verdicts(data: dict) -> list[dict]:
    if not isinstance(data, dict):
        return []
    out: list[dict] = []
    for v in data.get("rules") or []:
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
        out.append(entry)
    return out


# -----------------------------------------------------------------------------
# Stage glue
# -----------------------------------------------------------------------------

def _fan_out_cfg(project_dir: Path, *, fallback: LLMConfig) -> LLMConfig:
    try:
        return resolve_llm(
            project_dir=project_dir, tier="multi", interactive=False,
        )
    except Exception:
        return fallback


def _iteration_number(task_id: str) -> int:
    return int(task_id.split(".")[0].split("-")[1])


def _is_done(project_dir: Path) -> bool:
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        return False
    iteration_n = _iteration_number(parent_id)
    return iter_status.stage_is_done(
        project_dir, iteration_n, "rules_validate",
    )


STAGE = Stage(
    name="rules_validate",
    title="Pre-pass: per-lead vote on architect's pending globals",
    priority=1030,
    produces="iterations/<n>/global.rules.yaml",
    requires=("rules_architect",),
    needs_brief=False,
    is_done=_is_done,
    call=rules_validate,
)
