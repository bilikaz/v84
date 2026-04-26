"""
architect.py — Iteration architect stage (single cross-role call).

Once every active role has its lead output (corrections + accepted
conv/dec), one architect call reads everything cross-role and
emits:

    - verdict: approved | continue
    - cross-role corrections (suggestion shape, optional `for_role`)
    - rejected_corrections — ids from any lead's corrections file
      that the architect overrides
    - proposed global conventions (architect-authored, scope=global)
    - proposed global decisions (architect-authored)

Outputs:

    iterations/<n>/<role>.corrections.yaml
        — architect's cross-role corrections appended per role
          (id `v84-<n>.architect.c.<m>`; role inferred from
          `action_id` prefix or `for_role`)
    iterations/<n>/<role>.corrections-rejected.yaml
        — lead corrections the architect overrides; moved here
          from `<role>.corrections.yaml` with `rejected_by: architect`
    iterations/<n>/global.conventions.yaml
        — pending architect-proposed global conventions
    iterations/<n>/global.decisions.yaml
        — pending architect-proposed global decisions

No separate `architect.yaml` is written — whether the iteration
continues or closes is decided by the validate stage from the
on-disk corrections count and recorded in `status.yaml`.

No fan-out — single LLM call. Multi-tier still used so the call
goes to the architect tier when configured.
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
    plan_block,
    project_layout_block,
    rejected_conventions_block,
    rejected_decisions_block,
    roles_block,
    stack_block,
)
from core.stage import Stage
from core.util import default_log_dir, instruction_path
from llm import LLMConfig, call, resolve_llm
from ui import Spinner


def architect(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Run the iteration's architect call."""
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

    # Architect runs on the multi tier when configured, else single.
    arch_cfg = _arch_cfg(project_dir, fallback=cfg)

    skill_file = instruction_path("iteration", "architect.md")
    if not skill_file.exists():
        raise FileNotFoundError(f"Instruction not found: {skill_file}")
    system = skill_file.read_text(encoding="utf-8")

    user_msgs = _build_user_msgs(
        project_dir=project_dir,
        roles=roles,
        iteration_n=iteration_n,
        parent=parent,
    )

    print(f"  architecting iteration {iteration_n} — model {arch_cfg.model} "
          f"@ {arch_cfg.url}",
          file=sys.stderr)
    with Spinner(f"calling {arch_cfg.model} @ {arch_cfg.url}"):
        response = call(
            arch_cfg,
            system=system,
            user_msgs=user_msgs,
            log_name=f"iter-{iteration_n}-architect",
            log_dir=default_log_dir(),
        )

    _persist_architect_output(
        iter_dir=iter_dir,
        iteration_n=iteration_n,
        roles=roles,
        raw_response=response,
        project_dir=project_dir,
    )
    # Validate decides whether the cycle continues or ends — architect
    # just hands off. If validate finds corrections to apply, round++
    # and patch starts the new cycle; otherwise next_step=user_review.
    iter_status.advance_to(project_dir, iteration_n, "validate")
    return iter_dir


# -----------------------------------------------------------------------------
# Context builder
# -----------------------------------------------------------------------------

def _build_user_msgs(
    *,
    project_dir: Path,
    roles: list[str],
    iteration_n: int,
    parent: dict,
) -> list[str]:
    """Multi-message context for the architect call."""
    msgs: list[str] = [
        f"## Iteration plan\n\n{plan_block(parent)}",
        f"## Active roles\n\n{', '.join(roles)}",
        f"## Stack (full)\n\n{stack_block(project_dir, roles=roles)}",
    ]
    layout = project_layout_block(project_dir).strip()
    if layout:
        msgs.append(f"## Repo layout (all roles)\n\n{layout}")

    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)

    for role in roles:
        bundle = _role_bundle(iter_dir, role, project_dir, iteration_n)
        msgs.append(f"## Role bundle: {role}\n\n{bundle}")

    # Active globals — same context.conventions_block helper every
    # other layer uses. role=None so only globals appear (not the
    # role-scoped accepted from iteration role files, which are
    # already included in each role bundle above).
    conv = conventions_block(project_dir, role=None).strip()
    if conv:
        msgs.append(f"## Active global conventions\n\n{conv}")
    dec = decisions_block(project_dir, role=None).strip()
    if dec:
        msgs.append(f"## Active global decisions\n\n{dec}")

    # Rejected globals from earlier rounds — surfaced with their
    # rejection reasons so the architect doesn't re-propose ideas
    # that leads have already shot down. Empty on round 1.
    rej_conv = rejected_conventions_block(project_dir, role=None).strip()
    if rej_conv:
        msgs.append(
            "## Global conventions rejected this iteration\n\n"
            "These global proposals were rejected by lead validation. "
            "Don't re-propose them in this form. If you still believe "
            "the underlying concern is real, address the rejection "
            "reason in your reworded proposal — or drop the idea.\n\n"
            f"{rej_conv}"
        )
    rej_dec = rejected_decisions_block(project_dir, role=None).strip()
    if rej_dec:
        msgs.append(
            "## Global decisions rejected this iteration\n\n"
            "Same rule as rejected conventions — don't re-propose "
            "without addressing the recorded reason.\n\n"
            f"{rej_dec}"
        )

    msgs.append(
        "Synthesise across roles. Follow your output format exactly."
    )
    return msgs


def _role_bundle(
    iter_dir: Path, role: str, project_dir: Path, iteration_n: int,
) -> str:
    """Render every artefact the architect needs for one role."""
    sections: list[str] = []

    draft_file = iter_dir / f"{role}.yaml"
    if draft_file.exists():
        sections.append(
            f"### writer draft (`{role}.yaml`)\n\n"
            f"```yaml\n{draft_file.read_text(encoding='utf-8').strip()}\n```"
        )

    corr = proposals.read_corrections(project_dir, iteration_n, role)
    if corr:
        sections.append(
            f"### lead corrections (`{role}.corrections.yaml`)\n\n"
            f"```yaml\n{_dump(corr).rstrip()}\n```"
        )

    rejected = proposals.read_rejected_corrections(project_dir, iteration_n, role)
    if rejected:
        sections.append(
            f"### lead rejected corrections (`{role}.corrections-rejected.yaml`)\n\n"
            f"```yaml\n{_dump(rejected).rstrip()}\n```"
        )

    accepted_c = proposals.accepted_conventions(project_dir, iteration_n, role)
    if accepted_c:
        sections.append(
            f"### accepted role conventions (this iteration)\n\n"
            f"```yaml\n{_dump(accepted_c).rstrip()}\n```"
        )

    accepted_d = proposals.accepted_decisions(project_dir, iteration_n, role)
    if accepted_d:
        sections.append(
            f"### accepted role decisions (this iteration)\n\n"
            f"```yaml\n{_dump(accepted_d).rstrip()}\n```"
        )

    if not sections:
        return "(no artefacts present for this role)"
    return "\n\n".join(sections)


def _dump(data: Any) -> str:
    return yaml.safe_dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=10000,
    )


# -----------------------------------------------------------------------------
# Output persistence
# -----------------------------------------------------------------------------

def _persist_architect_output(
    *,
    iter_dir: Path,
    iteration_n: int,
    roles: list[str],
    raw_response: str,
    project_dir: Path,
) -> bool:
    """Persist all architect outputs and return whether another round
    is needed (any corrections, rejections, or proposals emitted)."""
    parsed = _parse(raw_response)

    # Verdict is derived from emitted content: anything that requires
    # the writers to patch (own corrections, rejected lead corrections
    # that leave gaps, new global rules) means another round; nothing
    # to apply means the iteration is approved. Captured in status.yaml
    # at the end (no separate architect.yaml).
    needs_round = bool(
        parsed["corrections"]
        or parsed["rejected_correction_ids"]
        or parsed["proposed_conventions"]
        or parsed["proposed_decisions"]
    )

    # Distribute architect's corrections directly into the relevant
    # role's corrections file. Role comes from `action_id` prefix
    # (fix/remove) or from `for_role` (missing). Each correction gets
    # an architect-prefixed id so its source is greppable.
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
        existing = proposals.read_corrections(project_dir, iteration_n, role)
        proposals.write_corrections(
            project_dir, iteration_n, role, existing + additions,
        )
        print(
            f"  ✓ {role}.corrections.yaml +{len(additions)} from architect",
            file=sys.stderr,
        )
    if skipped:
        print(
            f"  ✗ {len(skipped)} architect correction(s) skipped — "
            f"role unresolved",
            file=sys.stderr,
        )

    # Move rejected lead corrections to their respective rejected files.
    moved, missing = 0, 0
    for cid in parsed["rejected_correction_ids"]:
        role_for_id = _role_from_correction_id(cid, roles)
        if role_for_id is None:
            missing += 1
            continue
        if proposals.reject_correction(
            project_dir, iteration_n, role_for_id, cid,
            rejected_by="architect",
        ):
            moved += 1
        else:
            missing += 1
    if parsed["rejected_correction_ids"]:
        print(
            f"  ✓ rejected {moved} correction(s) cross-role"
            + (f", {missing} not found" if missing else ""),
            file=sys.stderr,
        )

    # Architect's proposed conv/dec → iteration global pending stores.
    conv_records = proposals.to_pending_records(
        parsed["proposed_conventions"],
        id_prefix=f"v84-{iteration_n}.architect.conv",
    )
    if conv_records:
        proposals.write_conventions(project_dir, iteration_n, "global", conv_records)
        print(
            f"  ✓ {iter_dir / 'global.conventions.yaml'} "
            f"({len(conv_records)} proposed)",
            file=sys.stderr,
        )

    dec_records = proposals.to_pending_records(
        parsed["proposed_decisions"],
        id_prefix=f"v84-{iteration_n}.architect.dec",
    )
    if dec_records:
        proposals.write_decisions(project_dir, iteration_n, "global", dec_records)
        print(
            f"  ✓ {iter_dir / 'global.decisions.yaml'} "
            f"({len(dec_records)} proposed)",
            file=sys.stderr,
        )

    return needs_round


def _role_from_correction_id(cid: str, roles: list[str]) -> Optional[str]:
    """A correction id encodes its role somewhere in the dotted path.

    Lead's accepted reviewer suggestion ids:  v84-1.frontend.pages.s.3
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


def _parse(yaml_text: str) -> dict:
    try:
        data = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError:
        data = {}
    if not isinstance(data, dict):
        data = {}

    return {
        "corrections": _norm_corrections(data.get("corrections")),
        "rejected_correction_ids": _norm_rejected_ids(
            data.get("rejected_corrections"),
        ),
        "proposed_conventions": _norm_proposals(
            data.get("proposed_conventions"),
        ),
        "proposed_decisions": _norm_proposals(
            data.get("proposed_decisions"),
        ),
    }


def _norm_corrections(raw: Any) -> list[dict]:
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


def _norm_rejected_ids(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for r in raw:
        if isinstance(r, dict):
            cid = r.get("id")
        else:
            cid = r
        if isinstance(cid, str) and cid.strip():
            out.append(cid.strip())
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
    requires=("lead",),
    needs_brief=False,
    is_done=_is_done,
    call=architect,
)
