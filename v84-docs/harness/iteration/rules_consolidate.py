"""
rules_consolidate.py — Pre-pass: architect's coherence pass over
surviving lead rules.

Fires after rules_validate. Single architect call — read every
role's lead pack (still status: accepted from rules_lead, minus
any retired via promotes_from), the now-settled globals (status:
accepted in iterations/<n>/global.rules.yaml), root rules, and
rejected globals.

For each pending lead rule, vote accept (keep as-is) or reject
(retire because it conflicts with a settled global, drifts from
a root rule, is subsumed, or duplicates another role's rule).

Architect does NOT propose new rules and does NOT reword existing
ones at this stage.

Output: status updates on per-role <role>.rules.yaml — accepted
records stay accepted; rejected records flip to status: rejected
with rejected_by: architect and rejection_reason set.

Advances next_step → user_rules_review.
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


def rules_consolidate(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Architect's coherence pass over surviving lead rules."""
    if cfg is None:
        raise ValueError("LLMConfig required — call via v84.py or pass cfg=")

    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        raise RuntimeError(
            "no current_iteration in core.yaml — earlier pre-pass stages missing"
        )
    parent = coreyaml.find_by_id(data, parent_id)
    iteration_n = _iteration_number(parent_id)

    profile_path = project_dir / "v84" / "profile.yaml"
    roles = active_roles(profile_path)
    if not roles:
        raise RuntimeError("no active roles in profile.yaml")

    # Gather every pending lead rule awaiting architect's coherence
    # verdict. Rules retired earlier this stage via promotes_from
    # carry status: superseded and won't appear here; rules already
    # rejected by rules_validate-side drift checks won't either.
    surviving: dict[str, list[dict]] = {}
    total_pending = 0
    for role in roles:
        recs = [
            r for r in proposals.read_rules(project_dir, iteration_n, role)
            if r.get("status") == "pending"
        ]
        if recs:
            surviving[role] = recs
            total_pending += len(recs)

    if total_pending == 0:
        spinner.log("  rules_consolidate: no surviving lead rules — skipping")
        iter_status.advance_to(
            project_dir, iteration_n, iter_status.STEP_USER_RULES_REVIEW,
        )
        return iter_status.path(project_dir, iteration_n)

    arch_cfg = _arch_cfg(project_dir, fallback=cfg)
    system, schema = load_instruction("iteration", "rules_consolidate")

    user_msgs = build_user_msgs(
        project_dir, parent, iteration_n,
        {
            "plan":            True,
            "active_roles":    True,
            "stack":           "all",
            "layout":          ["global"] + roles,
            "role_definition": "all",
            # Settled globals + any role rules already accepted from
            # earlier rounds — binding context.
            "rules":           ["global"] + roles,
            # The pending lead packs from rules_lead — these are the
            # items the architect must render a verdict on.
            "rules_pending":   roles,
            "rules_rejected":  ["global"],
            "trailing": (
                "Render a verdict (accept or reject) on every "
                "pending lead rule listed above, in light of the "
                "now-settled globals. Reject only when you can name "
                "a concrete cause — conflict with a settled global, "
                "drift vs a root rule, subsumption by a settled "
                "global, or same-scope duplication across roles."
            ),
        },
    )

    spinner.log(
        f"  rules_consolidate: judging {total_pending} lead rule(s) "
        f"across {len(surviving)} role(s) — model {arch_cfg.model} "
        f"@ {arch_cfg.url}"
    )
    response = call_json(
        arch_cfg,
        system=system,
        user_msgs=user_msgs,
        response_schema=schema,
        log_name=f"iter-{iteration_n}-rules_consolidate",
        log_dir=default_log_dir(),
    )

    verdicts = _parse_verdicts(response or {})
    _apply_verdicts_to_roles(
        project_dir=project_dir,
        iteration_n=iteration_n,
        verdicts=verdicts,
        surviving=surviving,
    )

    iter_status.advance_to(
        project_dir, iteration_n, iter_status.STEP_USER_RULES_REVIEW,
    )
    return iter_status.path(project_dir, iteration_n)


# -----------------------------------------------------------------------------
# Verdict application
# -----------------------------------------------------------------------------

def _apply_verdicts_to_roles(
    *,
    project_dir: Path,
    iteration_n: int,
    verdicts: list[dict],
    surviving: dict[str, list[dict]],
) -> None:
    """Walk each role's rules file once. For each pending record:
      - matching `accept` verdict → status: accepted (final), with
        `text` set to the record's proposal so downstream consumers
        (user_rules_review, draft) read a stable canonical wording.
      - matching `reject` verdict → status: rejected with
        rejected_by: architect and rejection_reason recorded.
      - no matching verdict (architect failed to vote on this
        rule) → status: rejected with reason
        "orphan: architect did not vote". Architect must
        explicitly bless every pending rule to make it binding.

    Orphan verdicts (no matching pending id) are logged.
    """
    by_id: dict[str, dict] = {v["id"]: v for v in verdicts}
    matched: set[str] = set()

    for role, _recs in surviving.items():
        records = proposals.read_rules(project_dir, iteration_n, role)
        accepted_n = rejected_n = orphan_n = 0
        for r in records:
            if r.get("status") != "pending":
                continue
            rid = r.get("id")
            v = by_id.get(rid)
            if v is None:
                r["status"] = "rejected"
                r["rejected_by"] = "architect"
                r["rejection_reason"] = "orphan: architect did not vote"
                r.pop("text", None)
                rejected_n += 1
                orphan_n += 1
                continue
            matched.add(rid)
            if v["verdict"] == "accept":
                r["status"] = "accepted"
                if not r.get("text"):
                    r["text"] = (r.get("proposal") or "").strip()
                r.pop("rejection_reason", None)
                accepted_n += 1
                continue
            r["status"] = "rejected"
            r["rejected_by"] = "architect"
            if v.get("reason"):
                r["rejection_reason"] = v["reason"]
            r.pop("text", None)
            rejected_n += 1
        proposals.write_rules(project_dir, iteration_n, role, records)
        msg = (
            f"  ✓ {role}.rules.yaml — {accepted_n} accepted, "
            f"{rejected_n} rejected by consolidate"
        )
        if orphan_n:
            msg += f" (incl. {orphan_n} orphan — architect skipped)"
        spinner.log(msg)

    orphan = sum(1 for vid in by_id if vid not in matched)
    if orphan:
        spinner.log(
            f"  ✗ {orphan} consolidate verdict(s) had no matching "
            f"pending lead rule (orphans, ignored)"
        )


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
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        return False
    iteration_n = _iteration_number(parent_id)
    return iter_status.stage_is_done(
        project_dir, iteration_n, "rules_consolidate",
    )


STAGE = Stage(
    name="rules_consolidate",
    title="Pre-pass: architect's coherence pass over lead rules",
    priority=1040,
    produces="iterations/<n>/<role>.rules.yaml",
    requires=("rules_validate",),
    needs_brief=False,
    is_done=_is_done,
    call=rules_consolidate,
)
