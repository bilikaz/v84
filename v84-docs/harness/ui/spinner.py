"""
spinner — live-elapsed progress for blocking calls.

Not a full-screen painter — stays on the main terminal and uses
in-place `\\r` overwrites. Used by stages to show that a long LLM
call is making progress.
"""

from __future__ import annotations

import itertools
import sys
import threading
import time
from typing import Optional, TextIO


class Spinner:
    """Context-manager spinner for LLM calls and other waits.

    Usage:
        with Spinner("calling qwen @ http://..."):
            response = make_long_call()

    Behaviour:
        - TTY stderr: animated spinner frame on the left of the
          message, refreshed every 0.1s, with a live "(Ns)" counter
          on the right. On exit, clears the spinner line and prints
          "✓ message (Xs)" or "✗ message (error)".
        - Non-TTY (pipe, CI, file redirect): prints "→ message" once
          at the start and the same "✓/✗ ...(Xs)" on exit. Never
          writes carriage returns or ANSI control codes — safe to log.

    The spinner uses a background daemon thread so the calling code
    blocks normally (e.g. urllib.urlopen inside) while the animation
    runs. The thread exits cleanly on the context manager's __exit__.
    """

    FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"   # braille pattern — smooth spin
    INTERVAL_S = 0.1              # refresh rate

    def __init__(self, message: str, stream: Optional[TextIO] = None):
        self.message = message
        self.stream: TextIO = stream if stream is not None else sys.stderr
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._tty = self.stream.isatty()
        self._start_time: float = 0.0
        # Track the longest line we've drawn so we can blank exactly
        # that many columns on exit — required because the elapsed
        # suffix grows over time ("(0s)" → "(127s)").
        self._max_line_len = 0

    def __enter__(self) -> "Spinner":
        self._start_time = time.monotonic()
        if self._tty:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        else:
            print(f"→ {self.message}", file=self.stream, flush=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        elapsed = time.monotonic() - self._start_time

        if self._thread is not None:
            self._stop.set()
            self._thread.join(timeout=1.0)
            # Blank the longest spinner line we drew, then return cursor
            # to column 0 so the final line prints cleanly.
            self.stream.write("\r" + " " * self._max_line_len + "\r")
            self.stream.flush()

        mark = "✓" if exc_type is None else "✗"
        suffix = f"({elapsed:.1f}s)"
        if exc_type is not None:
            suffix += " — error"
        print(f"{mark} {self.message} {suffix}", file=self.stream, flush=True)

    def _run(self) -> None:
        """Thread body: draw a new spinner frame every INTERVAL_S.

        Includes a live elapsed-seconds counter on the right so long
        LLM calls show progress instead of a stationary spinner.
        """
        frames = itertools.cycle(self.FRAMES)
        while not self._stop.is_set():
            frame = next(frames)
            elapsed = time.monotonic() - self._start_time
            line = f"{frame} {self.message} ({elapsed:.0f}s)"
            self._max_line_len = max(self._max_line_len, len(line))
            # \r returns the cursor to column 0 so we overwrite the
            # previous frame in place rather than scrolling.
            self.stream.write(f"\r{line}")
            self.stream.flush()
            self._stop.wait(self.INTERVAL_S)
