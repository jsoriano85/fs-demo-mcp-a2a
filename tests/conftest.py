import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT):
    entry = str(path)
    if entry not in sys.path:
        sys.path.insert(0, entry)
