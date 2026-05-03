"""
ui — terminal UI surface for the harness.

Two kinds of helpers live here, one file per primitive:

    Spinner          (spinner.py) — process-wide singleton spinner.
                     Every LLM call (via call_json or call_many)
                     registers a row automatically; callers don't
                     manage the lifecycle. Use `spinner.log(msg)`
                     to print informational lines that scroll above
                     the painted block instead of
                     `print(..., file=sys.stderr)`.

    Painters — full-screen interactive UIs that take over the
    alt-screen buffer for the duration of a user choice. They
    share a tiny private helper module (`_term.py`) for raw-mode
    keystroke reading and the alt-screen context manager.

      checklist      multi-select with toggleable rows (used by roles)
      single_select  pick exactly one option, optional type-custom row
      field_editor   three-mode review (review / pick / custom; stack)
      detail_list    items with toggleable details + action rows
                     (used by decompose)
      text_input     multi-line free-text input with ESC cancel
                     (used by decompose's revise-with-comment path)

Adding a new UI primitive:
    1. Create `ui/<name>.py` with a single function (or class).
    2. Import it + add it to __all__ below.
    3. Callers can `from ui import <name>`.
"""

from . import spinner
from .checklist import checklist
from .confirm_modal import confirm_modal
from .detail_list import detail_list
from .field_editor import field_editor
from .review_list import review_list
from .single_select import single_select
from .spinner import Spinner
from .text_input import text_input

__all__ = [
    "Spinner",
    "checklist",
    "confirm_modal",
    "detail_list",
    "field_editor",
    "review_list",
    "single_select",
    "spinner",
    "text_input",
]
