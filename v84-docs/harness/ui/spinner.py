"""
spinner — Process-wide dynamic spinner for concurrent LLM calls.

A single painter shared across every fan-out path. Tasks register
when they start and unregister when they finish; the painter
repaints the full table in place every ~100ms. Rows come and go
at any time, which is what the per-role pipeline needs:
frontend.review's 4 reviewer rows, backend.draft's 1 row, and
devops.lead's 2 rows can all show up together in one block and
shrink/grow as the cycle progresses.

Usage is automatic — every call to `llm.call_json` and
`llm.call_many` registers a row and unregisters on completion. The
only public surface most code touches is `spinner.log(msg)` to emit
informational lines that scroll above the painted block instead of
landing inside it (which a raw `print(..., file=sys.stderr)` would
do).

Non-tty fallback: each register/done emits one plain line
("→ label" / "  ✓ label (Ns)") so logs stay readable in CI.
"""

from __future__ import annotations

import itertools
import sys
import threading
import time
from typing import Any, Optional, TextIO


class Spinner:
    """Process-wide dynamic spinner. Singleton — instantiate one
    instance at module load and share via the `GLOBAL` reference."""

    FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    INTERVAL_S = 0.1

    def __init__(self, stream: Optional[TextIO] = None):
        self.stream: TextIO = stream if stream is not None else sys.stderr
        self._tty = self.stream.isatty()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._next_id = 0
        # Insertion-ordered dict of rows. Each row:
        #   {label, start, end, error, stream}
        self._rows: dict[int, dict[str, Any]] = {}
        self._capacity = 0   # how many lines we painted last frame
        self._lw = 0         # current label-column width (max label len)

    # ------------------------------------------------------------------
    # public API — register/started/done/stream_update/unregister
    # ------------------------------------------------------------------

    def register(self, label: str) -> int:
        """Add a row to the table. Returns an id used for subsequent
        `started`/`done`/`stream_update`/`unregister` calls.

        Starts the painter thread on first registration."""
        with self._lock:
            rid = self._next_id
            self._next_id += 1
            self._rows[rid] = {
                "label": label,
                "start": None,
                "end": None,
                "error": None,
                "stream": None,
            }
            if len(label) > self._lw:
                self._lw = len(label)
            self._ensure_thread_locked()
            if not self._tty:
                print(f"→ {label}", file=self.stream, flush=True)
            return rid

    def started(self, rid: int) -> None:
        with self._lock:
            row = self._rows.get(rid)
            if row is not None and row["start"] is None:
                row["start"] = time.monotonic()

    def done(self, rid: int, error: Optional[BaseException]) -> None:
        with self._lock:
            row = self._rows.get(rid)
            if row is None:
                return
            if row["start"] is None:
                row["start"] = time.monotonic()
            row["end"] = time.monotonic()
            row["error"] = error
            if not self._tty:
                mark = "✓" if error is None else "✗"
                elapsed = row["end"] - row["start"]
                print(
                    f"  {mark} {row['label']} ({elapsed:.1f}s)",
                    file=self.stream, flush=True,
                )

    def stream_update(
        self, rid: int, *, phase: str,
        content: int, reasoning: int, tail: str,
        loop_ratio: Optional[float] = None,
        loop_streak: int = 0,
    ) -> None:
        """Per-call streaming hook. Called from `llm/client.py:_post`
        through `call_many`'s adapter. Stores the latest snapshot;
        the painter reads it next frame."""
        with self._lock:
            row = self._rows.get(rid)
            if row is not None:
                row["stream"] = {
                    "phase": phase,
                    "content": content,
                    "reasoning": reasoning,
                    "tail": tail,
                    "loop_ratio": loop_ratio,
                    "loop_streak": loop_streak,
                }

    def unregister(self, rid: int) -> None:
        """Remove a row from the table. The painter clears that line on
        its next frame."""
        with self._lock:
            self._rows.pop(rid, None)
            # Recompute label-width from what's left so a long-label
            # task leaving doesn't keep stretching the column forever.
            if self._rows:
                self._lw = max(len(r["label"]) for r in self._rows.values())
            else:
                self._lw = 0

    def log(self, msg: str) -> None:
        """Emit a one-shot informational line above the painted block.

        Use instead of `print(..., file=sys.stderr)` while the spinner
        is active — a raw print would land inside the block area and
        get overwritten by the next frame. This:
            1. Walks the cursor up to the top of the current block
            2. Clears the block area in place
            3. Writes the message there
            4. Resets capacity so the next paint redraws the block
               below the freshly-emitted line, leaving the line in the
               scroll-back history.

        Falls back to a plain print when there's no active block (the
        spinner is idle) or stderr isn't a tty (CI/log capture).
        """
        with self._lock:
            if self._capacity == 0 or not self._tty:
                print(msg, file=self.stream, flush=True)
                return
            cap = self._capacity
            out: list[str] = [f"\033[{cap}A"]    # cursor at block top
            for _ in range(cap):                 # erase old block content
                out.append("\r\033[K\n")
            out.append(f"\033[{cap}A")           # back to block top
            out.append(f"\r\033[K{msg}\n")       # emit the log line
            self._capacity = 0                   # next paint redraws block fresh
            self.stream.write("".join(out))
            self.stream.flush()

    # ------------------------------------------------------------------
    # painter
    # ------------------------------------------------------------------

    def _ensure_thread_locked(self) -> None:
        """Start the painter thread on first use. Caller holds _lock."""
        if self._thread is not None:
            return
        if not self._tty:
            return
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="Spinner",
        )
        self._thread.start()

    def shutdown(self) -> None:
        """Stop the painter thread. Called at process exit (or never;
        as a daemon it dies with the process)."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        frames = itertools.cycle(self.FRAMES)
        while not self._stop.is_set():
            self._paint(next(frames))
            self._stop.wait(self.INTERVAL_S)

    def _paint(self, frame: str) -> None:
        if not self._tty:
            return
        with self._lock:
            rows = list(self._rows.values())
            n = len(rows)
            cap = self._capacity
            now = time.monotonic()

            if n == 0 and cap == 0:
                return  # nothing on screen, nothing to paint

            out: list[str] = []
            if cap > 0:
                out.append(f"\033[{cap}A")  # walk up to top of last block

            # Paint current rows.
            for row in rows:
                line = self._format(row, frame, now)
                out.append(f"\r\033[K{line}\n")

            # If the block shrank, clear the now-vacant trailing lines.
            for _ in range(cap - n):
                out.append("\r\033[K\n")

            # Update capacity to current row count. After this paint the
            # cursor is exactly `n` lines below the block's top when
            # n >= cap, or `cap` lines below when n < cap. To make the
            # next paint's `\033[XA` correct, walk the cursor up so it
            # ends `n` lines below — i.e., at the bottom of the painted
            # rows, ignoring trailing cleared lines.
            if cap > n:
                up = cap - n
                out.append(f"\033[{up}A")
            self._capacity = n

            self.stream.write("".join(out))
            self.stream.flush()

    # ------------------------------------------------------------------
    # row formatting — borrowed from MultiSpinner._format with
    # dynamic label padding and the same stats footnote on done.
    # ------------------------------------------------------------------

    def _format(self, row: dict, frame: str, now: float) -> str:
        label = row["label"].ljust(self._lw)
        start = row["start"]
        end = row["end"]
        err = row["error"]
        stream = row["stream"]
        if end is not None:
            mark = "✓" if err is None else "✗"
            elapsed = (end - start) if start is not None else 0.0
            base = f"  {mark} {label}  ({elapsed:.1f}s)"
            if stream:
                stats = (
                    f"think:{stream['reasoning']:,}c "
                    f"content:{stream['content']:,}c"
                )
                return f"{base}   {stats}"
            return base
        if start is not None:
            elapsed = now - start
            base = f"  {frame} {label}  ({elapsed:.0f}s)"
            if stream:
                loop_tag = ""
                if stream.get("loop_ratio") is not None:
                    loop_tag = (
                        f" loop:{stream['loop_ratio']:.2f}"
                        f"({stream['loop_streak']}/3)"
                    )
                tail_line = (
                    f"{stream['phase']} — think:{stream['reasoning']:,}c "
                    f"content:{stream['content']:,}c"
                    f"{loop_tag} ▶ {stream['tail']!r}"
                )
                return f"{base}   {tail_line}"
            return base
        return f"    {label}  (queued)"


# Singleton instance. Every call_many in the harness shares this.
GLOBAL = Spinner()


def log(msg: str) -> None:
    """Emit `msg` to stderr. Routed through the global spinner so it
    never lands inside the painted block. Use everywhere the iteration
    code would otherwise `print(msg, file=sys.stderr)` while a fan-out
    is in flight."""
    GLOBAL.log(msg)
