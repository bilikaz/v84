"""
menu.setup_llm — Setup LLM sub-menu.

v1: stub. Surfaces the existing CLI tier-set helpers so users can
re-probe or change endpoints without restarting with --llm-set
flags. To be fleshed out next.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def setup_llm(project_dir: Path, cfg: Any, args: Any) -> int:
    """Sub-menu placeholder. Returns 0 to come back to the main menu."""
    print(
        "\n  ⚠ Setup LLM sub-menu not yet implemented.\n"
        "    For now use the CLI flags:\n"
        "      python3 v84.py --llm-set [URL]        # single tier\n"
        "      python3 v84.py --llm-set-multi [URL]  # multi tier\n"
        "      python3 v84.py --reset-llm            # clear cached URL\n",
        file=sys.stderr,
    )
    input("  press Enter to return to the menu...")
    return 0
