#!/usr/bin/env python3
"""
util.py — Small helpers shared across the v84 harness.

Intentionally tiny. Path resolution + nothing else.
"""

from __future__ import annotations

from pathlib import Path


def v84_docs_root() -> Path:
    """Return the v84-docs root directory.

    Inferred from this file's location:
        v84-docs/harness/core/util.py   ← this file
    So v84-docs = parent of harness = parent of core = grandparent twice.
    """
    # Path(__file__) is this file. .resolve() makes it absolute. Three
    # .parent steps walk: util.py → core/ → harness/ → v84-docs/.
    return Path(__file__).resolve().parent.parent.parent


def project_root() -> Path:
    """Return the project root — the folder that contains v84-docs/.

    Computed from this file's location, not from the shell's CWD. That
    way `python3 v84-docs/harness/v84.py` works the same whether it's
    run from the project root, a subfolder, cron, a systemd unit, or
    anywhere else. CWD is unreliable; __file__ is not.

    Layout:
        <project-root>/
        ├── v84-docs/
        │   └── harness/
        │       └── v84.py, util.py, ...
        └── v84/           ← project state lives here
    """
    return v84_docs_root().parent


def instruction_path(*parts: str) -> Path:
    """Path to an instruction file.

    Examples:
        instruction_path("init", "decompose.md")
            → v84-docs/instructions/init/decompose.md
        instruction_path("executor", "agent.md")
            → v84-docs/instructions/executor/agent.md
    """
    return v84_docs_root() / "instructions" / Path(*parts)


def project_v84_dir(project_dir: Path) -> Path:
    """Return <project>/v84/, creating the folder if missing.

    Every project using v84 has a ./v84/ folder holding all its state.
    This helper is the one place we create that folder.
    """
    v84 = project_dir / "v84"
    v84.mkdir(parents=True, exist_ok=True)
    return v84


def default_log_dir() -> Path:
    """Default location for LLM call logs.

    Sibling directory to v84-docs/ so logs don't clutter the repo or
    the project tree. Everything under .v84-logs/ is safe to delete.
    """
    return v84_docs_root().parent / ".v84-logs"
