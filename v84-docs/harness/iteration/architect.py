"""
architect.py — Iteration architect stage (parallel raise + verdict).

Once every active role has its lead output (corrections + accepted
rules), the architect fires TWO LLM calls in parallel — both see
the same pre-vote disk state — then applies the outputs in two
phases:

    1. Raise call (architect.md). Cross-role corrections + global
       rule proposals + ids of lead corrections to override. The
       architect's view of what is missing or broken across roles.

    2. Verdict call (lead_validate.md). Rejection-only ballot
       over role-scoped rules that landed accepted in this
       iteration's lead_round (reviewer-raised rules the lead
       accepted + lead-raised rules that auto-accepted). Silence
       means the lead's authority stands; reject only when there
       is a concrete cross-role break.

Two-phase write applies the verdicts first (Phase A — flip
rejected lead rules + retract their synthetic apply-corrections),
then the raises (Phase B — append cross-role corrections to each
role's pending file, move rejected lead corrections, write
proposed globals as pending).

Outputs:

    iterations/<n>/<role>.corrections-pending.yaml
        — architect's cross-role corrections appended per role
          (id `v84-<n>.architect.c.<m>`; role inferred from
          `action_id` prefix or `for_role`). architect_validate
          fans out to each affected role's lead to vote
          accept/reject; accepted entries land in
          `<role>.corrections.yaml`, rejected in
          `<role>.corrections-rejected.yaml`.
    iterations/<n>/<role>.corrections-rejected.yaml
        — lead corrections the architect overrides; moved here
          from `<role>.corrections.yaml` with `rejected_by: architect`.
    iterations/<n>/<role>.rules.yaml
        — lead-rule status flipped from accepted → rejected for
          every entry the verdict call named, with rejected_by:
          architect and rejection_reason recorded. The matching
          synthetic `<rule_id>.apply` correction is also retracted
          from the role's corrections.yaml so patch doesn't carry
          a now-rejected rule forward.
    iterations/<n>/global.rules.yaml
        — pending architect-proposed global rules.

No separate `architect.yaml` is written — whether the iteration
continues or closes is decided by architect_validate from the
on-disk corrections count and recorded in `status.yaml`.

Two-call fan-out via call_many; the multi tier is used when
configured (else single).
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


def architect(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Run the iteration's architect stage — parallel raise + verdict."""
    if cfg is None:
        raise ValueError("LLMConfig required — call via v84.py or pass cfg=")

    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        raise RuntimeError(
            "no current_iteration set in core.yaml — run plan + draft + "
            "review + lead first"
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

    # Both calls run on the multi tier when configured, else single.
    fan_cfg = _arch_cfg(project_dir, fallback=cfg)

    raise_system,   raise_schema   = load_instruction("iteration", "architect")
    verdict_system, verdict_schema = load_instruction("iteration", "lead_validate")

    # Both calls see the SAME pre-vote disk state. The verdict call's
    # bundle includes per-role accepted rules (the items it votes on);
    # the raise call's bundle is identical so cross-role concerns can
    # cite the same rule set without drift between halves.
    raise_msgs = build_user_msgs(
        project_dir, parent, iteration_n,
        {
            "plan":                          True,
            "active_roles":                  True,
            "stack":                         "all",
            "layout":                        ["global"],
            "role_definition":               "all",
            "history":                       None,
            "actions":                       "all",
            "corrections":                   "all",
            "corrections_pending":           None,
            "corrections_rejected":          "all",
            "corrections_applied":           None,
            "corrections_rejected_history":  None,
            "rules":                         ["global"] + roles,
            "rules_pending":                 None,
            "rules_rejected":                ["global"],
            "trailing": "Synthesise across roles.",
        },
    )

    verdict_msgs = build_user_msgs(
        project_dir, parent, iteration_n,
        {
            "plan":                          True,
            "active_roles":                  True,
            "stack":                         "all",
            "layout":                        ["global"],
            "role_definition":               "all",
            "history":                       None,
            "actions":                       "all",
            "corrections":                   "all",
            "corrections_pending":           None,
            "corrections_rejected":          "all",
            "corrections_applied":           None,
            "corrections_rejected_history":  None,
            "rules":                         ["global"] + roles,
            "rules_pending":                 None,
            "rules_rejected":                ["global"],
            "trailing": (
                "Vote rejection-only on role-scoped rules that landed "
                "accepted in this iteration. Silence is the common case — "
                "leads' authority stands by default."
            ),
        },
    )

    # Skip the verdict call when there's nothing in scope to vote on
    # — no lead-blessed pending corrections (non-architect ids) and
    # no pending or accepted role rules across any active role.
    has_verdict_scope = _has_lead_validate_scope(
        project_dir, iteration_n, roles,
    )

    specs: list[CallSpec] = [
        CallSpec(
            system=raise_system,
            user_msgs=raise_msgs,
            response_schema=raise_schema,
            log_name=f"iter-{iteration_n}-architect-raise",
        ),
    ]
    kinds: list[str] = ["raise"]
    if has_verdict_scope:
        specs.append(CallSpec(
            system=verdict_system,
            user_msgs=verdict_msgs,
            response_schema=verdict_schema,
            log_name=f"iter-{iteration_n}-architect-verdict",
        ))
        kinds.append("verdict")

    if has_verdict_scope:
        spinner.log(
            f"  architecting iteration {iteration_n} — raise + verdict "
            f"in parallel — model {fan_cfg.model} @ {fan_cfg.url}"
        )
    else:
        spinner.log(
            f"  architecting iteration {iteration_n} — raise only "
            f"(nothing in scope for verdict) — model {fan_cfg.model} "
            f"@ {fan_cfg.url}"
        )
    results = call_many(fan_cfg, specs, log_dir=default_log_dir())

    raise_response: dict = {}
    verdict_response: dict = {}
    failed: list[tuple[str, str]] = []
    for kind, result in zip(kinds, results):
        if result.error is not None:
            failed.append((kind, repr(result.error)))
            continue
        if kind == "raise":
            raise_response = result.response or {}
        else:
            verdict_response = result.response or {}

    if failed:
        for kind, err in failed:
            spinner.log(f"  ✗ architect.{kind}: {err}")
        raise RuntimeError(
            f"architect failed: {len(failed)} call(s) — re-run to retry"
        )

    # Phase A — apply lead_validate verdicts on lead corrections and
    # role-scoped rules in scope. Lead-raised pending items transition
    # to accepted (corrections.yaml + synth apply-correction for rules)
    # or rejected; reviewer-source items already accepted by the lead
    # stay binding on accept and move to rejected on reject.
    correction_verdicts = _norm_correction_verdicts(verdict_response)
    rule_verdicts = _norm_rule_verdicts(verdict_response)
    parent_task_id = parent_id

    if correction_verdicts:
        _apply_lead_correction_verdicts(
            project_dir=project_dir,
            iteration_n=iteration_n,
            roles=roles,
            verdicts=correction_verdicts,
        )
    if rule_verdicts:
        _apply_lead_rule_verdicts(
            project_dir=project_dir,
            iteration_n=iteration_n,
            roles=roles,
            verdicts=rule_verdicts,
            parent_task_id=parent_task_id,
        )

    # Phase B — apply raises: cross-role corrections + global proposals.
    _persist_architect_output(
        iter_dir=iter_dir,
        iteration_n=iteration_n,
        roles=roles,
        response=raise_response,
        project_dir=project_dir,
    )

    # architect_validate decides whether the cycle continues or ends —
    # architect just hands off. If it finds corrections to apply,
    # round++ and patch starts the new cycle; otherwise next_step=
    # user_review.
    iter_status.advance_to(project_dir, iteration_n, "architect_validate")
    return iter_dir


# -----------------------------------------------------------------------------
# Output persistence
# -----------------------------------------------------------------------------

def _persist_architect_output(
    *,
    iter_dir: Path,
    iteration_n: int,
    roles: list[str],
    response: dict,
    project_dir: Path,
) -> bool:
    """Persist architect raise outputs (cross-role corrections + global
    rule proposals) and return whether another round is needed.
    Lead-correction rejections + lead-rule rejections come from the
    parallel verdict call and are applied separately in Phase A."""
    parsed = _parse(response)

    needs_round = bool(parsed["corrections"] or parsed["rules"])

    # Architect's cross-role corrections land in each affected role's
    # PENDING file. The validate stage then fans out to that role's
    # lead to vote accept/reject; only accepted ones become a real
    # punch-list entry. Role comes from `action_id` prefix (fix/remove)
    # or from `for_role` (missing). Each correction gets an
    # architect-prefixed id so its source is greppable.
    by_role: dict[str, list[dict]] = {}
    skipped: list[dict] = []
    for i, c in enumerate(parsed["corrections"]):
        target_role: Optional[str] = None
        if c.get("verdict") == "missing":
            target_role = c.get("for_role")
        else:
            aid = c.get("action_id") or ""
            target_role = _role_from_correction_id(aid, roles)
        if target_role is None or target_role not in roles:
            skipped.append(c)
            continue

        entry: dict[str, Any] = {
            "id": f"v84-{iteration_n}.architect.c.{i + 1}",
            "verdict": c["verdict"],
        }
        if c.get("action_id"):
            entry["action_id"] = c["action_id"]
        if c.get("task_id"):
            entry["task_id"] = c["task_id"]
        entry["correction"] = c["correction"]
        by_role.setdefault(target_role, []).append(entry)

    for role, additions in by_role.items():
        proposals.append_pending_corrections(
            project_dir, iteration_n, role, additions,
        )
        spinner.log(
            f"  ✓ {role}.corrections-pending.yaml +{len(additions)} "
            f"from architect (lead validation in validate stage)"
        )
    if skipped:
        spinner.log(
            f"  ✗ {len(skipped)} architect correction(s) skipped — "
            f"role unresolved"
        )

    # Architect's proposed rules → iteration global pending store.
    rule_records = proposals.to_pending_rule_records(
        parsed["rules"],
        id_prefix=f"v84-{iteration_n}.architect.rule",
    )
    if rule_records:
        proposals.write_rules(project_dir, iteration_n, "global", rule_records)
        spinner.log(
            f"  ✓ {iter_dir / 'global.rules.yaml'} "
            f"({len(rule_records)} proposed)"
        )

    return needs_round


# -----------------------------------------------------------------------------
# Pre-flight: is there anything for lead_validate to vote on?
# -----------------------------------------------------------------------------

def _has_lead_validate_scope(
    project_dir: Path, iteration_n: int, roles: list[str],
) -> bool:
    """Return True iff at least one role has something in scope for
    the verdict call: a lead-blessed pending correction (id NOT
    containing `architect.c.`) OR any pending / accepted rule."""
    for role in roles:
        # Lead-blessed pending corrections.
        for c in proposals.read_pending_corrections(
            project_dir, iteration_n, role,
        ):
            cid = c.get("id") or ""
            if cid and "architect.c." not in cid:
                return True
        # Pending or accepted rules.
        for r in proposals.read_rules(project_dir, iteration_n, role):
            if r.get("status") in ("pending", "accepted"):
                return True
    return False


# -----------------------------------------------------------------------------
# Phase A: apply lead_validate verdicts (lead corrections + role rules)
# -----------------------------------------------------------------------------

def _apply_lead_correction_verdicts(
    *,
    project_dir: Path,
    iteration_n: int,
    roles: list[str],
    verdicts: list[dict],
) -> None:
    """Apply architect verdicts on lead-blessed corrections in scope.

    The verdict scope covers items in `<role>.corrections-pending.yaml`
    that are lead-blessed (reviewer-source the lead accepted, plus
    lead's own raises) — architect cross-role corrections in the same
    file are voted on later by `architect_validate` and excluded here
    by id pattern.

    Per-verdict transition:
    - `accept` → record moves from pending to `<role>.corrections.yaml`
                  (now binding for patch).
    - `reject` → record moves from pending to
                  `<role>.corrections-rejected.yaml` tagged
                  `rejected_by: architect`.
    """
    by_role: dict[str, dict[str, dict]] = {}   # role -> {id: verdict}
    orphan = 0
    for v in verdicts:
        cid = v.get("id")
        if not cid or "architect.c." in cid:
            # Architect-source corrections are handled by
            # architect_validate, not lead_validate. Skip.
            continue
        role = _role_from_correction_id(cid, roles)
        if role is None:
            orphan += 1
            continue
        by_role.setdefault(role, {})[cid] = v

    if orphan:
        spinner.log(
            f"  ✗ {orphan} lead_validate correction verdict(s) skipped — "
            f"role unresolved"
        )

    for role, vmap in by_role.items():
        pending = proposals.read_pending_corrections(
            project_dir, iteration_n, role,
        )
        keep_pending: list[dict] = []
        accepted: list[dict] = []
        rejected: list[dict] = []
        for rec in pending:
            v = vmap.get(rec.get("id"))
            if v is None:
                keep_pending.append(rec)
                continue
            if v["verdict"] == "accept":
                accepted.append(rec)
            else:
                rec_out = dict(rec)
                rec_out["rejected_by"] = "architect"
                if v.get("reason"):
                    rec_out["rejection_reason"] = v["reason"]
                rejected.append(rec_out)

        # Move accepted records into corrections.yaml (binding) and
        # rejected ones into corrections-rejected.yaml. Pending file
        # is rewritten without either set so only items still
        # awaiting their verdict (architect cross-role) remain.
        if accepted:
            existing = proposals.read_corrections(
                project_dir, iteration_n, role,
            )
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
        proposals.write_pending_corrections(
            project_dir, iteration_n, role, keep_pending,
        )
        spinner.log(
            f"  ✓ {role}: lead corrections — {len(accepted)} accepted "
            f"by architect → corrections.yaml, {len(rejected)} rejected"
        )


def _apply_lead_rule_verdicts(
    *,
    project_dir: Path,
    iteration_n: int,
    roles: list[str],
    verdicts: list[dict],
    parent_task_id: str,
) -> None:
    """Apply architect verdicts on role-scoped rules in scope.

    Verdict scope covers any rule the leads have blessed:
    - status: pending records (lead-blessed reviewer raises + lead's
      own raises). Accept → flip to accepted + synthesize apply-
      correction so patch picks up the new binding. Reject → flip to
      rejected.
    - status: accepted records (older accepted rules still binding
      from earlier rounds). Accept → no-op. Reject → flip to rejected
      and retract the rule's synthetic apply-correction so patch
      doesn't carry a now-rejected rule forward.

    Records with no matching verdict are untouched. Records in other
    statuses (rejected, superseded) are out of scope.
    """
    grouped: dict[str, dict[str, dict]] = {}
    orphan = 0
    for v in verdicts:
        rid = v.get("id")
        role = _role_from_correction_id(rid or "", roles)
        if role is None:
            orphan += 1
            continue
        grouped.setdefault(role, {})[rid] = v

    if orphan:
        spinner.log(
            f"  ✗ {orphan} lead_validate rule verdict(s) skipped — "
            f"role unresolved"
        )

    for role, vmap in grouped.items():
        records = proposals.read_rules(project_dir, iteration_n, role)
        accepted_ids: list[str] = []
        rejected_ids: list[str] = []
        for r in records:
            rid = r.get("id")
            v = vmap.get(rid)
            if v is None:
                continue
            status = r.get("status")
            verdict = v["verdict"]
            if status == "pending":
                if verdict == "accept":
                    r["status"] = "accepted"
                    # Lead's preferred wording (recorded in
                    # apply_lead_verdicts during lead_round) lives in
                    # `text`; preserve it. Fall back to proposal if
                    # somehow absent.
                    if not r.get("text"):
                        r["text"] = (r.get("proposal") or "").strip()
                    r.pop("rejection_reason", None)
                    accepted_ids.append(rid)
                else:
                    r["status"] = "rejected"
                    r["rejected_by"] = "architect"
                    if v.get("reason"):
                        r["rejection_reason"] = v["reason"]
                    r.pop("text", None)
                    rejected_ids.append(rid)
            elif status == "accepted":
                if verdict == "reject":
                    r["status"] = "rejected"
                    r["rejected_by"] = "architect"
                    if v.get("reason"):
                        r["rejection_reason"] = v["reason"]
                    r.pop("text", None)
                    rejected_ids.append(rid)
                # accept on already-accepted = no-op
            # other statuses (rejected, superseded) untouched
        if accepted_ids or rejected_ids:
            proposals.write_rules(project_dir, iteration_n, role, records)

        # For newly-accepted rules, synthesize apply-corrections so
        # patch (next round) updates the role's draft to comply.
        synth_added = 0
        for rid in accepted_ids:
            rec = next((r for r in records if r.get("id") == rid), None)
            if rec is None:
                continue
            rule_text = rec.get("text") or rec.get("proposal") or ""
            synth = proposals.synthesize_apply_correction(
                rule_id=rid,
                rule_text=rule_text,
                parent_task_id=parent_task_id,
                scope="role",
            )
            if proposals.append_synthetic_correction(
                project_dir, iteration_n, role, synth,
            ):
                synth_added += 1

        # For newly-rejected rules that were previously accepted,
        # retract any synthetic apply-correction in the role's
        # corrections.yaml so patch doesn't carry the rule forward.
        retracted = _retract_apply_corrections(
            project_dir, iteration_n, role, rejected_ids,
        )

        msg_parts = []
        if accepted_ids:
            msg_parts.append(f"{len(accepted_ids)} accepted")
        if rejected_ids:
            msg_parts.append(f"{len(rejected_ids)} rejected")
        if msg_parts:
            extra = []
            if synth_added:
                extra.append(f"{synth_added} synth apply added")
            if retracted:
                extra.append(f"{retracted} synth apply retracted")
            tail = f" ({', '.join(extra)})" if extra else ""
            spinner.log(
                f"  ✓ {role}: rules — {', '.join(msg_parts)} by architect{tail}"
            )


def _retract_apply_corrections(
    project_dir: Path,
    iteration_n: int,
    role: str,
    rule_ids,
) -> int:
    """Drop entries with id `<rule_id>.apply` from <role>.corrections.yaml.
    Returns count removed. The `.apply` suffix matches what
    proposals.synthesize_apply_correction emits in lead_round."""
    target_ids = {f"{rid}.apply" for rid in rule_ids}
    if not target_ids:
        return 0
    existing = proposals.read_corrections(project_dir, iteration_n, role)
    keep = [c for c in existing if c.get("id") not in target_ids]
    removed = len(existing) - len(keep)
    if removed:
        proposals.write_corrections(project_dir, iteration_n, role, keep)
    return removed


def _norm_rule_verdicts(data: dict) -> list[dict]:
    """lead_validate response's `rules` → list of full
    `{id, verdict, reason?}` verdicts. Both accepts and rejects are
    kept — accept transitions pending → accepted (synth apply-
    correction generated); reject transitions to rejected."""
    return _norm_full_verdicts(data, "rules")


def _norm_correction_verdicts(data: dict) -> list[dict]:
    """lead_validate response's `corrections` → list of full
    `{id, verdict, reason?}` verdicts. Accept moves the lead-blessed
    correction from pending to corrections.yaml; reject moves it to
    corrections-rejected.yaml."""
    return _norm_full_verdicts(data, "corrections")


def _norm_full_verdicts(data: dict, key: str) -> list[dict]:
    """Schema-validated upstream; just normalise whitespace and filter
    invalid rows."""
    if not isinstance(data, dict):
        return []
    raw = data.get(key)
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        rid = (r.get("id") or "").strip()
        verdict = r.get("verdict")
        if not rid or verdict not in ("accept", "reject"):
            continue
        entry: dict[str, Any] = {"id": rid, "verdict": verdict}
        reason = r.get("reason")
        if isinstance(reason, str) and reason.strip():
            entry["reason"] = reason.strip()
        out.append(entry)
    return out


def _role_from_correction_id(cid: str, roles: list[str]) -> Optional[str]:
    """A correction id encodes its role somewhere in the dotted path.

    Lead's accepted reviewer correction ids:  v84-1.frontend.pages.c.3
    Lead's own correction ids:                v84-1.frontend.lead.c.1
    Either way, the role tag appears as a token in the dotted id.
    """
    parts = cid.split(".")
    for tok in parts:
        if tok in roles:
            return tok
    return None


# -----------------------------------------------------------------------------
# Parsing
# -----------------------------------------------------------------------------

_CORRECTION_VERDICTS = {"fix", "missing", "remove"}


def _parse(data: dict) -> dict:
    """Architect raise response is `{corrections, rules}`, already
    shape-validated by the response_format schema. Just sanity-filter
    rows. Rejection of lead corrections / lead-raised rules lives in
    the parallel verdict call's response, not here."""
    if not isinstance(data, dict):
        data = {}

    return {
        "corrections": _norm_corrections(data.get("corrections")),
        "rules": _norm_proposals(data.get("rules")),
    }


def _norm_corrections(raw: Any) -> list[dict]:
    """Architect cross-role corrections. Schema validation upstream
    enforces shape — no permissive aliases here."""
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
        entry: dict[str, Any] = {"verdict": verdict, "correction": text.strip()}
        if verdict == "missing":
            tid = c.get("task_id")
            if isinstance(tid, str) and tid.strip():
                entry["task_id"] = tid.strip()
            for_role = c.get("for_role")
            if isinstance(for_role, str) and for_role.strip():
                entry["for_role"] = for_role.strip()
        else:
            aid = c.get("action_id")
            if isinstance(aid, str) and aid.strip():
                entry["action_id"] = aid.strip()
        out.append(entry)
    return out


def _norm_proposals(raw: Any) -> list[dict]:
    """Same shape as writer/reviewer/lead proposals: {proposal, alternatives}."""
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
# Tier resolution + helpers
# -----------------------------------------------------------------------------

def _arch_cfg(project_dir: Path, *, fallback: LLMConfig) -> LLMConfig:
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
    """Done when status.yaml says next_step has moved past `architect`
    (either to `done` after approval, or to `draft` for round 2)."""
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        return False
    iteration_n = _iteration_number(parent_id)
    return iter_status.stage_is_done(project_dir, iteration_n, "architect")


STAGE = Stage(
    name="architect",
    title="Architect synthesises cross-role",
    priority=1401,
    produces="iterations/<n>/status.yaml#next_step",
    requires=("cycle",),
    needs_brief=False,
    is_done=_is_done,
    call=architect,
)
