"""
rules_lead.py — Pre-pass: per-role lead proposes role-internal rules
BEFORE any actions are drafted.

Fires once between plan and rules_architect. Fan-out per active
role; each lead reads plan + role + stack + layout + role's
promoted-root rules + role's history, then proposes 5–7 starting
rules covering file/folder conventions, naming, stack-driven
patterns, structural decomposition, and role-internal contracts.

Lead is the role's authority — proposals settle as accepted on
the spot. They later face the architect's consolidation pass
(rules_consolidate) once globals are settled, which may retire
ones that conflict or are subsumed.

Output: append accepted records to iterations/<n>/<role>.rules.yaml
with ids `v84-<n>.<role>.lead.rule.<m>`.

Advances next_step → rules_architect when every active role has
landed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from core import coreyaml, iter_status, proposals
from core.context import active_roles, build_user_msgs
from core.stage import Stage
from core.util import default_log_dir, load_instruction
from llm import CallSpec, LLMConfig, call_many, resolve_llm
from ui import spinner


def rules_lead(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Run the per-role rules_lead fan-out for the current iteration."""
    if cfg is None:
        raise ValueError("LLMConfig required — call via v84.py or pass cfg=")

    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        raise RuntimeError(
            "no current_iteration set in core.yaml — run plan first"
        )
    parent = coreyaml.find_by_id(data, parent_id)
    if parent is None:
        raise RuntimeError(f"current_iteration {parent_id!r} not found")
    iteration_n = _iteration_number(parent_id)

    profile_path = project_dir / "v84" / "profile.yaml"
    roles = active_roles(profile_path)
    if not roles:
        raise RuntimeError("no active roles in profile.yaml")

    fan_cfg = _fan_out_cfg(project_dir, fallback=cfg)
    system, schema = load_instruction("iteration", "rules_lead")

    specs: list[CallSpec] = []
    for role in roles:
        specs.append(CallSpec(
            system=system,
            user_msgs=build_user_msgs(
                project_dir, parent, iteration_n,
                {
                    "plan":             True,
                    "stack":            [role],
                    "layout":           [role],
                    "role_definition":  [role],
                    "history":          [role],
                    "rules":            [role],
                    "trailing": (
                        "Propose role-scoped rules to bind every action "
                        "your role produces this iteration. On a fresh "
                        "iteration with no inherited root rules, aim for "
                        "5–7 starting rules."
                    ),
                },
                role=role,
            ),
            response_schema=schema,
            log_name=f"iter-{iteration_n}-rules_lead-{role}",
        ))

    workers = min(fan_cfg.max_concurrency, len(specs))
    spinner.log(
        f"  rules_lead: proposing across {len(specs)} role(s) — "
        f"model {fan_cfg.model} @ {fan_cfg.url} (workers: {workers})"
    )
    results = call_many(fan_cfg, specs, log_dir=default_log_dir())

    failed: list[tuple[str, str]] = []
    for role, result in zip(roles, results):
        if result.error is not None:
            failed.append((role, repr(result.error)))
            continue
        rules = _norm_rules(result.response or {})
        _persist_role_rules(
            project_dir=project_dir,
            iteration_n=iteration_n,
            role=role,
            rules=rules,
        )

    if failed:
        for role, err in failed:
            spinner.log(f"  ✗ {role}: {err}")
        raise RuntimeError(
            f"{len(failed)} rules_lead call(s) failed — re-run to retry"
        )

    iter_status.advance_to(
        project_dir, iteration_n, iter_status.STEP_RULES_ARCHITECT,
    )
    return iter_status.path(project_dir, iteration_n)


# -----------------------------------------------------------------------------
# Persistence
# -----------------------------------------------------------------------------

def _persist_role_rules(
    *,
    project_dir: Path,
    iteration_n: int,
    role: str,
    rules: list[dict],
) -> None:
    """Append accepted lead-authored rule records to <role>.rules.yaml.
    Lead is the role's authority — they land as `status: accepted` with
    `text` set to the proposal."""
    if not rules:
        spinner.log(
            f"  ✓ {role}: no rules proposed (empty pack accepted)"
        )
        return

    rule_prefix = f"v84-{iteration_n}.{role}.lead.rule"
    existing = proposals.read_rules(project_dir, iteration_n, role)
    new_records = proposals.to_accepted_rule_records(
        rules,
        id_prefix=rule_prefix,
        start_n=proposals.next_index_for_prefix(existing, rule_prefix),
    )
    if not new_records:
        return

    proposals.write_rules(
        project_dir, iteration_n, role,
        proposals.append_pending(existing, new_records),
    )
    spinner.log(
        f"  ✓ {role}.rules.yaml +{len(new_records)} lead-authored "
        f"(accepted on the spot)"
    )


# -----------------------------------------------------------------------------
# Response parsing
# -----------------------------------------------------------------------------

def _norm_rules(data: dict) -> list[dict]:
    """`rules` is the only output key — schema-validated upstream."""
    if not isinstance(data, dict):
        return []
    raw = data.get("rules")
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        proposal = (p.get("proposal") or "").strip()
        if not proposal:
            continue
        entry: dict[str, Any] = {"proposal": proposal}
        alts = p.get("alternatives")
        if isinstance(alts, list):
            cleaned = [str(a).strip() for a in alts if str(a).strip()]
            if cleaned:
                entry["alternatives"] = cleaned
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
    """Done when status.yaml says next_step has moved past `rules_lead`."""
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        return False
    iteration_n = _iteration_number(parent_id)
    return iter_status.stage_is_done(
        project_dir, iteration_n, "rules_lead",
    )


STAGE = Stage(
    name="rules_lead",
    title="Pre-pass: per-role lead proposes role-internal rules",
    priority=1010,
    produces="iterations/<n>/<role>.rules.yaml",
    requires=("plan",),
    needs_brief=False,
    is_done=_is_done,
    call=rules_lead,
)
