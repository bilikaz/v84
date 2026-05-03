"""
versioning.py — opt-in archival of LLM-output files that mutate.

When `profile.yaml` carries `project.logging: true`, calls to
`versioned_write(path, content, project_dir=...)` archive the
existing file as `<path>.<n>` (next free integer) before writing
the new content. If the new content matches the existing
byte-for-byte, no archive is created (no version bump for nothing).

Currently used only for `iterations/<n>/<role>.yaml` — the
writer's draft, which gets patched in place across rounds and is
the most research-interesting file to track across runs (lets you
compare round-1 draft vs round-2 patch vs round-3 patch and see
how the cycle evolved the spec).

Other LLM outputs (corrections, conv/dec, reviews) preserve
their full history via id-stacked records or per-round files
already, so don't need versioning.

Naming convention: flat, same directory.
    iterations/1/frontend.yaml         ← current
    iterations/1/frontend.yaml.1       ← oldest archive (round 1)
    iterations/1/frontend.yaml.2       ← next archive (round 2)
    iterations/1/frontend.yaml.3       ← most recent before current
"""

from __future__ import annotations

from pathlib import Path

import yaml


def versioned_write(
    path: Path, content: str, *, project_dir: Path,
) -> None:
    """Write content to path; archive existing first when logging
    is enabled in profile.yaml AND content actually changed."""
    if not _logging_enabled(project_dir):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return

    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
        except OSError:
            existing = None
        if existing == content:
            return   # no change, no archive
        archive = _next_archive_path(path)
        path.rename(archive)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def archive_if_exists(path: Path, *, project_dir: Path) -> None:
    """Archive existing file (no replacement write). Used by
    restart_cycle / clear paths that would otherwise unlink the
    file — when logging is on, preserve it as .<n> for research."""
    if not path.exists():
        return
    if not _logging_enabled(project_dir):
        path.unlink()
        return
    archive = _next_archive_path(path)
    path.rename(archive)


def _next_archive_path(path: Path) -> Path:
    n = 1
    while path.with_name(f"{path.name}.{n}").exists():
        n += 1
    return path.with_name(f"{path.name}.{n}")


def _logging_enabled(project_dir: Path) -> bool:
    profile = project_dir / "v84" / "profile.yaml"
    if not profile.exists():
        return False
    try:
        data = yaml.safe_load(profile.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return False
    project = data.get("project") or {}
    return bool(project.get("logging"))
