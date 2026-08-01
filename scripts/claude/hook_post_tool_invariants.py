#!/usr/bin/env python3
"""Claude Code entry point for shared PostToolUse invariant checks."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.hooks.post_tool_invariants import *  # noqa: F401,F403


if __name__ == "__main__":
    sys.exit(main())
