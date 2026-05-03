"""
multi_spinner — N-track spinner for fan-out calls.

One line per track, all updating in place on the main terminal.
Each track has its own start time, animation, and ✓/✗ on completion.

Used by stages that fan out (writers per role, reviewers per lens).
Conforms to the same TTY/non-TTY split as Spinner — never writes
ANSI on a non-TTY stream.

Usage:

    with MultiSpinner(["frontend", "devops"]) as ms:
        results = call_many(cfg, specs, log_dir=..., progress=ms)

`progress` callback API (used by llm.call_many):
    .started(idx: int) -> None
    .done(idx: int, error: BaseException | None) -> None
"""

from __future__ import annotations

import itertools
import sys
import threading
import time
from typing import Optional, TextIO


class MultiSpinner:
    """N-track spinner. Each track shows queued → running (Ns) → ✓/✗ (Xs)."""

    FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    INTERVAL_S = 0.1

    def __init__(self, labels: list[str], stream: Optional[TextIO] = None):
        self.labels = list(labels)
        self.stream: TextIO = stream if stream is not None else sys.stderr
        self._tty = self.stream.isatty()
        self._n = len(self.labels)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._starts: list[Optional[float]] = [None] * self._n
        self._ends: list[Optional[float]] = [None] * self._n
        self._errors: list[Optional[BaseException]] = [None] * self._n
        # Per-track streaming progress, populated by llm.client._post when
        # a per-call `on_stream` hook is plumbed through. Each entry is
        # `{phase, content, reasoning, tail, since}` or None.
        self._streams: list[Optional[dict]] = [None] * self._n
        # Pad labels so the spinner column aligns across tracks.
        self._lw = max((len(l) for l in self.labels), default=0)

    # ------------------------------------------------------------------
    # progress callbacks (used by llm.call_many)
    # ------------------------------------------------------------------

    def started(self, idx: int) -> None:
        with self._lock:
            if 0 <= idx < self._n and self._starts[idx] is None:
                self._starts[idx] = time.monotonic()

    def done(self, idx: int, error: Optional[BaseException]) -> None:
        with self._lock:
            if 0 <= idx < self._n:
                if self._starts[idx] is None:
                    self._starts[idx] = time.monotonic()
                self._ends[idx] = time.monotonic()
                self._errors[idx] = error
                # Keep the last stream snapshot — `_format` strips the
                # phase + tail on ended tracks and shows just the final
                # char counts as a tiny stats footnote.

    def stream_update(
        self, idx: int, *, phase: str,
        content: int, reasoning: int, tail: str,
        loop_ratio: Optional[float] = None,
        loop_streak: int = 0,
    ) -> None:
        """Per-call streaming hook. Plumbed in via call_many → call_json
        → _post when MultiSpinner is the progress callback. Stores the
        latest snapshot; the paint loop reads it next frame.

        `loop_ratio` and `loop_streak` come from `_post`'s loop detector;
        rendered as `loop:R(N/M)` so the operator sees the streak
        building up before a kill fires."""
        with self._lock:
            if 0 <= idx < self._n:
                self._streams[idx] = {
                    "phase": phase,
                    "content": content,
                    "reasoning": reasoning,
                    "tail": tail,
                    "loop_ratio": loop_ratio,
                    "loop_streak": loop_streak,
                    "since": time.monotonic(),
                }

    # ------------------------------------------------------------------
    # context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "MultiSpinner":
        if self._n == 0:
            return self

        if self._tty:
            # Reserve N lines, then walk the cursor back up to the
            # first track so subsequent paints overwrite in place.
            self.stream.write("\n" * self._n)
            self.stream.write(f"\033[{self._n}A")
            self.stream.flush()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        else:
            for label in self.labels:
                print(f"→ {label}", file=self.stream, flush=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._n == 0:
            return

        if self._thread is not None:
            self._stop.set()
            self._thread.join(timeout=1.0)

        # One final paint that does NOT walk the cursor back — cursor
        # ends below the last track so normal output flows on.
        self._paint(frame="⠋", final=True)

    # ------------------------------------------------------------------
    # animation loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        frames = itertools.cycle(self.FRAMES)
        while not self._stop.is_set():
            self._paint(frame=next(frames), final=False)
            self._stop.wait(self.INTERVAL_S)

    def _paint(self, *, frame: str, final: bool) -> None:
        if not self._tty:
            return
        with self._lock:
            now = time.monotonic()
            for i in range(self._n):
                line = self._format(i, frame, now)
                # \r → col 0; \033[K → clear to end of line; \n → next track
                self.stream.write(f"\r\033[K{line}\n")
            if not final:
                # Walk cursor back to first track for the next paint.
                self.stream.write(f"\033[{self._n}A")
            self.stream.flush()

    def _format(self, i: int, frame: str, now: float) -> str:
        label = self.labels[i].ljust(self._lw)
        start = self._starts[i]
        end = self._ends[i]
        err = self._errors[i]
        stream = self._streams[i]
        if end is not None:
            mark = "✓" if err is None else "✗"
            elapsed = (end - start) if start is not None else 0.0
            base = f"  {mark} {label}  ({elapsed:.1f}s)"
            if stream:
                # Final stats footnote — no phase, no tail, just totals
                # so the row stays readable but the run's volume is
                # visible at a glance.
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
