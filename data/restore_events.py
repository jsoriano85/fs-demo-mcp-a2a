"""Restore the canonical event CSV."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fsdemo.events import default_csv_path, restore_events


def main() -> None:
    path = default_csv_path()
    restore_events(path)
    print(f"Restored {path}")


if __name__ == "__main__":
    main()
