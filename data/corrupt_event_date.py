"""Change the first event_date to the invalid demo value."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fsdemo.events import CORRUPT_DATE, corrupt_first_event_date, default_csv_path


def main() -> None:
    path = default_csv_path()
    corrupt_first_event_date(path)
    print(f"Set row 1 event_date in {path} to {CORRUPT_DATE}")


if __name__ == "__main__":
    main()
