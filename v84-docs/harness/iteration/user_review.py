"""
user_review.py — Iteration close + user-approval gate.

Fires when the cycle has converged (validate saw no pending
corrections). The user's surface here is rules only — actions are
a derived artifact of (rules + plan + role definitions), so once
the user has signed off on the rules and plan, the actions follow
by construction (and have already passed 4 reviewers × each round
+ lead + architect + validate).

Flow:

    1. Read every accepted rule from the iteration: per-role files
       filtered to status: accepted, plus the architect's globals
       from iterations/<n>/global.rules.yaml.
    2. AI classifier pre-buckets each rule (promote / iteration_only)
       and the row pre-ticks accordingly.
    3. Show them via review_list (ui/review_list.py). User ticks
       rules to promote, optionally drills into alternatives, can
       inline-edit text, then picks one of two terminal actions:
         - continue   close iteration with existing actions intact
         - regenerate clear cycle artifacts and redraft against the
                      new rule set
    4. Promote every ticked entry to project-root files —
       <project>/v84/<role>.rules.yaml or
       <project>/v84/global.rules.yaml. Unticked entries stay
       iteration-only.
    5. Dispatch on the explicit user choice:
         - continue    → write_handoff + advance to finish
         - regenerate  → _restart_cycle (back to round 1 / draft)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

import yaml

from core import coreyaml, iter_status, proposals
from core.context import active_roles, build_user_msgs
from core.stage import Stage
from core.util import default_log_dir, load_instruction
from core.versioning import archive_if_exists
from iteration.handoff import write_handoff
from llm import LLMConfig, call_json, resolve_llm
from ui import review_list


# -----------------------------------------------------------------------------
# Stage entry
# -----------------------------------------------------------------------------

def user_review(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Show accepted rules to user; on full accept, promote + close."""
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        raise RuntimeError(
            "no current_iteration set in core.yaml — user_review needs "
            "an in-flight iteration"
        )
    iteration_n = _iteration_number(parent_id)
    parent = coreyaml.find_by_id(data, parent_id)

    profile = project_dir / "v84" / "profile.yaml"
    roles = active_roles(profile)
    if not roles:
        raise RuntimeError("no active roles in profile.yaml")

    # Gather every accepted entry from per-role + globals.
    bundle = _collect_accepted(project_dir, iteration_n, roles)
    total = sum(len(s.get("rows") or []) for s in bundle["sections"])
    if total == 0:
        # Nothing to promote — render the handoff (actions still
        # need to ship even when no new rules accumulated) then
        # advance to the finish stage which verifies coverage.
        print(
            "  (no accepted rules from this iteration to review)",
            file=sys.stderr,
        )
        write_handoff(project_dir, iteration_n)
        iter_status.advance_to(project_dir, iteration_n, "finish")
        return project_dir / "v84" / "core.yaml"

    # AI pre-classifies each accepted rule into:
    #   - promote        → goes to <project>/v84/{role|global}.rules.yaml
    #                      (binds future iterations)
    #   - iteration_only → stays in iteration files; doesn't promote
    #                      (one-shot ruling for this iteration's scope)
    # User confirms or flips per item; defaults match the AI's read so
    # the user only walks items they want to override.
    classifications = _load_or_classify_rules(
        project_dir=project_dir,
        parent=parent,
        iteration_n=iteration_n,
        bundle=bundle,
        cfg=cfg,
    )
    _apply_classifications(bundle, classifications)

    # Show the review_list. User ticks rules to promote, optionally
    # drills into alternatives, optionally inline-edits, then picks
    # one of two terminal actions: continue (close iteration) or
    # regenerate (restart cycle against the new rule set).
    summary = _build_summary(iteration_n, total)
    result = review_list(
        bundle["sections"],
        summary=summary,
        enable_tick=True,
        enable_pick=True,
        enable_edit=True,
        actions=[
            {
                "name":  "continue",
                "key":   "c",
                "label": "promote & continue",
                "kind":  "commit",
                "confirm": {
                    "title": "Promote and continue",
                    "bullets": [
                        "Promote ticked rules to project root",
                        "Write tasks.md handoff",
                        "Advance to finish",
                    ],
                    "body": "Existing actions stay; iteration closes "
                            "after finish verifies coverage.",
                },
            },
            {
                "name":  "regenerate",
                "key":   "r",
                "label": "promote & regenerate",
                "kind":  "commit",
                "confirm": {
                    "title": "Promote and regenerate",
                    "bullets": [
                        "Promote ticked rules to project root",
                        "Clear cycle artifacts (drafts, corrections, "
                        "reviewer files)",
                        "Reset to round 1 / draft",
                    ],
                    "body": "This redrafts every action against the "
                            "new rule set. ~Cost: full cycle re-run.",
                },
            },
        ],
        status_fn=_status_line,
    )
    if result is None:
        raise RuntimeError(
            "user_review cancelled — re-run when ready to settle "
            "this iteration"
        )

    # Walk results: ticked rows promote with their (possibly edited)
    # text; unticked rows decline (kept iteration-only — don't bind
    # future iterations).
    promote: list[dict] = []   # {scope, role|None, record, final_text}
    declined: list[dict] = []  # {scope, role|None, record}

    for section in result["sections"]:
        meta = section["_meta"]
        for row in section.get("rows") or []:
            record = row.get("_record")
            if record is None:
                continue
            if row.get("ticked"):
                promote.append({
                    **meta,
                    "record": record,
                    "final_text": (row.get("text") or "").strip(),
                })
            else:
                declined.append({**meta, "record": record})

    # Promote every ticked entry. Picked/custom values become the rule.
    _promote_all(project_dir, promote)
    _writeback_edits(project_dir, iteration_n, promote)
    _writeback_declines(project_dir, iteration_n, declined)

    if result["action"] == "continue":
        # User explicitly chose to keep this iteration's actions.
        # Render the handoff document for the external implementer,
        # then advance to the finish stage — the iteration only
        # TRULY closes once finish verifies every action's files
        # exist and carry the right tag.
        write_handoff(project_dir, iteration_n)
        iter_status.advance_to(project_dir, iteration_n, "finish")
        kept = len(promote)
        msg = f"{kept} rule(s) promoted to project root"
        if declined:
            msg += f"; {len(declined)} kept iteration-only"
        print(
            f"  ✓ rules promoted, handoff written — next: run your "
            f"implementer, then re-run v84 for the finish gate. {msg}",
            file=sys.stderr,
        )
    else:   # regenerate
        # User explicitly chose to redraft against the new rule set.
        # Clean cycle artifacts and restart from draft so writers
        # re-emit against the rules now sitting in project root.
        _restart_cycle(project_dir, iteration_n, profile)
        changed_count = sum(
            1 for it in promote
            if it["final_text"] != _original_text_for(it["record"])
        )
        print(
            f"  ✓ {len(promote)} rule(s) promoted "
            f"({changed_count} changed, {len(declined)} declined). "
            f"Restarting drafting against the new rule set.",
            file=sys.stderr,
        )
    return project_dir / "v84" / "core.yaml"


def _status_line(sections: list[dict]) -> str:
    """Status line shown beneath the review_list action bar.
    Counts edited rules to surface the regen-vs-continue tradeoff."""
    edited = 0
    ticked = 0
    total = 0
    for section in sections:
        for row in section.get("rows") or []:
            total += 1
            if row.get("ticked"):
                ticked += 1
            record = row.get("_record") or {}
            original = (record.get("text") or record.get("proposal") or "").strip()
            if (row.get("text") or "").strip() != original:
                edited += 1
    parts = [f"{ticked}/{total} ticked for promotion"]
    if edited:
        parts.append(
            f"{edited} edited from lead's wording — `r` regen "
            f"redrafts to honour them"
        )
    return " · ".join(parts)


def _original_text_for(record: dict) -> str:
    """Re-derive the lead's original rule text for a record."""
    return (record.get("text") or record.get("proposal") or "").strip()


# -----------------------------------------------------------------------------
# Read accepted entries → review_list sections
# -----------------------------------------------------------------------------

def _collect_accepted(
    project_dir: Path, iteration_n: int, roles: list[str],
) -> dict:
    """Build the {sections} payload for review_list + remember per-record
    metadata (scope/role) so we can route promotions later."""
    sections: list[dict] = []

    # Globals first.
    global_records = _read_global_accepted(project_dir, iteration_n)
    if global_records:
        sections.append(_make_section(
            title="Global rules",
            records=global_records,
            meta={"scope": "global", "role": None},
        ))

    # Then per role.
    for role in roles:
        records = proposals.accepted_rules(project_dir, iteration_n, role)
        if records:
            sections.append(_make_section(
                title=f"{role.capitalize()} rules",
                records=records,
                meta={"scope": "role", "role": role},
            ))

    return {"sections": sections}


def _make_section(*, title: str, records: list[dict], meta: dict) -> dict:
    """Pack records into a review_list section with embedded metadata.

    Each row carries the rule's id (`label`), the lead's wording
    (`text`), the available alternatives (the original `proposal`
    plus its `alternatives`, deduped against the rule's text), and
    the source record under `_record` so the caller can route
    promotions/writebacks later. `ticked` is set later by
    `_apply_classifications` based on the AI bucket; `tag` is also
    set there.
    """
    rows: list[dict] = []
    for r in records:
        text = (r.get("text") or r.get("proposal") or "").strip()
        proposal = (r.get("proposal") or "").strip()
        original_alts = [str(a).strip() for a in (r.get("alternatives") or [])
                         if str(a).strip()]
        # Build the full option pool: rule's current text first
        # (always, so the picker has a "current" entry), then proposal
        # (if different), then original alternatives.
        seen: set[str] = set()
        all_options: list[str] = []
        if text:
            all_options.append(text)
            seen.add(text)
        if proposal and proposal not in seen:
            all_options.append(proposal)
            seen.add(proposal)
        for alt in original_alts:
            if alt not in seen:
                all_options.append(alt)
                seen.add(alt)

        rows.append({
            "label":        r.get("id", "?"),
            "text":         text,
            "alternatives": all_options,
            "ticked":       False,    # set by _apply_classifications
            "tag":          "",       # set by _apply_classifications
            "_record":      r,
        })
    return {"title": title, "rows": rows, "_meta": meta}


def _read_global_accepted(
    project_dir: Path, iteration_n: int,
) -> list[dict]:
    """Read iterations/<n>/global.rules.yaml filtered to status=accepted."""
    p = (project_dir / "v84" / "iterations" / str(iteration_n)
         / "global.rules.yaml")
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        return []
    return [r for r in data if isinstance(r, dict) and r.get("status") == "accepted"]


# -----------------------------------------------------------------------------
# Promotion to project root
# -----------------------------------------------------------------------------

def _promote_all(project_dir: Path, items: list[dict]) -> None:
    """Promote each item to its destination root file using the
    user's `final_text` (which may be the lead's original wording,
    a picked alternative, or custom-typed text). Root records carry
    only id + text — pending-time fields drop off."""
    by_dest: dict[tuple, list[dict]] = {}
    for it in items:
        key = (it["scope"], it["role"])
        by_dest.setdefault(key, []).append({
            "id": it["record"].get("id"),
            "text": it["final_text"],
        })

    for (scope, role), records in by_dest.items():
        if scope == "global":
            proposals.append_project_rules(project_dir, records)
            label = "global.rules.yaml"
        else:
            proposals.append_project_role_rules(project_dir, role, records)
            label = f"{role}.rules.yaml"
        print(
            f"  ✓ promoted {len(records)} rule(s) → v84/{label}",
            file=sys.stderr,
        )


# -----------------------------------------------------------------------------
# Edits / declines write-back to iteration files
# -----------------------------------------------------------------------------

def _writeback_edits(
    project_dir: Path, iteration_n: int, edits: list[dict],
) -> None:
    """For each edited entry (user picked an alternative or wrote
    custom text), update the text field in the iteration file and
    flag `edited_by_user: true` so Step 2 (action review) can tell
    which rules diverged from the lead's original wording — those
    are the candidates for action regeneration."""
    for it in edits:
        rid = it["record"].get("id")
        new_text = it["final_text"]
        path = _resolve_iteration_path(project_dir, iteration_n, it)
        records = _read_iteration_file(path)
        for r in records:
            if r.get("id") == rid:
                r["text"] = new_text
                r["edited_by_user"] = True
                break
        _write_iteration_file(path, records)


def _writeback_declines(
    project_dir: Path, iteration_n: int, declines: list[dict],
) -> None:
    """For each declined entry, mark status: rejected_by_user so the
    record stays for audit but no longer counts as accepted."""
    for it in declines:
        rid = it["record"].get("id")
        path = _resolve_iteration_path(project_dir, iteration_n, it)
        records = _read_iteration_file(path)
        for r in records:
            if r.get("id") == rid:
                r["status"] = "rejected_by_user"
                break
        _write_iteration_file(path, records)


def _resolve_iteration_path(
    project_dir: Path, iteration_n: int, item: dict,
) -> Path:
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    if item["scope"] == "global":
        return iter_dir / "global.rules.yaml"
    return iter_dir / f"{item['role']}.rules.yaml"


def _read_iteration_file(p: Path) -> list[dict]:
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def _write_iteration_file(p: Path, records: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump(records, default_flow_style=False, sort_keys=False,
                       allow_unicode=True, width=10000),
        encoding="utf-8",
    )


# -----------------------------------------------------------------------------
# Iteration close
# -----------------------------------------------------------------------------

def _restart_cycle(project_dir: Path, iteration_n: int, profile: Path) -> None:
    """Clear the iteration so drafting re-runs from scratch against
    the user's finalised rule set (now sitting in project-root
    rules files).

    Kept on disk:
        - status.yaml (reset to {round: 1, next_step: draft})
        - plan.yaml (iteration's sub-task plan, independent of rules)

    Deleted (everything else regenerates):
        - <role>.yaml (writer drafts)
        - <role>.corrections{,-applied,-rejected}.yaml
        - <role>.rules.yaml
          (promoted rules now live in <project>/v84/<role>.rules.yaml;
          declined entries are dropped entirely)
        - global.rules.yaml
          (promoted globals now live in <project>/v84/global.rules.yaml)
        - reviews/<role>.<reviewer>.yaml (per-lens corrections)
    """
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    roles = active_roles(profile)

    # <role>.yaml is the writer's draft — archived (when logging on)
    # so research can compare pre-restart vs post-restart drafts.
    # Everything else is deleted; their content (corrections /
    # rules) is already preserved through stacked record ids
    # within a round, and a fresh restart starts those over anyway.
    for role in roles:
        archive_if_exists(iter_dir / f"{role}.yaml", project_dir=project_dir)

    plain_unlink: list[Path] = [
        iter_dir / "global.rules.yaml",
    ]
    for role in roles:
        plain_unlink.extend([
            iter_dir / f"{role}.corrections.yaml",
            iter_dir / f"{role}.corrections-applied.yaml",
            iter_dir / f"{role}.corrections-rejected.yaml",
            iter_dir / f"{role}.rules.yaml",
        ])
    for p in plain_unlink:
        if p.exists():
            p.unlink()

    reviews_dir = iter_dir / "reviews"
    if reviews_dir.exists():
        for f in reviews_dir.glob("*.yaml"):
            f.unlink()

    # Wipe the rendered-context cache too — rules just changed,
    # so cached blocks like rules_block would still reflect the old
    # rule set if their source mtimes didn't change in a way that
    # invalidates them.
    cache_dir = iter_dir / "cache"
    if cache_dir.exists():
        for f in cache_dir.glob("*.md"):
            f.unlink()

    # Reset to round 1 with every active role parked at draft, so the
    # cycle stage starts fresh and re-runs every role end-to-end.
    profile_path = project_dir / "v84" / "profile.yaml"
    iter_status.init_pipeline(
        project_dir, iteration_n,
        round=1,
        roles=active_roles(profile_path),
        starting_step=iter_status.STEP_DRAFT,
    )


# -----------------------------------------------------------------------------
# UI summary builder
# -----------------------------------------------------------------------------

def _build_summary(iteration_n: int, total: int) -> str:
    return (
        f"Iteration {iteration_n} produced {total} accepted rule(s). "
        f"The actions you'll see\n"
        f"in the next step were drafted with these rules in scope. "
        f"If you OVERRIDE or DECLINE any rule below, the cycle\n"
        f"will regenerate so the actions reflect your changes. "
        f"Accept the lead's wording as-is to keep the current draft."
    )


# -----------------------------------------------------------------------------
# Rule classification (AI pre-classifies promote vs iteration_only)
# -----------------------------------------------------------------------------

def _classification_path(project_dir: Path, iteration_n: int) -> Path:
    return (
        project_dir / "v84" / "iterations" / str(iteration_n)
        / "rule_classifications.yaml"
    )


def _load_or_classify_rules(
    *,
    project_dir: Path,
    parent: Any,
    iteration_n: int,
    bundle: dict,
    cfg: Optional[LLMConfig],
) -> dict[str, dict]:
    """Return {id: {bucket, reason}} for every accepted rule.

    Reuses cached classifications when the cached set of ids matches
    the current accepted set. Otherwise fires the classifier LLM call
    and persists. Falls back to deterministic defaults when cfg is
    missing or the call fails — every rule still gets a bucket so the
    UI never shows a half-classified list.
    """
    expected_ids: set[str] = set()
    for s in bundle["sections"]:
        for f in s.get("rows") or []:
            rid = f.get("_record", {}).get("id")
            if rid:
                expected_ids.add(rid)

    cache_path = _classification_path(project_dir, iteration_n)
    cached = _read_cached_classifications(cache_path)
    if cached and set(cached.keys()) == expected_ids:
        print(
            f"  ✓ classifications loaded from cache "
            f"({len(cached)} entries)",
            file=sys.stderr,
        )
        return cached

    if cfg is None:
        print(
            "  ⚠ no LLM cfg available — using deterministic classification "
            "defaults (everything → promote; user flips per item)",
            file=sys.stderr,
        )
        result = _default_classifications(bundle)
    else:
        try:
            result = _classify_rules_call(
                project_dir=project_dir,
                parent=parent,
                iteration_n=iteration_n,
                bundle=bundle,
                cfg=cfg,
            )
        except Exception as err:
            print(
                f"  ⚠ classifier failed ({err!r}); falling back to "
                f"deterministic defaults",
                file=sys.stderr,
            )
            result = {}

        # Backfill any rule the classifier missed with the deterministic
        # default — partial classifier output is still better than re-asking
        # the user from scratch.
        defaults = _default_classifications(bundle)
        for rid, default in defaults.items():
            result.setdefault(rid, default)

    _write_cached_classifications(cache_path, result)
    return result


def _classify_rules_call(
    *,
    project_dir: Path,
    parent: Any,
    iteration_n: int,
    bundle: dict,
    cfg: LLMConfig,
) -> dict[str, dict]:
    """Single LLM call. Returns {id: {bucket, reason}}."""
    system, schema = load_instruction("iteration", "classify-rules")

    rules_yaml = _render_rules_for_classifier(bundle)
    n_rules = sum(len(s.get("rows") or []) for s in bundle["sections"])

    user_msgs = build_user_msgs(
        project_dir, parent, iteration_n,
        {
            "plan":                          True,
            "active_roles":                  True,
            "stack":                         "all",
            "layout":                        None,
            "role_definition":               None,
            "history":                       None,
            "actions":                       None,
            "corrections":                   None,
            "corrections_pending":           None,
            "corrections_rejected":          None,
            "corrections_applied":           None,
            "corrections_rejected_history":  None,
            "rules":                         None,
            "rules_pending":                 None,
            "rules_rejected":                None,
            "trailing": (
                "Accepted rules to classify (every entry must appear "
                "exactly once in your `classifications` output):\n\n"
                f"```yaml\n{rules_yaml}\n```\n\n"
                "Decide bucket per rule."
            ),
        },
    )

    classify_cfg = _classify_cfg(project_dir, fallback=cfg)
    print(
        f"  classifying {n_rules} rule(s) — model {classify_cfg.model} "
        f"@ {classify_cfg.url}",
        file=sys.stderr,
    )
    response = call_json(
        classify_cfg,
        system=system,
        user_msgs=user_msgs,
        response_schema=schema,
        log_name=f"iter-{iteration_n}-classify-rules",
        log_dir=default_log_dir(),
    )
    return _parse_classifier_response(response)


def _render_rules_for_classifier(bundle: dict) -> str:
    """Render every accepted rule as a flat YAML list of
    `{id, scope, role, text}` for the classifier's user message."""
    rows: list[dict] = []
    for s in bundle["sections"]:
        meta = s["_meta"]
        for f in s.get("rows") or []:
            r = f["_record"]
            rid = r.get("id")
            if not rid:
                continue
            text = (r.get("text") or r.get("proposal") or "").strip()
            rows.append({
                "id": rid,
                "scope": meta["scope"],
                "role": meta["role"],
                "text": text,
            })
    return yaml.safe_dump(
        rows,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=10000,
    )


_BUCKETS = {"promote", "iteration_only"}


def _parse_classifier_response(data: dict) -> dict[str, dict]:
    """Reshape the schema-validated classifier response into a
    {id: {bucket, reason}} lookup the rest of user_review consumes."""
    if not isinstance(data, dict):
        return {}
    raw = data.get("classifications") or []
    if not isinstance(raw, list):
        return {}
    out: dict[str, dict] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        rid = item.get("id")
        bucket = item.get("bucket")
        if not isinstance(rid, str) or not rid.strip():
            continue
        if bucket not in _BUCKETS:
            continue
        reason = item.get("reason") or ""
        if not isinstance(reason, str):
            reason = str(reason)
        out[rid.strip()] = {
            "id": rid.strip(),
            "bucket": bucket,
            "reason": reason.strip(),
        }
    return out


def _read_cached_classifications(p: Path) -> dict[str, dict]:
    if not p.exists():
        return {}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    if not isinstance(data, dict):
        return {}
    raw = data.get("classifications") or []
    if not isinstance(raw, list):
        return {}
    out: dict[str, dict] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        rid = item.get("id")
        bucket = item.get("bucket")
        if not rid or bucket not in _BUCKETS:
            continue
        out[rid] = {
            "id": rid,
            "bucket": bucket,
            "reason": (item.get("reason") or "").strip(),
        }
    return out


def _write_cached_classifications(p: Path, classifications: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump(
            {"classifications": list(classifications.values())},
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=10000,
        ),
        encoding="utf-8",
    )


def _default_classifications(bundle: dict) -> dict[str, dict]:
    """Deterministic fallback when the classifier is unavailable.
    Default everything to `promote`; the user can flip down to
    iteration-only per item via the review_list."""
    out: dict[str, dict] = {}
    for s in bundle["sections"]:
        meta = s["_meta"]
        for f in s.get("rows") or []:
            rid = f.get("_record", {}).get("id")
            if not rid:
                continue
            if meta["scope"] == "global":
                reason = "Global rule (cross-lead validated)."
            else:
                reason = "Role-scoped rule — durable by default."
            out[rid] = {"id": rid, "bucket": "promote", "reason": reason}
    return out


def _apply_classifications(
    bundle: dict, classifications: dict[str, dict],
) -> None:
    """Mutate bundle's rows so the review_list pre-selects the
    classifier's bucket choice.

    promote rules → row starts ticked (will go to project root).
    iteration_only rules → row starts unticked (kept iteration-only).
    Either way, the AI's reason surfaces as the row's `tag` so the
    user sees the bucket + rationale at a glance without drilling in.
    """
    for s in bundle["sections"]:
        for row in s.get("rows") or []:
            rid = row.get("_record", {}).get("id")
            if not rid:
                continue
            cls = classifications.get(rid)
            if not cls:
                row["ticked"] = True   # default to promote when AI is silent
                row["tag"] = ""
                continue
            bucket = cls.get("bucket", "promote")
            reason = (cls.get("reason") or "").strip()
            if bucket == "iteration_only":
                row["ticked"] = False
                row["tag"] = "AI: iteration-only"
            else:
                row["ticked"] = True
                row["tag"] = "AI: promote"
            if reason:
                # Append a short reason after the bucket; keep it
                # compact so the tag fits on the row header line.
                row["tag"] = f"{row['tag']} — {reason[:60]}"


def _classify_cfg(
    project_dir: Path, *, fallback: LLMConfig,
) -> LLMConfig:
    """Classifier runs on the single tier (one-shot, low-throughput)."""
    try:
        return resolve_llm(
            project_dir=project_dir, tier="single", interactive=False,
        )
    except RuntimeError:
        return fallback


# -----------------------------------------------------------------------------
# Stage glue
# -----------------------------------------------------------------------------

def _iteration_number(task_id: str) -> int:
    return int(task_id.split(".")[0].split("-")[1])


def _is_done(project_dir: Path) -> bool:
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        return True   # iteration already closed
    iteration_n = _iteration_number(parent_id)
    return iter_status.stage_is_done(project_dir, iteration_n, "user_review")


STAGE = Stage(
    name="user_review",
    title="User reviews accepted rules; iteration close",
    priority=1404,
    produces="iterations/<n>/status.yaml#next_step=done",
    requires=("architect_validate",),
    needs_brief=False,
    is_done=_is_done,
    call=user_review,
)
