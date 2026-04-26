"""
lead.py — Iteration lead stage (round 1, parallel per role).

For every active role, fan one lead call out. The lead reads:
    - iteration plan (plan_block)
    - role + stack
    - writer's draft for this role
    - merged suggestions from this role's 4 reviewers (with ids)
    - pending convention proposals (writer + reviewers, with ids)
    - pending decision proposals (writer + reviewers, with ids)

The lead emits verdicts (accept/reject + reason) on every
suggestion and every pending proposal, plus a corrections list
distilled from the accepted suggestions.

Outputs per role:
    iterations/<n>/<role>.corrections.yaml          corrections list
    iterations/<n>/<role>.corrections-rejected.yaml id + reason audit
    iterations/<n>/<role>.conventions.yaml          status updated in place
    iterations/<n>/<role>.decisions.yaml            status updated in place

Approved conv/dec stay in iteration-local files at this stage.
The user-review gate that promotes them to the project's main
folder runs at the architect/iteration-close step.

No resume — re-running rewrites all files.
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
    corrections_applied_block,
    corrections_rejected_block,
    plan_block,
    rejected_conventions_block,
    rejected_decisions_block,
)
from core.stage import Stage
from core.util import default_log_dir, instruction_path
from llm import CallSpec, LLMConfig, call_many, resolve_llm
from ui import MultiSpinner


def lead(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Run round-1 leads for every active role in parallel."""
    if cfg is None:
        raise ValueError("LLMConfig required — call via v84.py or pass cfg=")

    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        raise RuntimeError(
            "no current_iteration set in core.yaml — plan + draft + review first"
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

    plan = plan_block(parent)
    skill_file = instruction_path("iteration", "lead.md")
    if not skill_file.exists():
        raise FileNotFoundError(f"Instruction not found: {skill_file}")
    system = skill_file.read_text(encoding="utf-8")

    drafts_by_role = {
        role: (iter_dir / f"{role}.yaml").read_text(encoding="utf-8")
        for role in roles
        if (iter_dir / f"{role}.yaml").exists()
    }
    if len(drafts_by_role) != len(roles):
        missing = [r for r in roles if r not in drafts_by_role]
        raise RuntimeError(
            f"drafts missing for {missing} — run the draft + review stages first"
        )

    specs: list[CallSpec] = []
    labels: list[str] = []
    for role in roles:
        labels.append(role)
        specs.append(CallSpec(
            system=system,
            user_msgs=_build_user_msgs(
                project_dir=project_dir,
                role=role,
                iteration_n=iteration_n,
                plan=plan,
                draft_yaml=drafts_by_role[role],
                iter_dir=iter_dir,
            ),
            log_name=f"iter-{iteration_n}-lead-{role}",
        ))

    workers = min(fan_cfg.max_concurrency, len(specs))
    print(f"  leading {len(specs)} role(s) — model {fan_cfg.model} "
          f"@ {fan_cfg.url} (workers: {workers})",
          file=sys.stderr)
    with MultiSpinner(labels) as ms:
        results = call_many(
            fan_cfg, specs,
            log_dir=default_log_dir(),
            progress=ms,
        )

    failed: list[tuple[str, str]] = []
    for role, result in zip(roles, results):
        if result.error is not None:
            failed.append((role, repr(result.error)))
            continue
        _persist_lead_output(
            iter_dir=iter_dir,
            role=role,
            iteration_n=iteration_n,
            raw_response=result.response or "",
            project_dir=project_dir,
        )

    if failed:
        for role, err in failed:
            print(f"  ✗ {role}: {err}", file=sys.stderr)
        raise RuntimeError(
            f"{len(failed)} lead call(s) failed — re-run to retry"
        )

    iter_status.advance_to(project_dir, iteration_n, "architect")
    return iter_dir


# -----------------------------------------------------------------------------
# Per-role context builder
# -----------------------------------------------------------------------------

def _build_user_msgs(
    *,
    project_dir: Path,
    role: str,
    iteration_n: int,
    plan: str,
    draft_yaml: str,
    iter_dir: Path,
) -> list[str]:
    """Multi-message context for one lead call. Cached blocks
    (roles/stack/conv/dec/history) read once per iteration and
    reuse across stages — see core.cache."""
    msgs: list[str] = [
        f"## Iteration plan\n\n{plan}",
        f"## Your role\n\n{cached_roles_block(project_dir, role, iter_dir)}",
    ]

    stack = cached_stack_block(project_dir, role, iter_dir).strip()
    if stack:
        msgs.append(f"## Role stack\n\n{stack}")

    layout = cached_layout_block(project_dir, role, iter_dir).strip()
    if layout:
        msgs.append(f"## Role's repo layout\n\n{layout}")

    conv = cached_conventions_block(project_dir, role, iter_dir).strip()
    if conv:
        msgs.append(f"## Active conventions in scope\n\n{conv}")

    dec = cached_decisions_block(project_dir, role, iter_dir).strip()
    if dec:
        msgs.append(f"## Active decisions in scope\n\n{dec}")

    history = cached_role_history_block(project_dir, role, iter_dir).strip()
    if history:
        msgs.append(
            f"## Role's implementation history\n\n"
            f"What this role has shipped in past iterations. Use it "
            f"to keep verdicts consistent with what's already been "
            f"committed — don't accept suggestions that re-do past "
            f"work or contradict past decisions without a new reason.\n\n"
            f"{history}"
        )

    msgs.append(f"## Writer draft\n\n```yaml\n{draft_yaml.strip()}\n```")

    sugs = proposals.collect_role_suggestions(project_dir, iteration_n, role)
    msgs.append(
        f"## Reviewer suggestions ({len(sugs)})\n\n"
        f"```yaml\n{_dump(sugs)}\n```"
    )

    pending_conv = proposals.pending_conventions(project_dir, iteration_n, role)
    if pending_conv:
        msgs.append(
            f"## Pending convention proposals ({len(pending_conv)})\n\n"
            f"```yaml\n{_dump(pending_conv)}\n```"
        )

    pending_dec = proposals.pending_decisions(project_dir, iteration_n, role)
    if pending_dec:
        msgs.append(
            f"## Pending decision proposals ({len(pending_dec)})\n\n"
            f"```yaml\n{_dump(pending_dec)}\n```"
        )

    # Round 2+ context — empty on round 1 so naturally skipped.
    # Lead sees everything (no reviewer filter) since it owns
    # the role's full punch list.
    applied = corrections_applied_block(project_dir, role).strip()
    if applied:
        msgs.append(
            "## Corrections that was applied, do not re-raise them\n\n"
            f"{applied}"
        )

    rejected = corrections_rejected_block(project_dir, role).strip()
    if rejected:
        msgs.append(
            "## Corrections that was rejected, do not re-raise them\n\n"
            f"{rejected}"
        )

    rej_conv = rejected_conventions_block(project_dir, role=role).strip()
    if rej_conv:
        msgs.append(
            "## Conventions rejected this iteration\n\n"
            "Stay consistent with these dismissals — don't re-accept "
            "the same proposals (or close variants) without a "
            "materially new argument. Rejection reasons are recorded "
            "below.\n\n"
            f"{rej_conv}"
        )

    rej_dec = rejected_decisions_block(project_dir, role=role).strip()
    if rej_dec:
        msgs.append(
            "## Decisions rejected this iteration\n\n"
            "Same rule as rejected conventions — don't re-accept "
            "without a new argument.\n\n"
            f"{rej_dec}"
        )

    msgs.append(
        "Decide on every suggestion and every pending proposal. "
        "Follow your output format exactly."
    )
    return msgs


def _dump(items: list[dict]) -> str:
    return yaml.safe_dump(
        items,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=10000,
    ).rstrip()


# -----------------------------------------------------------------------------
# Output normalisation + persistence
# -----------------------------------------------------------------------------

def _persist_lead_output(
    *,
    iter_dir: Path,
    role: str,
    iteration_n: int,
    raw_response: str,
    project_dir: Path,
) -> None:
    """Parse the lead's YAML and split it across role-scoped files.

    - <role>.corrections.yaml           ← accepted reviewer suggestions
                                         (looked up by id from review
                                         files) PLUS the lead's own
                                         corrections, all carrying ids
                                         the architect can later reference.
    - <role>.corrections-rejected.yaml  ← suggestion_verdicts where
                                         verdict == reject (id + the
                                         original suggestion echoed as
                                         a `correction` field for audit),
                                         tagged `rejected_by: lead`.
                                         The architect appends to the
                                         same file with `rejected_by:
                                         architect` for cross-role
                                         conflicts.
    - <role>.conventions.yaml           ← updated in place via apply_verdicts.
    - <role>.decisions.yaml             ← same.
    """
    parsed = _parse(raw_response)

    # Look up every reviewer suggestion by id so we can echo accepted/
    # rejected ones into the harness-managed files.
    suggestions_by_id = {
        s["id"]: s
        for s in proposals.collect_role_suggestions(project_dir, iteration_n, role)
        if s.get("id")
    }

    accept_ids: list[str] = []
    reject_ids: list[str] = []
    for v in parsed["suggestion_verdicts"]:
        if v["verdict"] == "accept":
            accept_ids.append(v["id"])
        elif v["verdict"] == "reject":
            reject_ids.append(v["id"])

    # Build corrections file: every accepted reviewer suggestion (in
    # its original suggestion shape, renaming the prose field to
    # `correction`) followed by the lead's own corrections — those
    # get harness-assigned ids so the architect can reject them by
    # reference if needed.
    corrections: list[dict] = []
    for sid in accept_ids:
        s = suggestions_by_id.get(sid)
        if s is None:
            continue
        entry: dict[str, Any] = {"id": sid, "verdict": s.get("verdict")}
        if s.get("action_id"):
            entry["action_id"] = s["action_id"]
        if s.get("task_id"):
            entry["task_id"] = s["task_id"]
        entry["correction"] = s.get("suggestion", "")
        corrections.append(entry)
    for i, c in enumerate(parsed["corrections"]):
        own: dict[str, Any] = {
            "id": f"v84-{iteration_n}.{role}.lead.c.{i + 1}",
            "verdict": c["verdict"],
        }
        if c.get("action_id"):
            own["action_id"] = c["action_id"]
        if c.get("task_id"):
            own["task_id"] = c["task_id"]
        own["correction"] = c["correction"]
        corrections.append(own)

    corrections_file = iter_dir / f"{role}.corrections.yaml"
    corrections_file.write_text(_dump_block(corrections), encoding="utf-8")
    print(
        f"  ✓ {corrections_file} "
        f"({len(corrections)} corrections: "
        f"{len(accept_ids)} accepted + "
        f"{len(parsed['corrections'])} lead-authored)",
        file=sys.stderr,
    )

    # Rejected file: id + echoed original suggestion text (audit),
    # tagged `rejected_by: lead`. The architect can later append
    # entries with `rejected_by: architect` to the same file.
    rejected: list[dict] = []
    for sid in reject_ids:
        s = suggestions_by_id.get(sid)
        if s is None:
            rejected.append({"id": sid, "rejected_by": "lead"})
            continue
        entry: dict[str, Any] = {"id": sid, "verdict": s.get("verdict")}
        if s.get("action_id"):
            entry["action_id"] = s["action_id"]
        if s.get("task_id"):
            entry["task_id"] = s["task_id"]
        entry["correction"] = s.get("suggestion", "")
        entry["rejected_by"] = "lead"
        rejected.append(entry)

    rejected_file = iter_dir / f"{role}.corrections-rejected.yaml"
    rejected_file.write_text(_dump_block(rejected), encoding="utf-8")
    print(
        f"  ✓ {rejected_file} ({len(rejected)} rejected)",
        file=sys.stderr,
    )

    if parsed["convention_verdicts"]:
        recs = proposals.read_conventions(project_dir, iteration_n, role)
        proposals.apply_verdicts(recs, parsed["convention_verdicts"])
        proposals.write_conventions(project_dir, iteration_n, role, recs)
        print(f"  ✓ {role}.conventions.yaml updated", file=sys.stderr)

    if parsed["decision_verdicts"]:
        recs = proposals.read_decisions(project_dir, iteration_n, role)
        proposals.apply_verdicts(recs, parsed["decision_verdicts"])
        proposals.write_decisions(project_dir, iteration_n, role, recs)
        print(f"  ✓ {role}.decisions.yaml updated", file=sys.stderr)

    # Lead-authored raises — settle directly as accepted because lead
    # is the authority for role-scoped rules. Numbering continues
    # past existing entries so ids don't collide with writer/reviewer
    # raises in the same file.
    if parsed["needs_convention"]:
        conv_prefix = f"v84-{iteration_n}.{role}.lead.conv"
        existing_conv = proposals.read_conventions(project_dir, iteration_n, role)
        new_conv = proposals.to_accepted_records(
            parsed["needs_convention"],
            id_prefix=conv_prefix,
            start_n=proposals.next_index_for_prefix(existing_conv, conv_prefix),
        )
        if new_conv:
            proposals.write_conventions(
                project_dir, iteration_n, role,
                proposals.append_pending(existing_conv, new_conv),
            )
            print(
                f"  ✓ {role}.conventions.yaml +{len(new_conv)} lead-authored "
                f"(accepted instantly)",
                file=sys.stderr,
            )

    if parsed["needs_decision"]:
        dec_prefix = f"v84-{iteration_n}.{role}.lead.dec"
        existing_dec = proposals.read_decisions(project_dir, iteration_n, role)
        new_dec = proposals.to_accepted_records(
            parsed["needs_decision"],
            id_prefix=dec_prefix,
            start_n=proposals.next_index_for_prefix(existing_dec, dec_prefix),
        )
        if new_dec:
            proposals.write_decisions(
                project_dir, iteration_n, role,
                proposals.append_pending(existing_dec, new_dec),
            )
            print(
                f"  ✓ {role}.decisions.yaml +{len(new_dec)} lead-authored "
                f"(accepted instantly)",
                file=sys.stderr,
            )


def _dump_block(data: Any) -> str:
    """Block-scalar friendly YAML dump."""
    return yaml.safe_dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=10000,
    )


_VERDICTS = {"accept", "reject"}


def _parse(yaml_text: str) -> dict:
    """Permissive parse of the lead's response.

    Returns a dict with four normalised lists:
        suggestion_verdicts, convention_verdicts, decision_verdicts, corrections
    """
    try:
        data = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError:
        data = {}
    if not isinstance(data, dict):
        data = {}

    return {
        "suggestion_verdicts": _norm_verdicts(
            data.get("suggestion_verdicts"), needs_form=False,
        ),
        "convention_verdicts": _norm_verdicts(
            data.get("convention_verdicts"), needs_form=True,
        ),
        "decision_verdicts": _norm_verdicts(
            data.get("decision_verdicts"), needs_form=True,
        ),
        "corrections": _norm_corrections(data.get("corrections")),
        "needs_convention": _norm_lead_raises(data.get("needs_convention")),
        "needs_decision": _norm_lead_raises(data.get("needs_decision")),
    }


def _norm_lead_raises(raw: Any) -> list[dict]:
    """Lead-authored conv/dec raises. Each entry is
    `{proposal, alternatives}` — same shape as reviewer raises so
    user_review has the full context (lead's preferred form + the
    alternatives lead considered) at promotion time. In-iteration
    they auto-promote to accepted (lead is the role's authority);
    user is the final gate at iteration close.
    """
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


def _norm_verdicts(raw: Any, *, needs_form: bool) -> list[dict]:
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
        entry: dict[str, Any] = {
            "id": rid.strip(),
            "verdict": verdict,
        }
        if needs_form and verdict == "accept":
            form = v.get("rule")
            if isinstance(form, str) and form.strip():
                entry["rule"] = form.strip()
        if needs_form and verdict == "reject":
            reason = v.get("reason")
            if isinstance(reason, str) and reason.strip():
                entry["reason"] = reason.strip()
        out.append(entry)
    return out


_CORRECTION_VERDICTS = {"fix", "missing", "remove"}


def _norm_corrections(raw: Any) -> list[dict]:
    """Lead's own corrections — suggestion-shape entries."""
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
    """Done when status.yaml says next_step has moved past `lead`."""
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        return False
    iteration_n = _iteration_number(parent_id)
    return iter_status.stage_is_done(project_dir, iteration_n, "lead")


STAGE = Stage(
    name="lead",
    title="Lead synthesises reviewers + proposals per role",
    priority=1301,
    produces="iterations/<n>/<role>.corrections.yaml",
    requires=("review",),
    needs_brief=False,
    is_done=_is_done,
    call=lead,
)
