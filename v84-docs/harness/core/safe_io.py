"""
safe_io — Concurrency-safe file I/O for harness state.

Every important file the harness reads or mutates (profile.yaml,
status.yaml, core.yaml, the per-role corrections / rules YAMLs, …)
can now be touched by multiple stage workers in parallel. The naïve
`Path.read_text` / `Path.write_text` pair is unsafe under that
model: `write_text` truncates before writing, so a sibling reader
in that window sees an empty/partial file, applies a regex-or-parse
to the empty string, gets garbage, and may write garbage back.

This module is the single concurrency-safe primitive set.

Guarantees
----------
1. **Atomic writes.** `write_text` / `write_yaml` write to a tempfile
   in the same directory and `os.replace` onto the target. Concurrent
   readers see either the prior content or the new content — never a
   half-written file.
2. **Lock-coupled reads.** `read_text` / `read_yaml` acquire the same
   per-path lock writers hold, so a read concurrent with an
   in-progress update **blocks** until the writer commits, then
   returns the post-update content. No mid-flight nonsense.
3. **Read-modify-write helpers.** `update_yaml(path)` yields the
   parsed value (or a default), lets you mutate it, then atomic-writes
   the result on exit — under the lock the whole way.
4. **Per-path locks, lazy.** Locks live in a process-wide registry
   keyed by the resolved path. Different files don't serialise
   against each other.

Usage
-----

    from core import safe_io

    # Read (lock-protected)
    text = safe_io.read_text(path)
    data = safe_io.read_yaml(path, default={})

    # One-shot write (atomic)
    safe_io.write_text(path, "...")
    safe_io.write_yaml(path, {"key": "val"})

    # Read-modify-write (atomic, exclusive)
    with safe_io.update_yaml(path, default={}) as data:
        data["foo"] = "bar"

    # Raw lock (for code that does its own read/write inside)
    with safe_io.lock(path):
        ...

    # Bytes / generic text RMW
    with safe_io.update_text(path, default="") as holder:
        # holder.text is the current content; set holder.text to
        # whatever should be persisted on exit.
        holder.text = holder.text.replace("foo", "bar")
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional

import yaml


# -----------------------------------------------------------------------------
# Per-path lock registry
# -----------------------------------------------------------------------------

_REGISTRY_LOCK = threading.Lock()
_LOCKS: dict[str, threading.RLock] = {}


def _lock_for(path: Path) -> threading.RLock:
    """Return (and lazily create) the lock guarding `path`. Keyed by
    the absolute string form so two `Path` objects pointing at the
    same file share one lock. RLock so update_yaml's lock holder can
    re-enter via read_yaml without deadlocking itself."""
    key = str(path.resolve()) if path.is_absolute() or path.exists() else str(path.absolute())
    with _REGISTRY_LOCK:
        lk = _LOCKS.get(key)
        if lk is None:
            lk = threading.RLock()
            _LOCKS[key] = lk
        return lk


@contextmanager
def lock(path: Path) -> Iterator[None]:
    """Acquire `path`'s lock for arbitrary read-modify-write. Use the
    higher-level helpers (`read_text`, `update_yaml`, etc.) when you
    can — this is the escape hatch for code that needs to do something
    the helpers don't cover."""
    lk = _lock_for(path)
    with lk:
        yield


# -----------------------------------------------------------------------------
# Reads (lock-protected)
# -----------------------------------------------------------------------------

def read_text(path: Path, default: Optional[str] = None) -> Optional[str]:
    """Read `path` as text under its lock. Returns `default` when the
    file does not exist (caller's choice — None for "no file", "" for
    "treat missing as empty")."""
    lk = _lock_for(path)
    with lk:
        if not path.exists():
            return default
        return path.read_text(encoding="utf-8")


def read_yaml(path: Path, default: Any = None) -> Any:
    """Read `path` and parse it as YAML under its lock. Returns
    `default` when the file is missing or empty. Malformed YAML
    raises — callers wrap when they want to swallow."""
    text = read_text(path, default=None)
    if text is None:
        return default
    parsed = yaml.safe_load(text)
    if parsed is None:
        return default
    return parsed


# -----------------------------------------------------------------------------
# Writes (atomic)
# -----------------------------------------------------------------------------

def write_text(path: Path, content: str) -> Path:
    """Atomically replace `path` with `content`. Holds the lock for
    the duration so concurrent readers block until commit."""
    lk = _lock_for(path)
    with lk:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
    return path


def write_yaml(path: Path, data: Any) -> Path:
    """Atomically write `data` as YAML. Same dumper settings the
    rest of the harness uses (block style, key order preserved,
    unicode passthrough)."""
    text = yaml.safe_dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=10000,
    )
    return write_text(path, text)


# -----------------------------------------------------------------------------
# Read-modify-write
# -----------------------------------------------------------------------------

@dataclass
class _TextHolder:
    """Mutable container for `update_text`. Set `.text` to the new
    content; the context manager atomic-writes it on exit."""
    text: str


@contextmanager
def update_text(path: Path, default: str = "") -> Iterator[_TextHolder]:
    """Lock-protected read-modify-write of a text file. The yielded
    holder starts with the current content (or `default` if missing);
    set `holder.text` to what should be on disk after this block.
    Atomic write on exit, only when the content actually changed."""
    lk = _lock_for(path)
    with lk:
        if path.exists():
            initial = path.read_text(encoding="utf-8")
        else:
            initial = default
        holder = _TextHolder(text=initial)
        yield holder
        if holder.text != initial:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(holder.text, encoding="utf-8")
            os.replace(tmp, path)


@contextmanager
def update_yaml(path: Path, default: Any = None) -> Iterator[Any]:
    """Lock-protected read-modify-write of a YAML file. Yields the
    parsed value (or a fresh copy of `default` if missing); the
    caller mutates it in place, and on exit it's atomically written
    back. If `default` is `None`, you'll get None for missing files —
    pass an empty dict / list when you want to start from scratch.

    The yielded value IS what gets serialised — don't reassign the
    name (that just rebinds your local). Mutate in place."""
    lk = _lock_for(path)
    with lk:
        if path.exists():
            text = path.read_text(encoding="utf-8")
            data = yaml.safe_load(text)
            if data is None:
                # Empty file; treat like missing for the purposes of
                # the default. Caller may still get a fresh container.
                data = _fresh(default)
        else:
            data = _fresh(default)
        yield data
        # Always write back — even if `data` looks unchanged, the
        # serialiser may produce a slightly different file (whitespace,
        # ordering when sort_keys=False) and that's fine. Keeps the
        # contract simple.
        path.parent.mkdir(parents=True, exist_ok=True)
        text = yaml.safe_dump(
            data,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=10000,
        )
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)


def _fresh(default: Any) -> Any:
    """Return a fresh copy of `default` so callers mutating dict/list
    defaults don't accidentally share state across update_yaml calls."""
    if isinstance(default, dict):
        return dict(default)
    if isinstance(default, list):
        return list(default)
    return default
