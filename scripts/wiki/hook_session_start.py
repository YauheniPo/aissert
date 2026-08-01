#!/usr/bin/env python3
"""Claude Code entry point for the shared wiki SessionStart hook."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.hooks.session_start import main


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # The shared hook intentionally fails open; keep a minimal fallback for
        # a broken local Python environment.
        print('{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"[LLM Wiki] Read knowledge/index.md then knowledge/status.md before working."}}')
