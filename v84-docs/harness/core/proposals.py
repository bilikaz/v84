"""
proposals.py — Iteration-local rules store + correction gathering.

For each role per iteration we maintain one append-and-update
file that aggregates every rule proposal raised by the writer
or any reviewer, plus the lead's verdicts on them:

    iterations/<n>/<role>.rules.yaml

Each entry has the shape:

    - id: v84-<iter>.<role>[.<reviewer_tag>].rule.<n>
      proposal: |
        <prose>
      alternatives:
        - |
          <prose>
      status: pending | accepted | rejected
      text: |                    # only when status == accepted
        <final wording (lead's `text` field)>
      reason: |                  # set on accept or reject by the lead
        <one line>

The id encodes the source — writer ids look like
`v84-1.frontend.rule.1`; reviewer ids carry their reviewer_tag,
e.g. `v84-1.frontend.pages.rule.1`. No separate `source:` field.

Lifecycle:
    draft stage   →  writes the file with writer's proposals
                     (status: pending), harness-assigned ids.
    review stage  →  appends each reviewer's proposals
                     (status: pending), harness-assigned ids.
    lead stage    →  updates each pending entry's status to
                     accepted (writing `text` = the lead's final
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
# like `correction`, `reason`, `proposal`, `text` then render
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
# Iteration-local rules store
# -----------------------------------------------------------------------------

def rules_path(project_dir: Path, n: int, role: str) -> Path:
    return _iter_dir(project_dir, n) / f"{role}.rules.yaml"


def read_rules(project_dir: Path, n: int, role: str) -> list[dict]:
    return _read_records(rules_path(project_dir, n, role))


def write_rules(
    project_dir: Path, n: int, role: str, records: list[dict],
) -> Path:
    return _write_records(rules_path(project_dir, n, role), records)


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
# Conversion: agent's rules proposal entries → store records
# -----------------------------------------------------------------------------

def to_pending_rule_records(
    proposals_in: list[dict] | None, *, id_prefix: str, start_n: int = 1,
) -> list[dict]:
    """Translate `rules` entries from a writer or reviewer YAML
    into store records.

    Ids are assigned `<id_prefix>.<n>` in the agent's emit order,
    starting at `start_n` (default 1). Round-2+ patch passes a
    `start_n` past the highest existing index so new proposals
    extend the writer's round-1 numbering instead of colliding.
    Caller passes the full prefix including the `.rule` segment,
    e.g. `v84-1.frontend.rule` or `v84-1.frontend.pages.rule`.
    All records emerge with `status: pending`.
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


def to_accepted_rule_records(
    items: list[dict] | None, *, id_prefix: str, start_n: int = 1,
) -> list[dict]:
    """Translate lead-authored `rules` entries straight into
    accepted records.

    Lead is the authority for role-scoped rules in-iteration — no
    further verdicting is needed inside the cycle. But user_review
    is the final gate, so each record carries the same
    `{proposal, alternatives}` payload as reviewer raises so the
    user has the full context (lead's preferred form + the
    alternatives lead considered) at promotion time. The `text`
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
        entry["text"] = proposal
        out.append(entry)
    return out


def next_index_for_prefix(existing: list[dict], id_prefix: str) -> int:
    """Find the next integer suffix for `<id_prefix>.<n>` ids in
    `existing`. Returns 1 if no record matches the prefix.

    Used by patch (round 2+) to continue the writer's numbering for
    fresh rule proposals so ids don't collide with round-1's.
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

def pending_rules(
    project_dir: Path, n: int, role: str,
) -> list[dict]:
    return [r for r in read_rules(project_dir, n, role)
            if r.get("status") == "pending"]


def accepted_rules(
    project_dir: Path, n: int, role: str,
) -> list[dict]:
    return [r for r in read_rules(project_dir, n, role)
            if r.get("status") == "accepted"]


# -----------------------------------------------------------------------------
# Promotion / retirement (pre-pass: architect promoting a lead rule to global)
# -----------------------------------------------------------------------------

def retire_lead_rules(
    project_dir: Path, n: int, ids_to_retire: dict[str, str],
) -> int:
    """Mark each cited lead rule as superseded by the global that
    promoted it. `ids_to_retire` maps lead_rule_id → superseding
    global_rule_id. Walks every role's rules file once. Returns
    the count of records actually transitioned.

    Records found are flipped to `status: superseded` with a
    `superseded_by` field carrying the global's id and `text`/
    proposal preserved for audit. Records not found are silently
    skipped — caller logs that.
    """
    if not ids_to_retire:
        return 0
    iter_dir = _iter_dir(project_dir, n)
    if not iter_dir.exists():
        return 0
    moved = 0
    for p in sorted(iter_dir.glob("*.rules.yaml")):
        if p.name == "global.rules.yaml":
            continue
        records = _read_records(p)
        changed = False
        for r in records:
            rid = r.get("id")
            if not rid or rid not in ids_to_retire:
                continue
            r["status"] = "superseded"
            r["superseded_by"] = ids_to_retire[rid]
            moved += 1
            changed = True
        if changed:
            _write_records(p, records)
    return moved


# -----------------------------------------------------------------------------
# Active rules from the project's main folder
# -----------------------------------------------------------------------------

def append_project_rules(
    project_dir: Path, records: list[dict],
) -> Path:
    """Append records to <project>/v84/global.rules.yaml, dedup by id."""
    return _append_project_records(
        project_dir / "v84" / "global.rules.yaml", records,
    )


def append_project_role_rules(
    project_dir: Path, role: str, records: list[dict],
) -> Path:
    """Append records to <project>/v84/<role>.rules.yaml, dedup by id."""
    return _append_project_records(
        project_dir / "v84" / f"{role}.rules.yaml", records,
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


def pending_corrections_path(project_dir: Path, n: int, role: str) -> Path:
    """Pending corrections awaiting lead verdict — merged from every
    source that targets this role (every reviewer, plus architect).
    Lead reads this, votes, and clears the file as part of its stage.
    """
    return _iter_dir(project_dir, n) / f"{role}.corrections-pending.yaml"


def read_corrections(project_dir: Path, n: int, role: str) -> list[dict]:
    return _read_records(corrections_path(project_dir, n, role))


def read_rejected_corrections(
    project_dir: Path, n: int, role: str,
) -> list[dict]:
    return _read_records(rejected_corrections_path(project_dir, n, role))


def read_pending_corrections(
    project_dir: Path, n: int, role: str,
) -> list[dict]:
    return _read_records(pending_corrections_path(project_dir, n, role))


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


def write_pending_corrections(
    project_dir: Path, n: int, role: str, records: list[dict],
) -> Path:
    return _write_records(
        pending_corrections_path(project_dir, n, role), records,
    )


def append_pending_corrections(
    project_dir: Path, n: int, role: str, new: list[dict],
) -> Path:
    """Append entries to <role>.corrections-pending.yaml, preserving
    existing records. Used by review (per reviewer fan-out) and
    architect (cross-role corrections) to deposit into the same file.
    """
    if not new:
        return pending_corrections_path(project_dir, n, role)
    existing = read_pending_corrections(project_dir, n, role)
    return write_pending_corrections(project_dir, n, role, existing + new)


def clear_pending_corrections(
    project_dir: Path, n: int, role: str,
) -> None:
    """Remove the pending file (lead has finished verdicting it)."""
    p = pending_corrections_path(project_dir, n, role)
    if p.exists():
        p.unlink()


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
    """Update statuses in `records` from a verdicts list.

    Each verdict carries {id, verdict (accept|reject), optional
    text (the final wording when accepting), optional reason
    (when rejecting — captured for cross-pass visibility so the
    next round's architect / writer can see WHY a proposal was
    shot down without re-running the same idea)}. Records with no
    matching verdict are untouched.

    Use this helper when the verdict's accept transitions a record
    to the final accepted state (e.g. architect Phase A flipping
    pending → accepted after lead_validate). For lead's verdict on
    reviewer-raised rules — where accept does NOT flip status; the
    record stays pending awaiting architect's final decision — use
    `apply_lead_verdicts` instead.
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
            form = v.get("text")
            if isinstance(form, str) and form.strip():
                r["text"] = form.strip()
            r.pop("rejection_reason", None)
        else:
            r.pop("text", None)
            reason = v.get("reason")
            if isinstance(reason, str) and reason.strip():
                r["rejection_reason"] = reason.strip()
            else:
                r.pop("rejection_reason", None)
    return records


def apply_lead_verdicts(
    records: list[dict],
    verdicts: list[dict],
    *,
    rejected_by: str,
) -> list[dict]:
    """Apply lead's verdicts on pending reviewer-raised rules under
    the symmetric "lead-blessed but architect-pending" lifecycle.

    Per-verdict effect:
    - `accept` — record stays `status: pending`. Lead's preferred
      wording is recorded on the record's `text` field. Architect's
      `lead_validate` makes the final accepted/rejected call.
    - `reject` — record's status flips to `rejected` (final). The
      `rejected_by` tag and reason (when given) are stored.

    Records with no matching verdict are untouched.
    """
    by_id = {v.get("id"): v for v in verdicts if isinstance(v, dict) and v.get("id")}
    for r in records:
        v = by_id.get(r.get("id"))
        if v is None:
            continue
        verdict = v.get("verdict")
        if verdict not in ("accept", "reject"):
            continue
        if verdict == "accept":
            # Status stays pending; record lead's preferred wording.
            form = v.get("text")
            if isinstance(form, str) and form.strip():
                r["text"] = form.strip()
            r.pop("rejection_reason", None)
        else:
            r["status"] = "rejected"
            r["rejected_by"] = rejected_by
            r.pop("text", None)
            reason = v.get("reason")
            if isinstance(reason, str) and reason.strip():
                r["rejection_reason"] = reason.strip()
            else:
                r.pop("rejection_reason", None)
    return records


# -----------------------------------------------------------------------------
# Pending corrections — alias to the merged-per-role pending file
# -----------------------------------------------------------------------------

def collect_role_corrections(
    project_dir: Path, n: int, role: str,
) -> list[dict]:
    """Every pending correction targeting `role`, in order.

    Reads `<role>.corrections-pending.yaml`. Records there carry
    full ids that already encode their source — `v84-N.<role>.<reviewer_tag>.c.M`
    for reviewer-sourced, `v84-N.architect.c.M` for architect-sourced.
    No filename-derived `reviewer_tag` injection is needed; the lead
    reads ids directly.
    """
    return read_pending_corrections(project_dir, n, role)


# -----------------------------------------------------------------------------
# Synthetic corrections from newly-accepted rules
# -----------------------------------------------------------------------------
#
# When a rule lands as `status: accepted`, the role's existing draft
# may not yet conform. Rather than wait for the next round's reviewer
# to detect drift and raise a fix correction, the harness synthesises
# the apply-this-rule correction at acceptance time and feeds it directly to
# patch via the role's corrections.yaml. Round 2 patches and verifies in one
# pass; round 3 (drift-discovery) is no longer needed.
#
# Globals fan out to every active role; role-scoped go to that role only.

def synthesize_apply_correction(
    *,
    rule_id: str,
    rule_text: str,
    parent_task_id: str,       # iteration's parent task, e.g. "v84-1"
    scope: str,                # "role" or "global"
) -> dict:
    """Build the synthetic correction record signalling that the role's
    draft must be reviewed against a newly-accepted rule. Returned in
    the same shape as ordinary lead/architect corrections so patch can
    process it through the existing path."""
    suffix_id = f"{rule_id}.apply"
    rule_text = (rule_text or "").strip()
    correction_prose = (
        f"Apply newly-accepted rule {rule_id} to your draft. "
        f"Scan every action and update any that don't yet conform. "
        f"Surviving actions that already comply stay as-is."
    )
    if rule_text:
        correction_prose += f"\n\nRule:\n{rule_text}"
    return {
        "id": suffix_id,
        "verdict": "fix",
        "task_id": parent_task_id,
        "source": f"{scope}_rule_acceptance",
        "correction": correction_prose,
    }


def append_synthetic_correction(
    project_dir: Path, n: int, role: str, synthetic: dict,
) -> bool:
    """Append a synthetic apply-correction to <role>.corrections.yaml
    if its id isn't already present. Idempotent — re-running the
    triggering stage won't duplicate the correction.

    Returns True when newly appended, False when the id was already
    present (no-op).
    """
    sid = synthetic.get("id")
    if not sid:
        return False
    existing = read_corrections(project_dir, n, role)
    if any(rec.get("id") == sid for rec in existing):
        return False
    write_corrections(project_dir, n, role, existing + [synthetic])
    return True
