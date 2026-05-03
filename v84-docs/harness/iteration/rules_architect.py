"""
rules_architect.py — Pre-pass: architect proposes cross-role globals
BEFORE any actions are drafted.

Fires after rules_lead. Single LLM call — architect reads the
plan, every active role's lead pack (just-accepted role-internal
rules), full repo layout, full stack, and root globals + previously
rejected globals from earlier rounds.

Output:
    iterations/<n>/global.rules.yaml
        — pending architect-proposed globals (status: pending)
          with ids `v84-<n>.architect.rule.<m>` and an optional
          `promotes_from` field listing source lead-rule ids when
          the global lifts a role-internal pattern.

Advances next_step → rules_validate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from core import coreyaml, iter_status, proposals
from core.context import active_roles, build_user_msgs
from core.stage import Stage
from core.util import default_log_dir, load_instruction
from llm import LLMConfig, call_json, resolve_llm
from ui import spinner


def rules_architect(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Run the architect's cross-role rule proposal call."""
    if cfg is None:
        raise ValueError("LLMConfig required — call via v84.py or pass cfg=")

    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        raise RuntimeError(
            "no current_iteration set in core.yaml — run plan + rules_lead first"
        )
    parent = coreyaml.find_by_id(data, parent_id)
    if parent is None:
        raise RuntimeError(f"current_iteration {parent_id!r} not found")
    iteration_n = _iteration_number(parent_id)

    profile_path = project_dir / "v84" / "profile.yaml"
    roles = active_roles(profile_path)
    if not roles:
        raise RuntimeError("no active roles in profile.yaml")

    arch_cfg = _arch_cfg(project_dir, fallback=cfg)
    system, schema = load_instruction("iteration", "rules_architect")

    # The lead packs from rules_lead landed in <role>.rules.yaml as
    # `status: accepted`. Architect needs to see them to spot
    # generalisation patterns; we surface them via the existing rules
    # builder (scope=all) so accepted records render naturally.
    user_msgs = build_user_msgs(
        project_dir, parent, iteration_n,
        {
            "plan":            True,
            "active_roles":    True,
            "stack":           "all",
            "layout":          ["global"] + roles,
            "role_definition": "all",
            "rules":           ["global"] + roles,
            "rules_rejected":  ["global"],
            "trailing": (
                "Propose cross-role global rules. The rules listed "
                "per role above are the just-accepted lead packs from "
                "rules_lead — read them to spot patterns that should "
                "generalise across roles. On a fresh iteration with no "
                "inherited root globals, aim for 8–12 starting globals."
            ),
        },
    )

    spinner.log(
        f"  rules_architect: proposing globals for iteration "
        f"{iteration_n} — model {arch_cfg.model} @ {arch_cfg.url}"
    )
    response = call_json(
        arch_cfg,
        system=system,
        user_msgs=user_msgs,
        response_schema=schema,
        log_name=f"iter-{iteration_n}-rules_architect",
        log_dir=default_log_dir(),
    )

    rules = _norm_rules(response or {})
    _persist_globals(
        project_dir=project_dir,
        iteration_n=iteration_n,
        rules=rules,
    )

    iter_status.advance_to(
        project_dir, iteration_n, iter_status.STEP_RULES_VALIDATE,
    )
    return iter_status.path(project_dir, iteration_n)


# -----------------------------------------------------------------------------
# Persistence
# -----------------------------------------------------------------------------

def _persist_globals(
    *,
    project_dir: Path,
    iteration_n: int,
    rules: list[dict],
) -> None:
    """Write architect-proposed globals to global.rules.yaml as
    pending. Each carries an optional `promotes_from` list which
    survives into the validation pass and the post-vote retirement
    step in rules_validate."""
    if not rules:
        spinner.log("  ✓ architect proposed no globals (empty pack)")
        return

    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    iter_dir.mkdir(parents=True, exist_ok=True)
    rule_prefix = f"v84-{iteration_n}.architect.rule"

    records: list[dict] = []
    n = 0
    for r in rules:
        n += 1
        entry: dict[str, Any] = {
            "id": f"{rule_prefix}.{n}",
            "proposal": r["proposal"],
        }
        if r.get("alternatives"):
            entry["alternatives"] = r["alternatives"]
        if r.get("promotes_from"):
            entry["promotes_from"] = r["promotes_from"]
        entry["status"] = "pending"
        records.append(entry)

    proposals.write_rules(project_dir, iteration_n, "global", records)
    promo_n = sum(1 for r in records if r.get("promotes_from"))
    spinner.log(
        f"  ✓ global.rules.yaml ({len(records)} pending"
        + (f", {promo_n} with promotes_from" if promo_n else "") + ")"
    )


# -----------------------------------------------------------------------------
# Response parsing
# -----------------------------------------------------------------------------

def _norm_rules(data: dict) -> list[dict]:
    """Architect's `rules` array — schema-validated upstream. Pull
    proposal/alternatives/promotes_from with whitespace normalisation."""
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
        promotes = p.get("promotes_from")
        if isinstance(promotes, list):
            ids = [str(x).strip() for x in promotes if str(x).strip()]
            if ids:
                entry["promotes_from"] = ids
        out.append(entry)
    return out


# -----------------------------------------------------------------------------
# Stage glue
# -----------------------------------------------------------------------------

def _arch_cfg(project_dir: Path, *, fallback: LLMConfig) -> LLMConfig:
    try:
        return resolve_llm(
            project_dir=project_dir, tier="multi", interactive=False,
        )
    except Exception:
        return fallback


def _iteration_number(task_id: str) -> int:
    return int(task_id.split(".")[0].split("-")[1])


def _is_done(project_dir: Path) -> bool:
    """Done when next_step has moved past `rules_architect`."""
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        return False
    iteration_n = _iteration_number(parent_id)
    return iter_status.stage_is_done(
        project_dir, iteration_n, "rules_architect",
    )


STAGE = Stage(
    name="rules_architect",
    title="Pre-pass: architect proposes cross-role globals",
    priority=1020,
    produces="iterations/<n>/global.rules.yaml",
    requires=("rules_lead",),
    needs_brief=False,
    is_done=_is_done,
    call=rules_architect,
)
