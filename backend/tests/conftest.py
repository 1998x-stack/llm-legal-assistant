from pathlib import Path
import sys

# Allow running pytest from repository root without an editable install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
