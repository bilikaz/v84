"""
review.py — Iteration review stage (round 1, parallel reviewers).

Once every active role has its draft (`iterations/<n>/<role>.yaml`),
fan out one call per role × per reviewer-lens. Each reviewer reads
its role's draft only, applies its single challenge, and emits
suggestions plus optional needs_convention / needs_decision.

Per-reviewer output lands at
`iterations/<n>/reviews/<role>.<reviewer>.yaml`. The stage is done
when every (role, reviewer) combination has its yaml file.

Resume is intentionally NOT supported: any re-run rewrites all
files. Reviewers are cheap and small; we want a fresh pass each
time so suggestions reflect the current draft, not stale state.

Lead / architect layers come in later phases.
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
)
from core.stage import Stage
from core.util import default_log_dir, instruction_path
from llm import CallSpec, LLMConfig, call_many, resolve_llm
from ui import MultiSpinner


def review(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Run round-1 reviewers for every active role × lens in parallel."""
    if cfg is None:
        raise ValueError("LLMConfig required — call via v84.py or pass cfg=")

    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        raise RuntimeError(
            "no current_iteration set in core.yaml — run plan + draft first"
        )

    parent = coreyaml.find_by_id(data, parent_id)
    if parent is None:
        raise RuntimeError(f"current_iteration {parent_id!r} not found in core.yaml")

    iteration_n = _iteration_number(parent_id)
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    reviews_dir = iter_dir / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)

    # Clear stale reviewer files from any prior run — review.py owns
    # this directory. Prevents leaking round-1 suggestions into a
    # partially-failed round-2 re-run, or orphans when a role's
    # reviewer set was edited between rounds.
    for f in reviews_dir.glob("*.yaml"):
        f.unlink()

    profile_path = project_dir / "v84" / "profile.yaml"
    roles = active_roles(profile_path)
    if not roles:
        raise RuntimeError("no active roles in profile.yaml")

    plan = plan_block(parent)

    fan_cfg = _fan_out_cfg(project_dir, fallback=cfg)

    # Build (role, reviewer) pairs from each role's structure file.
    pairs: list[tuple[str, dict]] = []
    for role in roles:
        draft_file = iter_dir / f"{role}.yaml"
        if not draft_file.exists():
            raise RuntimeError(
                f"draft missing for role {role!r} at {draft_file} — "
                f"run the draft stage first"
            )
        for reviewer in _load_reviewers(project_dir, role):
            pairs.append((role, reviewer))

    if not pairs:
        raise RuntimeError("no reviewers found across active roles")

    skill_file = instruction_path("iteration", "review.md")
    if not skill_file.exists():
        raise FileNotFoundError(f"Instruction not found: {skill_file}")
    system = skill_file.read_text(encoding="utf-8")

    drafts_by_role = {
        role: (iter_dir / f"{role}.yaml").read_text(encoding="utf-8")
        for role in roles
    }

    specs: list[CallSpec] = []
    labels: list[str] = []
    for role, reviewer in pairs:
        rev_name = reviewer["name"]
        labels.append(f"{role}.{rev_name}")
        specs.append(CallSpec(
            system=system,
            user_msgs=_build_user_msgs(
                project_dir=project_dir,
                role=role,
                reviewer=reviewer,
                plan=plan,
                draft_yaml=drafts_by_role[role],
                iter_dir=iter_dir,
            ),
            log_name=f"iter-{iteration_n}-review-{role}-{rev_name}",
        ))

    workers = min(fan_cfg.max_concurrency, len(specs))
    print(f"  reviewing {len(specs)} (role × lens) — model {fan_cfg.model} "
          f"@ {fan_cfg.url} (workers: {workers})",
          file=sys.stderr)
    with MultiSpinner(labels) as ms:
        results = call_many(
            fan_cfg, specs,
            log_dir=default_log_dir(),
            progress=ms,
        )

    failed: list[tuple[str, str]] = []
    for (role, reviewer), spec, result in zip(pairs, specs, results):
        rev_name = reviewer["name"]
        label = f"{role}.{rev_name}"
        if result.error is not None:
            failed.append((label, repr(result.error)))
            continue
        parsed = _parse(result.response or "")
        out_file = reviews_dir / f"{role}.{rev_name}.yaml"
        out_file.write_text(
            _render_review_output(
                parsed,
                iteration_n=iteration_n,
                role=role,
                reviewer_tag=rev_name,
            ),
            encoding="utf-8",
        )
        n_sugs = len(parsed.get("suggestions") or [])
        print(
            f"  ✓ {out_file} ({n_sugs} suggestion{'s' if n_sugs != 1 else ''})",
            file=sys.stderr,
        )

        # Append this reviewer's conv/dec proposals to the iteration's
        # role-scoped pending stores (writer wrote them first; we
        # accumulate). Ids are harness-assigned and embed the
        # reviewer_tag, so `append_pending` dedups cleanly on re-run.
        new_conv = proposals.to_pending_records(
            parsed.get("needs_convention"),
            id_prefix=f"v84-{iteration_n}.{role}.{rev_name}.conv",
        )
        if new_conv:
            existing = proposals.read_conventions(project_dir, iteration_n, role)
            proposals.write_conventions(
                project_dir, iteration_n, role,
                proposals.append_pending(existing, new_conv),
            )
            print(
                f"    + {len(new_conv)} convention proposal"
                f"{'s' if len(new_conv) != 1 else ''}",
                file=sys.stderr,
            )

        new_dec = proposals.to_pending_records(
            parsed.get("needs_decision"),
            id_prefix=f"v84-{iteration_n}.{role}.{rev_name}.dec",
        )
        if new_dec:
            existing = proposals.read_decisions(project_dir, iteration_n, role)
            proposals.write_decisions(
                project_dir, iteration_n, role,
                proposals.append_pending(existing, new_dec),
            )
            print(
                f"    + {len(new_dec)} decision proposal"
                f"{'s' if len(new_dec) != 1 else ''}",
                file=sys.stderr,
            )

    if failed:
        for label, err in failed:
            print(f"  ✗ {label}: {err}", file=sys.stderr)
        raise RuntimeError(
            f"{len(failed)} reviewer call(s) failed — re-run to retry"
        )

    iter_status.advance_to(project_dir, iteration_n, "lead")
    return reviews_dir


# -----------------------------------------------------------------------------
# Per-reviewer context builder
# -----------------------------------------------------------------------------

def _build_user_msgs(
    *,
    project_dir: Path,
    role: str,
    reviewer: dict,
    plan: str,
    draft_yaml: str,
    iter_dir: Path,
) -> list[str]:
    """Multi-message context for one reviewer call. Cached blocks
    (roles/stack/conv/dec/history) read once per iteration and
    reuse across stages — see core.cache."""
    msgs: list[str] = [
        f"## Your reviewer definition\n\n{_render_reviewer(reviewer)}",
        f"## Role context\n\n{cached_roles_block(project_dir, role, iter_dir)}",
        f"## Iteration plan\n\n{plan}",
        f"## Writer draft\n\n```yaml\n{draft_yaml.strip()}\n```",
    ]

    stack = cached_stack_block(project_dir, role, iter_dir).strip()
    if stack:
        msgs.append(f"## Role stack\n\n{stack}")

    layout = cached_layout_block(project_dir, role, iter_dir).strip()
    if layout:
        msgs.append(f"## Role's repo layout\n\n{layout}")

    conv = cached_conventions_block(project_dir, role, iter_dir).strip()
    if conv:
        msgs.append(f"## Conventions in scope\n\n{conv}")

    dec = cached_decisions_block(project_dir, role, iter_dir).strip()
    if dec:
        msgs.append(f"## Decisions in scope\n\n{dec}")

    history = cached_role_history_block(project_dir, role, iter_dir).strip()
    if history:
        msgs.append(
            f"## Role's implementation history\n\n"
            f"What this role has shipped in past iterations. Use it "
            f"to spot regressions or contradictions in the writer's "
            f"current draft against what's already been built — but "
            f"don't re-flag past decisions absent a new reason.\n\n"
            f"{history}"
        )

    # Round 2+ context — empty on round 1 so naturally skipped.
    # Filtered to this reviewer's own suggestions plus role-wide
    # lead/architect entries; other reviewers' lens-specific items
    # don't reach this reviewer.
    rev_tag = reviewer.get("name")
    applied = corrections_applied_block(
        project_dir, role, reviewer_tag=rev_tag,
    ).strip()
    if applied:
        msgs.append(
            "## Corrections that was applied, do not re-raise them\n\n"
            f"{applied}"
        )

    rejected = corrections_rejected_block(
        project_dir, role, reviewer_tag=rev_tag,
    ).strip()
    if rejected:
        msgs.append(
            "## Corrections that was rejected, do not re-raise them\n\n"
            f"{rejected}"
        )

    msgs.append(
        "Review the draft through your lens. "
        "Follow your output format exactly."
    )
    return msgs


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

def _render_review_output(
    parsed: dict,
    *,
    iteration_n: int,
    role: str,
    reviewer_tag: str,
) -> str:
    """Render the reviewer's suggestions list as the on-disk shape.

    File name (`<role>.<reviewer_tag>.yaml`) already encodes role +
    reviewer; output is just the suggestions list (each with a
    harness-assigned `id`). Conv/dec proposals are persisted
    separately by the caller into the iteration's role-scoped
    pending stores.

    Suggestion ids are assigned per listed order:
        v84-<iter>.<role>.<reviewer_tag>.s.<n>
    Greppable as `[v84-1.frontend.pages.s` for one reviewer's
    suggestions across the iteration.
    """
    sugs = parsed.get("suggestions", [])
    for i, s in enumerate(sugs):
        s_with_id = {"id": f"v84-{iteration_n}.{role}.{reviewer_tag}.s.{i + 1}"}
        s_with_id.update(s)
        sugs[i] = s_with_id

    return yaml.safe_dump(
        {"suggestions": sugs},
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=10000,
    )


_VERDICTS = {"fix", "missing", "remove"}


def _parse(yaml_text: str) -> dict:
    """Permissive parse of the reviewer response. Empty dict on failure."""
    try:
        data = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError:
        return {}
    if not isinstance(data, dict):
        return {}

    raw_sugs = data.get("suggestions") or []
    sugs: list[dict] = []
    for s in raw_sugs:
        if not isinstance(s, dict):
            continue
        verdict = s.get("verdict")
        if verdict not in _VERDICTS:
            continue
        entry: dict[str, Any] = {"verdict": verdict}
        # `missing` references the under-covered task by task_id;
        # `fix` and `remove` reference the existing action by action_id.
        if verdict == "missing":
            tid = s.get("task_id")
            if isinstance(tid, str) and tid.strip():
                entry["task_id"] = tid.strip()
        else:
            ref = s.get("action_id")
            if isinstance(ref, str) and ref.strip():
                entry["action_id"] = ref.strip()
        text = s.get("suggestion")
        if isinstance(text, str):
            entry["suggestion"] = text.strip()
        sugs.append(entry)

    out: dict[str, Any] = {"suggestions": sugs}

    conv = _parse_proposals(data.get("needs_convention"))
    if conv:
        out["needs_convention"] = conv

    dec = _parse_proposals(data.get("needs_decision"))
    if dec:
        out["needs_decision"] = dec

    return out


def _parse_proposals(raw: Any) -> list[dict]:
    """Normalise needs_convention / needs_decision entries.

    Both share the {id, proposal, alternatives} shape; alternatives
    is a list of strings. Entries with no proposal text are skipped.
    """
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


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _iteration_number(task_id: str) -> int:
    """v84-3 → 3. v84-3.1 → 3."""
    return int(task_id.split(".")[0].split("-")[1])


# -----------------------------------------------------------------------------
# Stage metadata
# -----------------------------------------------------------------------------

def _is_done(project_dir: Path) -> bool:
    """Done when status.yaml says next_step has moved past `review`."""
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        return False
    iteration_n = _iteration_number(parent_id)
    return iter_status.stage_is_done(project_dir, iteration_n, "review")


STAGE = Stage(
    name="review",
    title="Reviewers critique per role × lens",
    priority=1201,
    produces="iterations/<n>/reviews/<role>.<reviewer>.yaml",
    requires=("draft",),
    needs_brief=False,
    is_done=_is_done,
    call=review,
)
