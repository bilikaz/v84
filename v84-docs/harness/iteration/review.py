"""
review.py — Per-role review stage (parallel reviewer fan-out).

Once a single role's draft (or patched draft) has landed, fan out
one call per reviewer lens for THAT role. Each reviewer reads the
role's draft, applies its single challenge, and emits corrections
plus optional rules.

All reviewers' corrections for the role merge into a single pending
file: `iterations/<n>/<role>.corrections-pending.yaml`. The lead
consumes that file in its verdict pass; the architect later appends
to the same file for cross-role corrections.

Resume policy: re-running re-clears the role's pending file and
fans the reviewers again. Cheap and small; corrections always
reflect the current draft, not stale state.

On success the role's pipeline step advances from `review` → `lead`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from core import iter_status, proposals
from core.context import build_user_msgs
from core.util import default_log_dir, load_instruction
from llm import CallSpec, LLMConfig, call_many, resolve_llm
from ui import spinner


def review_role(
    project_dir: Path,
    parent: dict,
    iteration_n: int,
    role: str,
    *,
    cfg: LLMConfig,
) -> None:
    """Run every reviewer lens for a single role.

    Persists merged corrections to `<role>.corrections-pending.yaml`
    and appends rule proposals to `<role>.rules.yaml`. Advances the
    role's pipeline step from `review` → `lead` on success.
    """
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    iter_dir.mkdir(parents=True, exist_ok=True)

    draft_file = iter_dir / f"{role}.yaml"
    if not draft_file.exists():
        raise RuntimeError(
            f"draft missing for role {role!r} at {draft_file} — "
            f"draft/patch must run first"
        )

    reviewers = _load_reviewers(project_dir, role)
    if not reviewers:
        # No reviewers configured for this role — skip straight to lead.
        # An empty pending file makes the lead a no-op for corrections.
        proposals.write_pending_corrections(project_dir, iteration_n, role, [])
        iter_status.set_role_step(
            project_dir, iteration_n, role, iter_status.STEP_LEAD,
        )
        spinner.log(f"  ↷ {role}: no reviewers configured")
        return

    fan_cfg = _fan_out_cfg(project_dir, fallback=cfg)

    # Fresh pass — clear last round's reviewer raises before re-fanning.
    proposals.write_pending_corrections(project_dir, iteration_n, role, [])

    review_md, schema = load_instruction("iteration", "review")

    # Prefix-cache layout: the system prompt and every context block
    # is byte-identical across the role's reviewers. Only the trailing
    # user message — reviewer identity + the lens-specific ask — varies.
    # vLLM's prefix cache covers everything up to that final message,
    # so each reviewer call after the first reuses ~all of the prompt.
    specs: list[CallSpec] = []
    for reviewer in reviewers:
        rev_name = reviewer["name"]
        trailing = (
            f"## Your reviewer\n\n"
            f"{_render_reviewer(reviewer)}\n\n"
            f"Review the role's draft through your lens."
        )
        specs.append(CallSpec(
            system=review_md,
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
                    "corrections_pending":           None,
                    "corrections_rejected":          None,
                    "corrections_applied":           [role],
                    "corrections_rejected_history":  [role],
                    "rules":                         [role],
                    "rules_pending":                 None,
                    "rules_rejected":                None,
                    "trailing": trailing,
                },
                role=role,
            ),
            response_schema=schema,
            log_name=f"iter-{iteration_n}-review-{role}-{rev_name}",
        ))

    results = call_many(fan_cfg, specs, log_dir=default_log_dir())

    failed: list[tuple[str, str]] = []
    pending: list[dict] = []
    for reviewer, result in zip(reviewers, results):
        rev_name = reviewer["name"]
        if result.error is not None:
            failed.append((rev_name, repr(result.error)))
            continue
        parsed = _parse(result.response or {})
        new_corrs = _assign_correction_ids(
            parsed.get("corrections") or [],
            iteration_n=iteration_n,
            role=role,
            reviewer_tag=rev_name,
        )
        pending.extend(new_corrs)
        n = len(new_corrs)
        spinner.log(
            f"  ✓ {role}.{rev_name} ({n} correction{'s' if n != 1 else ''})"
        )

        new_rules = proposals.to_pending_rule_records(
            parsed.get("rules"),
            id_prefix=f"v84-{iteration_n}.{role}.{rev_name}.rule",
        )
        if new_rules:
            existing = proposals.read_rules(project_dir, iteration_n, role)
            proposals.write_rules(
                project_dir, iteration_n, role,
                proposals.append_pending(existing, new_rules),
            )
            spinner.log(
                f"    + {len(new_rules)} rule proposal"
                f"{'s' if len(new_rules) != 1 else ''}"
            )

    if failed:
        for rev_name, err in failed:
            spinner.log(f"  ✗ {role}.{rev_name}: {err}")
        raise RuntimeError(
            f"review failed for {role}: {len(failed)} reviewer call(s) "
            f"failed — re-run to retry"
        )

    proposals.write_pending_corrections(
        project_dir, iteration_n, role, pending,
    )
    spinner.log(
        f"  ✓ {role}.corrections-pending.yaml "
        f"({len(pending)} correction{'s' if len(pending) != 1 else ''} "
        f"from {len(reviewers)} reviewer(s))"
    )

    iter_status.set_role_step(
        project_dir, iteration_n, role, iter_status.STEP_LEAD,
    )


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _render_reviewer(r: dict) -> str:
    """Format a single reviewer's definition for the prompt."""
    title = r.get("title") or r.get("name", "")
    name = r.get("name", "")
    resp = (r.get("responsibilities") or "").strip()
    challenge = (r.get("challenge") or "").strip()
    catches = r.get("catches") or []

    lines = [f"### {title}", f"reviewer_tag: {name}", ""]
    if resp:
        lines.extend(["**Responsibilities:**", resp, ""])
    if challenge:
        lines.extend(["**Challenge (single question to hold):**", challenge, ""])
    if catches:
        lines.append("**Catches (example failure modes):**")
        for c in catches:
            lines.append(f"- {c}")
    return "\n".join(lines).rstrip()


def _load_reviewers(project_dir: Path, role: str) -> list[dict]:
    """Read the role file and return its reviewers list."""
    role_file = project_dir / "v84" / "structure" / "roles" / f"{role}.yaml"
    if not role_file.exists():
        raise FileNotFoundError(f"Role file missing: {role_file}")
    data = yaml.safe_load(role_file.read_text(encoding="utf-8")) or {}
    raw = data.get("reviewers") or []
    out: list[dict] = []
    for r in raw:
        if isinstance(r, dict) and isinstance(r.get("name"), str):
            out.append(r)
    return out


# -----------------------------------------------------------------------------
# Output normalisation + persistence
# -----------------------------------------------------------------------------

def _assign_correction_ids(
    raw: list[dict],
    *,
    iteration_n: int,
    role: str,
    reviewer_tag: str,
) -> list[dict]:
    """Assign harness-managed ids to a reviewer's parsed corrections.

    Id format:  v84-<iter>.<role>.<reviewer_tag>.c.<n>
    """
    out: list[dict] = []
    for i, c in enumerate(raw):
        entry = {"id": f"v84-{iteration_n}.{role}.{reviewer_tag}.c.{i + 1}"}
        entry.update(c)
        out.append(entry)
    return out


_VERDICTS = {"fix", "missing", "remove"}


def _parse(data: dict) -> dict:
    if not isinstance(data, dict):
        return {}

    raw_corrs = data.get("corrections") or []
    corrs: list[dict] = []
    for c in raw_corrs:
        if not isinstance(c, dict):
            continue
        verdict = c.get("verdict")
        if verdict not in _VERDICTS:
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
        text = c.get("correction")
        if isinstance(text, str) and text.strip():
            entry["correction"] = text.strip()
        corrs.append(entry)

    out: dict[str, Any] = {"corrections": corrs}
    rules = _parse_proposals(data.get("rules"))
    if rules:
        out["rules"] = rules
    return out


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
    try:
        return resolve_llm(
            project_dir=project_dir, tier="multi", interactive=False,
        )
    except RuntimeError:
        return fallback
