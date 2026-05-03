"""
lead_round.py — Per-role combined verdict + raise stage.

The cycle orchestrator calls this once per role after the role's
review pass has landed. Two LLM calls fire in parallel for the role:

    1. Verdict call (review_validate.md) — vote accept/reject on
       pending reviewer corrections + pending rule proposals.
    2. Raise call (lead.md) — optionally add own corrections /
       rules the reviewers missed.

Both calls see the SAME pre-vote disk state. The raise call is told
to avoid duplicating concerns that already appear in the pending
lists. Once both responses are in, writes are applied sequentially:

    Phase A: apply verdicts
        - Accepted reviewer corrections → <role>.corrections.yaml
        - Rejected ones → <role>.corrections-rejected.yaml
        - Rule status updates in <role>.rules.yaml
        - Synthetic apply-corrections for newly-accepted rules
        - Pending corrections file cleared

    Phase B: apply raises (on top of post-verdict state)
        - Lead-authored corrections appended to corrections.yaml
        - Lead-authored rules added to rules.yaml as
          status: accepted (lead is the role's authority)
        - Synthetic apply-corrections for lead-authored rules

On success the role's pipeline step advances from `lead` → `done`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core import iter_status, proposals
from core.context import build_user_msgs
from core.util import default_log_dir, load_instruction
from llm import CallSpec, LLMConfig, call_many, resolve_llm
from ui import spinner


def lead_role(
    project_dir: Path,
    parent: dict,
    iteration_n: int,
    role: str,
    *,
    cfg: LLMConfig,
) -> None:
    """Run the verdict + raise pair for a single role.

    Applies verdicts and raises sequentially after both calls return.
    Advances the role's pipeline step to `done` on success. Raises on
    failure so the cycle orchestrator can leave the role at `lead`.
    """
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    iter_dir.mkdir(parents=True, exist_ok=True)

    # Snapshot pending state — verdicts apply against this exact list
    # (the LLM saw the same view).
    pending = proposals.read_pending_corrections(project_dir, iteration_n, role)
    has_pending_rules = _has_pending_rules(project_dir, iteration_n, role)

    fan_cfg = _fan_out_cfg(project_dir, fallback=cfg)

    verdict_system, verdict_schema = load_instruction("iteration", "review_validate")
    raise_system, raise_schema = load_instruction("iteration", "lead")

    specs: list[CallSpec] = []
    spec_kinds: list[str] = []   # "verdict" | "raise" per spec
    if pending or has_pending_rules:
        specs.append(_verdict_spec(
            role=role, system=verdict_system, schema=verdict_schema,
            project_dir=project_dir, parent=parent, iteration_n=iteration_n,
        ))
        spec_kinds.append("verdict")
    # Raise call always fires (lead might raise even if reviewers were
    # silent — lead spots what nobody else did).
    specs.append(_raise_spec(
        role=role, system=raise_system, schema=raise_schema,
        project_dir=project_dir, parent=parent, iteration_n=iteration_n,
    ))
    spec_kinds.append("raise")

    if not specs:
        # Nothing to do — pending was empty AND no rules, AND somehow
        # raise was suppressed (shouldn't happen). Mark done and move on.
        iter_status.set_role_step(
            project_dir, iteration_n, role, iter_status.STEP_DONE,
        )
        return

    results = call_many(fan_cfg, specs, log_dir=default_log_dir())

    verdict_response: dict = {}
    raise_response: dict = {}
    failed: list[tuple[str, str]] = []
    for kind, result in zip(spec_kinds, results):
        if result.error is not None:
            failed.append((kind, repr(result.error)))
            continue
        if kind == "verdict":
            verdict_response = result.response or {}
        else:
            raise_response = result.response or {}

    if failed:
        for kind, err in failed:
            spinner.log(f"  ✗ {role}.{kind}: {err}")
        raise RuntimeError(
            f"lead failed for {role}: {len(failed)} call(s) failed — "
            f"re-run to retry"
        )

    parent_task_id = f"v84-{iteration_n}"

    # Phase A: apply verdicts (post-vote state). Accepted reviewer
    # corrections STAY in the pending file (lead-blessed, awaiting
    # architect's lead_validate); rejected ones move to
    # corrections-rejected.yaml. Accepted reviewer rules stay
    # status: pending with the lead's text recorded; rejected ones
    # flip to status: rejected. Synth apply-correction generation
    # moved to architect Phase A so it only fires when a rule actually
    # transitions to accepted.
    if verdict_response:
        parsed = _parse_verdicts(verdict_response)
        _apply_corrections_verdicts(
            project_dir=project_dir,
            iteration_n=iteration_n,
            role=role,
            pending=pending,
            verdicts=parsed["correction_verdicts"],
        )
        _apply_rule_verdicts(
            project_dir=project_dir,
            iteration_n=iteration_n,
            role=role,
            verdicts=parsed["rule_verdicts"],
            parent_task_id=parent_task_id,
        )

    # Phase B: apply raises (on top of post-verdict state)
    if raise_response:
        parsed = _parse_raises(raise_response)
        _apply_lead_corrections(
            project_dir=project_dir,
            iteration_n=iteration_n,
            role=role,
            corrections=parsed["corrections"],
        )
        _apply_lead_rules(
            project_dir=project_dir,
            iteration_n=iteration_n,
            role=role,
            rules=parsed["rules"],
            parent_task_id=parent_task_id,
        )

    iter_status.set_role_step(
        project_dir, iteration_n, role, iter_status.STEP_DONE,
    )


# -----------------------------------------------------------------------------
# Spec builders
# -----------------------------------------------------------------------------

def _verdict_spec(
    *,
    role: str,
    system: str,
    schema: dict,
    project_dir: Path,
    parent: dict,
    iteration_n: int,
) -> CallSpec:
    return CallSpec(
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
                "actions":                       [role],
                "corrections":                   None,
                "corrections_pending":           [role],
                "corrections_rejected":          None,
                "corrections_applied":           [role],
                "corrections_rejected_history":  [role],
                "rules":                         [role],
                "rules_pending":                 [role],
                "rules_rejected":                [role],
                "trailing": (
                    "Vote accept/reject on every pending correction "
                    "and every pending rule proposal."
                ),
            },
            role=role,
        ),
        response_schema=schema,
        log_name=f"iter-{iteration_n}-lead_round-{role}-verdict",
    )


def _raise_spec(
    *,
    role: str,
    system: str,
    schema: dict,
    project_dir: Path,
    parent: dict,
    iteration_n: int,
) -> CallSpec:
    return CallSpec(
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
                "actions":                       [role],
                "corrections":                   None,
                "corrections_pending":           [role],
                "corrections_rejected":          None,
                "corrections_applied":           [role],
                "corrections_rejected_history":  [role],
                "rules":                         [role],
                "rules_pending":                 [role],
                "rules_rejected":                [role],
                "trailing": (
                    "Optionally raise corrections or rules if you "
                    "spot something the reviewers missed. The pending "
                    "lists above are being voted on in parallel — "
                    "don't duplicate concerns already raised there. "
                    "Most lead calls produce nothing — silence is fine."
                ),
            },
            role=role,
        ),
        response_schema=schema,
        log_name=f"iter-{iteration_n}-lead_round-{role}-raise",
    )


# -----------------------------------------------------------------------------
# Phase A: verdict application
# -----------------------------------------------------------------------------

def _apply_corrections_verdicts(
    *,
    project_dir: Path,
    iteration_n: int,
    role: str,
    pending: list[dict],
    verdicts: list[dict],
) -> None:
    """Apply lead's verdicts on reviewer corrections. Accepted entries
    STAY in `<role>.corrections-pending.yaml` (lead-blessed, awaiting
    architect's `lead_validate` to make the final move to
    `corrections.yaml`). Rejected entries — and orphans — move to
    `corrections-rejected.yaml`. Pending file is rewritten without the
    rejected/orphan entries."""
    if not pending:
        return
    by_id = {v["id"]: v for v in verdicts if v.get("id")}
    kept: list[dict] = []   # accepted-by-lead, still pending architect
    rejected: list[dict] = []
    orphan = 0
    for rec in pending:
        v = by_id.get(rec.get("id"))
        if v is None:
            orphan += 1
            rec_out = dict(rec)
            rec_out["rejected_by"] = f"{role}.lead"
            rec_out["rejection_reason"] = "orphan: lead did not vote"
            rejected.append(rec_out)
            continue
        if v["verdict"] == "accept":
            kept.append(rec)
        else:
            rec_out = dict(rec)
            rec_out["rejected_by"] = f"{role}.lead"
            if v.get("reason"):
                rec_out["rejection_reason"] = v["reason"]
            rejected.append(rec_out)

    # Rewrite pending without the rejected/orphan entries; keep the
    # accepted ones in place for architect to pick up.
    proposals.write_pending_corrections(
        project_dir, iteration_n, role, kept,
    )
    if rejected:
        existing_rej = proposals.read_rejected_corrections(
            project_dir, iteration_n, role,
        )
        proposals.write_rejected_corrections(
            project_dir, iteration_n, role, existing_rej + rejected,
        )

    msg = (f"  ✓ {role}: corrections — {len(kept)} kept pending "
           f"(awaiting architect), {len(rejected)} rejected")
    if orphan:
        msg += f" (incl. {orphan} orphan)"
    spinner.log(msg)


def _apply_rule_verdicts(
    *,
    project_dir: Path,
    iteration_n: int,
    role: str,
    verdicts: list[dict],
    parent_task_id: str,
) -> None:
    """Apply lead's verdicts on pending reviewer-raised rules. On
    `reject`, status flips to `rejected` (final). On `accept`, status
    stays `pending` and the lead's preferred wording is recorded on
    the record's `text` field — the architect's `lead_validate` makes
    the final accepted/rejected decision in its Phase A.

    The `parent_task_id` argument is preserved for caller signature
    compatibility but unused — synth apply-correction generation
    moved to architect Phase A so it fires only when a rule actually
    transitions to accepted."""
    del parent_task_id  # synth generation moved to architect Phase A
    if not verdicts:
        return
    recs = proposals.read_rules(project_dir, iteration_n, role)
    proposals.apply_lead_verdicts(recs, verdicts, rejected_by=f"{role}.lead")
    proposals.write_rules(project_dir, iteration_n, role, recs)

    accepts = sum(1 for v in verdicts if v.get("verdict") == "accept")
    rejects = sum(1 for v in verdicts if v.get("verdict") == "reject")
    spinner.log(
        f"  ✓ {role}.rules.yaml — {accepts} kept pending (lead's "
        f"text recorded, awaiting architect), {rejects} rejected"
    )


# -----------------------------------------------------------------------------
# Phase B: raise application
# -----------------------------------------------------------------------------

def _apply_lead_corrections(
    *,
    project_dir: Path,
    iteration_n: int,
    role: str,
    corrections: list[dict],
) -> None:
    """Lead's own raised corrections land in `<role>.corrections-pending.yaml`
    awaiting the architect's `lead_validate` verdict. Accepted ones move to
    `corrections.yaml` in architect Phase A; rejected ones move to
    `corrections-rejected.yaml`."""
    if not corrections:
        return
    own: list[dict] = []
    for i, c in enumerate(corrections):
        entry: dict[str, Any] = {
            "id": f"v84-{iteration_n}.{role}.lead.c.{i + 1}",
            "verdict": c["verdict"],
        }
        if c.get("action_id"):
            entry["action_id"] = c["action_id"]
        if c.get("task_id"):
            entry["task_id"] = c["task_id"]
        entry["correction"] = c["correction"]
        own.append(entry)
    proposals.append_pending_corrections(
        project_dir, iteration_n, role, own,
    )
    spinner.log(
        f"  ✓ {role}.corrections-pending.yaml +{len(own)} lead-authored "
        f"(awaiting architect verdict)"
    )


def _apply_lead_rules(
    *,
    project_dir: Path,
    iteration_n: int,
    role: str,
    rules: list[dict],
    parent_task_id: str,
) -> None:
    """Lead's own raised rules land in `<role>.rules.yaml` with
    `status: pending` awaiting the architect's `lead_validate` verdict.
    Accepted ones flip to `accepted` and synthesize an apply-correction
    in architect Phase A; rejected ones flip to `rejected`. The
    `parent_task_id` argument is preserved for signature compatibility
    with lead_round's caller — it is unused here since synth-correction
    generation moved to architect Phase A."""
    del parent_task_id  # unused after synth moved to architect Phase A
    if not rules:
        return
    rule_prefix = f"v84-{iteration_n}.{role}.lead.rule"
    existing_rules = proposals.read_rules(project_dir, iteration_n, role)
    new_rules = proposals.to_pending_rule_records(
        rules,
        id_prefix=rule_prefix,
        start_n=proposals.next_index_for_prefix(existing_rules, rule_prefix),
    )
    if not new_rules:
        return
    proposals.write_rules(
        project_dir, iteration_n, role,
        proposals.append_pending(existing_rules, new_rules),
    )
    spinner.log(
        f"  ✓ {role}.rules.yaml +{len(new_rules)} lead-authored "
        f"(pending architect verdict)"
    )


# -----------------------------------------------------------------------------
# Response parsing
# -----------------------------------------------------------------------------

_VERDICTS = {"accept", "reject"}
_CORRECTION_VERDICTS = {"fix", "missing", "remove"}


def _parse_verdicts(data: dict) -> dict:
    if not isinstance(data, dict):
        return {"correction_verdicts": [], "rule_verdicts": []}

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
        text = v.get("text")
        if isinstance(text, str) and text.strip():
            entry["text"] = text.strip()
        reason = v.get("reason")
        if isinstance(reason, str) and reason.strip():
            entry["reason"] = reason.strip()
        rule_verdicts.append(entry)

    return {
        "correction_verdicts": correction_verdicts,
        "rule_verdicts": rule_verdicts,
    }


def _parse_raises(data: dict) -> dict:
    if not isinstance(data, dict):
        data = {}
    return {
        "corrections": _norm_lead_corrections(data.get("corrections")),
        "rules": _norm_lead_rules(data.get("rules")),
    }


def _norm_lead_corrections(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for c in raw:
        if not isinstance(c, dict):
            continue
        verdict = c.get("verdict")
        if verdict not in _CORRECTION_VERDICTS:
            continue
        text = c.get("correction")
        if not isinstance(text, str) or not text.strip():
            continue
        entry: dict[str, Any] = {"verdict": verdict}
        if verdict == "missing":
            tid = c.get("task_id")
            if isinstance(tid, str) and tid.strip():
                entry["task_id"] = tid.strip()
        else:
            aid = c.get("action_id")
            if isinstance(aid, str) and aid.strip():
                entry["action_id"] = aid.strip()
        entry["correction"] = text.strip()
        out.append(entry)
    return out


def _norm_lead_rules(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        proposal = item.get("proposal")
        if not isinstance(proposal, str) or not proposal.strip():
            continue
        entry: dict[str, Any] = {"proposal": proposal.strip()}
        alts = item.get("alternatives")
        if isinstance(alts, list):
            cleaned = [str(a).strip() for a in alts if str(a).strip()]
            if cleaned:
                entry["alternatives"] = cleaned
        out.append(entry)
    return out


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _has_pending_rules(project_dir: Path, n: int, role: str) -> bool:
    return any(
        r.get("status") == "pending"
        for r in proposals.read_rules(project_dir, n, role)
    )


def _fan_out_cfg(project_dir: Path, *, fallback: LLMConfig) -> LLMConfig:
    try:
        return resolve_llm(
            project_dir=project_dir, tier="multi", interactive=False,
        )
    except Exception:
        return fallback
