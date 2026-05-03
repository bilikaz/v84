"""
draft.py — Per-role round-1 writer.

Round 1's pipeline opener for a single role. Called from the cycle
orchestrator: one role's writer drafts the concrete actions for the
iteration's sub-tasks, given the iteration plan + the role's stack
slice + history.

Per-role output lands at `iterations/<n>/<role>.yaml`. On success the
role's pipeline step advances from `draft` → `review`.

Reviewer / lead / architect layers run later — see cycle.py for the
orchestrator and review.py / lead_round.py / architect.py for the
downstream stages.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from core import iter_status, proposals
from core.context import build_user_msgs
from core.util import default_log_dir, load_instruction
from core.versioning import versioned_write
from llm import CallSpec, LLMConfig, call_many, resolve_llm
from ui import spinner


def draft_role(
    project_dir: Path,
    parent: dict,
    iteration_n: int,
    role: str,
    *,
    cfg: LLMConfig,
) -> None:
    """Draft round 1 for a single role.

    Parses the writer's response, persists `<role>.yaml` and seeds
    `<role>.rules.yaml` with any rule proposals, and advances the
    role's pipeline step to `review` on success. Raises on failure
    so the cycle orchestrator can surface the error and leave the
    role's status untouched (re-running resumes from `draft`).
    """
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    iter_dir.mkdir(parents=True, exist_ok=True)

    fan_cfg = _fan_out_cfg(project_dir, fallback=cfg)

    system, schema = load_instruction("iteration", "draft")
    spec = CallSpec(
        system=system,
        user_msgs=build_user_msgs(
            project_dir, parent, iteration_n,
            {
                "plan":                          True,
                "active_roles":                  None,
                "stack":                         [role],
                "layout":                        [role],
                "role_definition":               [role],
                "history":                       [role],
                "actions":                       None,
                "corrections":                   None,
                "corrections_pending":           None,
                "corrections_rejected":          None,
                "corrections_applied":           None,
                "corrections_rejected_history":  None,
                "rules":                         [role],
                "rules_pending":                 None,
                "rules_rejected":                None,
                "trailing": "Draft the concrete actions for this iteration.",
            },
            role=role,
        ),
        response_schema=schema,
        log_name=f"iter-{iteration_n}-draft-{role}",
    )

    results = call_many(fan_cfg, [spec], log_dir=default_log_dir())
    result = results[0]
    if result.error is not None:
        raise RuntimeError(f"draft failed for {role}: {result.error!r}")

    parsed = _parse(result.response or {})
    out_file = iter_dir / f"{role}.yaml"
    versioned_write(
        out_file, _render_role_output(parsed),
        project_dir=project_dir,
    )
    spinner.log(f"  ✓ {out_file}")

    # Seed the iteration's role-scoped rules store. Draft is the first
    # stage to touch this file; review/patch will append later. Ids are
    # harness-assigned per emit order.
    rule_records = proposals.to_pending_rule_records(
        parsed.get("rules"),
        id_prefix=f"v84-{iteration_n}.{role}.rule",
    )
    proposals.write_rules(project_dir, iteration_n, role, rule_records)

    iter_status.set_role_step(
        project_dir, iteration_n, role, iter_status.STEP_REVIEW,
    )


# -----------------------------------------------------------------------------
# Output normalisation + persistence
# -----------------------------------------------------------------------------

def _render_role_output(parsed: dict) -> str:
    """Render the writer's actions list as the on-disk shape.

    The writer owns its own ids in the form `<task_id>.<role>.<n>`;
    the parent task is encoded in the id itself, so no separate
    `task_id` field is kept. The filename already encodes the role
    so no top-level `role:` key is written. Rule proposals are
    persisted separately by the caller into the iteration's role-
    scoped pending store; they don't appear here.
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
        # `verify` is the writer-authored block of observable
        # assertions. Stripped from documentation/<role>.yaml at
        # finish time (not part of the role's persistent surface),
        # but preserved here so reviewer / lead / architect / patch
        # see it alongside the rest of the action.
        if a.get("verify"):
            entry["verify"] = a["verify"]
        ordered.append(entry)

    return yaml.safe_dump(
        {"actions": ordered},
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=10000,
    )


def _parse(data: dict) -> dict:
    """Writer response is `{actions, rules}`, already shape-validated by
    the response_format schema. Sanity-strip rows missing required prose
    and normalise the `verify:` field to a single string."""
    if not isinstance(data, dict):
        return {}

    actions: list[dict] = []
    for a in data.get("actions") or []:
        if not isinstance(a, dict):
            continue
        prose = (a.get("action") or "").strip()
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
        verify = _parse_verify(a.get("verify"))
        if verify:
            entry["verify"] = verify
        actions.append(entry)

    out: dict[str, Any] = {"actions": actions}
    rules = _parse_proposals(data.get("rules"))
    if rules:
        out["rules"] = rules
    return out


def _parse_verify(raw: Any) -> str:
    """Normalise an action's `verify:` field to a single block-scalar
    string with one assertion per line."""
    if raw is None:
        return ""
    if isinstance(raw, list):
        lines = [str(item).strip() for item in raw]
    elif isinstance(raw, str):
        lines = [ln.rstrip() for ln in raw.splitlines()]
    else:
        return ""
    cleaned = [ln for ln in lines if ln.strip()]
    return "\n".join(cleaned)


def _parse_proposals(raw: Any) -> list[dict]:
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
