from pathlib import Path

import pytest

from fsdemo.events import (
    CORRUPT_DATE,
    REQUIRED_FORMAT,
    canonical_rows,
    corrupt_first_event_date,
    default_csv_path,
    diagnose_file,
    fetch_report,
    read_table,
    repair_dates,
    restore_events,
    write_table,
)


def test_committed_csv_matches_the_contract() -> None:
    header, rows = read_table(default_csv_path())
    assert header == ["event_date", "event_name", "pos", "listings", "seats"]
    assert rows == canonical_rows()
    assert diagnose_file(default_csv_path()).ok


def test_fetch_hides_the_reason_until_diagnosis(tmp_path: Path) -> None:
    path = tmp_path / "events.csv"
    restore_events(path)
    loaded = fetch_report(path)
    assert loaded.ok is True
    assert len(loaded.rows) == 9

    corrupt_first_event_date(path)
    failed = fetch_report(path)
    assert failed.ok is False
    assert failed.message == "Cannot load the report"
    assert failed.rows == []


def test_corrupt_date_is_diagnosed(tmp_path: Path) -> None:
    path = tmp_path / "events.csv"
    restore_events(path)
    corrupt_first_event_date(path)

    report = diagnose_file(path)

    assert report.ok is False
    assert report.issues[0].row == 1
    assert report.issues[0].field == "event_date"
    assert report.issues[0].value == CORRUPT_DATE
    assert report.issues[0].expected_format == REQUIRED_FORMAT


def test_repair_is_idempotent_and_accepts_each_column(tmp_path: Path) -> None:
    path = tmp_path / "events.csv"
    restore_events(path)
    corrupt_first_event_date(path)
    rows = read_table(path)[1]
    rows[1]["event_name"] = "  Cirque  "
    rows[1]["pos"] = "tradedesk|stubhub"
    rows[1]["listings"] = "69.0"
    rows[1]["seats"] = " none "
    write_table(path, rows)

    first = repair_dates(path, "event_date")
    second = repair_dates(path, "event_date")
    name = repair_dates(path, "event_name")
    pos = repair_dates(path, "pos")
    listings = repair_dates(path, "listings")
    seats = repair_dates(path, "seats")

    repaired = read_table(path)[1]
    assert first.rows_changed == 1
    assert second.rows_changed == 0
    assert repaired[0]["event_date"] == "10-21-2026 17:30"
    assert name.rows_changed == 1
    assert repaired[1]["event_name"] == "Cirque"
    assert pos.rows_changed == 1
    assert repaired[1]["pos"] == "TradeDesk|Stubhub"
    assert listings.rows_changed == 1
    assert repaired[1]["listings"] == "69"
    assert seats.rows_changed == 0
    assert seats.unparsed[0].field == "seats"
    with pytest.raises(ValueError, match="unknown field"):
        repair_dates(path, "venue")


def test_unparseable_date_is_left_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "events.csv"
    rows = canonical_rows()
    rows[2]["event_date"] = "not-a-date"
    write_table(path, rows)

    result = repair_dates(path, "event_date")

    assert result.rows_changed == 0
    assert result.unparsed[0].row == 3
    assert read_table(path)[1][2]["event_date"] == "not-a-date"


def test_named_date_replaces_an_impossible_value(tmp_path: Path) -> None:
    path = tmp_path / "events.csv"
    rows = canonical_rows()
    rows[8]["event_date"] = "13-25-2026 13:30"
    write_table(path, rows)

    result = repair_dates(path, "event_date", "10-25-2026 13:30")

    repaired = read_table(path)[1]
    assert result.rows_changed == 1
    assert result.unparsed == []
    assert repaired[8]["event_date"] == "10-25-2026 13:30"
    assert repaired[0]["event_date"] == "10-21-2026 17:30"
