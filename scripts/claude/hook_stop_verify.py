#!/usr/bin/env python3
"""Claude Code entry point for shared Stop verification."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.hooks.stop_verify import *  # noqa: F401,F403


if __name__ == "__main__":
    sys.exit(main())
