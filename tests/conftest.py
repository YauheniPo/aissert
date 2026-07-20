import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills" / "aissert" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
