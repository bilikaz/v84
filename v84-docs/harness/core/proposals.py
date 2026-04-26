"""
proposals.py — Iteration-local conv/dec stores + suggestion gathering.

For each role per iteration we maintain two append-and-update
files that aggregate every convention/decision proposal raised by
the writer or any reviewer, plus the lead's verdicts on them:

    iterations/<n>/<role>.conventions.yaml
    iterations/<n>/<role>.decisions.yaml

Each entry has the shape:

    - id: v84-<iter>.<role>[.<reviewer_tag>].conv.<n>
      proposal: |
        <prose>
      alternatives:
        - |
          <prose>
      status: pending | accepted | rejected
      rule: |                    # only when status == accepted
        <final wording (lead's `rule` field)>
      reason: |                  # set on accept or reject by the lead
        <one line>

The id encodes the source — writer ids look like
`v84-1.frontend.conv.1`; reviewer ids carry their reviewer_tag,
e.g. `v84-1.frontend.pages.conv.1`. No separate `source:` field.

Lifecycle:
    draft stage   →  writes the file with writer's proposals
                     (status: pending), harness-assigned ids.
    review stage  →  appends each reviewer's proposals
                     (status: pending), harness-assigned ids.
    lead stage    →  updates each pending entry's status to
                     accepted (writing `rule` = the lead's final
                     wording) or rejected. Rejected entries stay
                     in the file as audit/history.

Suggestions stay inside their reviewer files (each carrying the
harness-assigned id from `review._render_review_output`); the
gathering helper here flattens them across a role's reviewers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


# Force block-scalar style for any string carrying `: ` (which would
# otherwise force single-quoted style) or a newline. Plain prose fields
# like `correction`, `reason`, `proposal`, `rule` then render
# as `|` block scalars in every file we write — readable diffs, no
# escape soup, parser-safe. Registered on SafeDumper so it applies to
# every yaml.safe_dump in the harness.
def _str_repr(dumper: yaml.Dumper, data: str):
    style = "|" if ("\n" in data or ": " in data) else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


yaml.add_representer(str, _str_repr, Dumper=yaml.SafeDumper)


def _read_yaml(p: Path) -> Any:
    if not p.exists():
        return None
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _dump(data: Any) -> str:
    return yaml.safe_dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=10000,
    )


def _iter_dir(project_dir: Path, n: int) -> Path:
    return project_dir / "v84" / "iterations" / str(n)


# -----------------------------------------------------------------------------
# Iteration-local conv/dec store
# -----------------------------------------------------------------------------

def conventions_path(project_dir: Path, n: int, role: str) -> Path:
    return _iter_dir(project_dir, n) / f"{role}.conventions.yaml"


def decisions_path(project_dir: Path, n: int, role: str) -> Path:
    return _iter_dir(project_dir, n) / f"{role}.decisions.yaml"


def read_conventions(project_dir: Path, n: int, role: str) -> list[dict]:
    return _read_records(conventions_path(project_dir, n, role))


def read_decisions(project_dir: Path, n: int, role: str) -> list[dict]:
    return _read_records(decisions_path(project_dir, n, role))


def write_conventions(
    project_dir: Path, n: int, role: str, records: list[dict],
) -> Path:
    return _write_records(conventions_path(project_dir, n, role), records)


def write_decisions(
    project_dir: Path, n: int, role: str, records: list[dict],
) -> Path:
    return _write_records(decisions_path(project_dir, n, role), records)


def _read_records(p: Path) -> list[dict]:
    data = _read_yaml(p)
    if not isinstance(data, list):
        return []
    return [r for r in data if isinstance(r, dict)]


def _write_records(p: Path, records: list[dict]) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_dump(records), encoding="utf-8")
    return p


# -----------------------------------------------------------------------------
# Conversion: agent's needs_* proposal entries → store records
# -----------------------------------------------------------------------------

def to_pending_records(
    proposals_in: list[dict] | None, *, id_prefix: str, start_n: int = 1,
) -> list[dict]:
    """Translate `needs_convention` / `needs_decision` entries from a
    writer or reviewer YAML into store records.

    Ids are assigned `<id_prefix>.<n>` in the agent's emit order,
    starting at `start_n` (default 1). Round-2+ patch passes a
    `start_n` past the highest existing index so new proposals
    extend the writer's round-1 numbering instead of colliding.
    Caller passes the full prefix including the `.conv` or `.dec`
    segment, e.g. `v84-1.frontend.conv` or
    `v84-1.frontend.pages.dec`. All records emerge with
    `status: pending`.
    """
    out: list[dict] = []
    n = start_n - 1
    for p in proposals_in or []:
        if not isinstance(p, dict):
            continue
        proposal = (p.get("proposal") or "").strip()
        if not proposal:
            continue
        n += 1
        entry: dict[str, Any] = {
            "id": f"{id_prefix}.{n}",
            "proposal": proposal,
        }
        alts = p.get("alternatives")
        if isinstance(alts, list):
            cleaned = [str(a).strip() for a in alts if str(a).strip()]
            if cleaned:
                entry["alternatives"] = cleaned
        entry["status"] = "pending"
        out.append(entry)
    return out


def to_accepted_records(
    items: list[dict] | None, *, id_prefix: str, start_n: int = 1,
) -> list[dict]:
    """Translate lead-authored `needs_convention` / `needs_decision`
    entries straight into accepted records.

    Lead is the authority for role-scoped rules in-iteration — no
    further verdicting is needed inside the cycle. But user_review
    is the final gate, so each record carries the same
    `{proposal, alternatives}` payload as reviewer raises so the
    user has the full context (lead's preferred form + the
    alternatives lead considered) at promotion time. The `rule`
    field is set to the proposal text since the lead's preferred
    form is what gets enacted. Ids assigned `<id_prefix>.<n>`
    starting at `start_n`.
    """
    out: list[dict] = []
    n = start_n - 1
    for item in items or []:
        if not isinstance(item, dict):
            continue
        proposal = (item.get("proposal") or "").strip()
        if not proposal:
            continue
        n += 1
        entry: dict[str, Any] = {
            "id": f"{id_prefix}.{n}",
            "status": "accepted",
            "proposal": proposal,
        }
        alts = item.get("alternatives")
        if isinstance(alts, list):
            cleaned = [str(a).strip() for a in alts if str(a).strip()]
            if cleaned:
                entry["alternatives"] = cleaned
        entry["rule"] = proposal
        out.append(entry)
    return out


def next_index_for_prefix(existing: list[dict], id_prefix: str) -> int:
    """Find the next integer suffix for `<id_prefix>.<n>` ids in
    `existing`. Returns 1 if no record matches the prefix.

    Used by patch (round 2+) to continue the writer's numbering for
    fresh conv/dec proposals so ids don't collide with round-1's.
    """
    max_n = 0
    target = f"{id_prefix}."
    for r in existing:
        rid = r.get("id")
        if not isinstance(rid, str) or not rid.startswith(target):
            continue
        suffix = rid[len(target):]
        if suffix.isdigit():
            max_n = max(max_n, int(suffix))
    return max_n + 1


def append_pending(existing: list[dict], new: list[dict]) -> list[dict]:
    """Append new pending records, dropping ones that share an id with
    a record already present (keeps the existing file authoritative
    so re-running review doesn't duplicate)."""
    seen_ids = {r.get("id") for r in existing if r.get("id")}
    merged = list(existing)
    for r in new:
        if r.get("id") and r["id"] in seen_ids:
            continue
        merged.append(r)
        if r.get("id"):
            seen_ids.add(r["id"])
    return merged


# -----------------------------------------------------------------------------
# Pending-only views for the lead
# -----------------------------------------------------------------------------

def pending_conventions(
    project_dir: Path, n: int, role: str,
) -> list[dict]:
    return [r for r in read_conventions(project_dir, n, role)
            if r.get("status") == "pending"]


def pending_decisions(
    project_dir: Path, n: int, role: str,
) -> list[dict]:
    return [r for r in read_decisions(project_dir, n, role)
            if r.get("status") == "pending"]


def accepted_conventions(
    project_dir: Path, n: int, role: str,
) -> list[dict]:
    return [r for r in read_conventions(project_dir, n, role)
            if r.get("status") == "accepted"]


def accepted_decisions(
    project_dir: Path, n: int, role: str,
) -> list[dict]:
    return [r for r in read_decisions(project_dir, n, role)
            if r.get("status") == "accepted"]


# -----------------------------------------------------------------------------
# Active global rules from the project's main folder
# -----------------------------------------------------------------------------

def append_project_conventions(
    project_dir: Path, records: list[dict],
) -> Path:
    """Append records to <project>/v84/global.conventions.yaml, dedup by id."""
    return _append_project_records(
        project_dir / "v84" / "global.conventions.yaml", records,
    )


def append_project_decisions(
    project_dir: Path, records: list[dict],
) -> Path:
    """Append records to <project>/v84/global.decisions.yaml, dedup by id."""
    return _append_project_records(
        project_dir / "v84" / "global.decisions.yaml", records,
    )


def append_project_role_conventions(
    project_dir: Path, role: str, records: list[dict],
) -> Path:
    """Append records to <project>/v84/<role>.conventions.yaml, dedup by id."""
    return _append_project_records(
        project_dir / "v84" / f"{role}.conventions.yaml", records,
    )


def append_project_role_decisions(
    project_dir: Path, role: str, records: list[dict],
) -> Path:
    """Append records to <project>/v84/<role>.decisions.yaml, dedup by id."""
    return _append_project_records(
        project_dir / "v84" / f"{role}.decisions.yaml", records,
    )


def _append_project_records(p: Path, new: list[dict]) -> Path:
    existing = _read_records(p)
    seen_ids = {r.get("id") for r in existing if r.get("id")}
    for r in new:
        if r.get("id") and r["id"] in seen_ids:
            continue
        existing.append(r)
        if r.get("id"):
            seen_ids.add(r["id"])
    return _write_records(p, existing)


# -----------------------------------------------------------------------------
# Corrections + corrections-rejected (per-role files)
# -----------------------------------------------------------------------------

def corrections_path(project_dir: Path, n: int, role: str) -> Path:
    return _iter_dir(project_dir, n) / f"{role}.corrections.yaml"


def rejected_corrections_path(project_dir: Path, n: int, role: str) -> Path:
    return _iter_dir(project_dir, n) / f"{role}.corrections-rejected.yaml"


def read_corrections(project_dir: Path, n: int, role: str) -> list[dict]:
    return _read_records(corrections_path(project_dir, n, role))


def read_rejected_corrections(
    project_dir: Path, n: int, role: str,
) -> list[dict]:
    return _read_records(rejected_corrections_path(project_dir, n, role))


def write_corrections(
    project_dir: Path, n: int, role: str, records: list[dict],
) -> Path:
    return _write_records(corrections_path(project_dir, n, role), records)


def write_rejected_corrections(
    project_dir: Path, n: int, role: str, records: list[dict],
) -> Path:
    return _write_records(
        rejected_corrections_path(project_dir, n, role), records,
    )


def reject_correction(
    project_dir: Path, n: int, role: str, correction_id: str, *,
    rejected_by: str,
) -> bool:
    """Move a correction by id from corrections.yaml to
    corrections-rejected.yaml, tagging it with `rejected_by`.

    Returns True if found and moved; False if not present.
    """
    corrections = read_corrections(project_dir, n, role)
    keep, removed = [], None
    for c in corrections:
        if c.get("id") == correction_id and removed is None:
            removed = c
        else:
            keep.append(c)
    if removed is None:
        return False
    removed["rejected_by"] = rejected_by
    write_corrections(project_dir, n, role, keep)
    rejected = read_rejected_corrections(project_dir, n, role)
    rejected.append(removed)
    write_rejected_corrections(project_dir, n, role, rejected)
    return True


# -----------------------------------------------------------------------------
# Status updates from lead verdicts
# -----------------------------------------------------------------------------

def apply_verdicts(
    records: list[dict],
    verdicts: list[dict],
) -> list[dict]:
    """Update statuses in `records` from a lead's verdicts list.

    Each verdict carries {id, verdict (accept|reject), optional
    rule (the final wording when accepting), optional reason
    (when rejecting — captured for cross-pass visibility so the
    next round's architect / writer can see WHY a proposal was
    shot down without re-running the same idea)}. Records with no
    matching verdict are untouched.
    """
    by_id = {v.get("id"): v for v in verdicts if isinstance(v, dict) and v.get("id")}
    for r in records:
        v = by_id.get(r.get("id"))
        if v is None:
            continue
        verdict = v.get("verdict")
        if verdict not in ("accept", "reject"):
            continue
        r["status"] = "accepted" if verdict == "accept" else "rejected"
        if verdict == "accept":
            form = v.get("rule")
            if isinstance(form, str) and form.strip():
                r["rule"] = form.strip()
            r.pop("rejection_reason", None)
        else:
            r.pop("rule", None)
            reason = v.get("reason")
            if isinstance(reason, str) and reason.strip():
                r["rejection_reason"] = reason.strip()
            else:
                r.pop("rejection_reason", None)
    return records


# -----------------------------------------------------------------------------
# Suggestions — flat across this role's reviewers
# -----------------------------------------------------------------------------

def collect_role_suggestions(
    project_dir: Path, n: int, role: str,
) -> list[dict]:
    """Every suggestion for `role` from every reviewer file, in order.

    Each entry carries: id, reviewer_tag (added here from filename),
    plus the verdict / action_id / task_id / suggestion fields.
    Order: by reviewer file (alphabetical), then by emitted order
    inside each reviewer's suggestions list.
    """
    reviews = _iter_dir(project_dir, n) / "reviews"
    if not reviews.exists():
        return []

    out: list[dict] = []
    for f in sorted(reviews.glob(f"{role}.*.yaml")):
        reviewer_tag = f.stem[len(role) + 1:]
        data = _read_yaml(f)
        if not isinstance(data, dict):
            continue
        for s in data.get("suggestions") or []:
            if not isinstance(s, dict):
                continue
            entry: dict[str, Any] = {"reviewer_tag": reviewer_tag}
            entry.update(s)
            out.append(entry)
    return out
