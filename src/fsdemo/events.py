"""CSV event storage, date validation, and event_date repair."""

from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from fsdemo.runtime import ROOT

COLUMNS = ["event_date", "event_name", "pos", "listings", "seats"]
REQUIRED_FORMAT = "MM-dd-yyyy HH:mm"
CONTRACT_FORMAT = "%m-%d-%Y %H:%M"
ACCEPTED_FORMATS = (CONTRACT_FORMAT, "%m/%d/%y %H:%M", "%m/%d/%Y %H:%M")
EVENT_NAME = "Cirque du Soleil - Drawn to Life"
POS = "TradeDesk|Stubhub"
KNOWN_POS = frozenset({"TradeDesk", "Stubhub"})
POS_CANONICAL = {name.lower(): name for name in KNOWN_POS}
CORRUPT_DATE = "10/21/26 17:30"
REPAIR_FIELD = "event_date"
FIELD_FORMATS = {
    "event_date": REQUIRED_FORMAT,
    "event_name": "non-empty name",
    "pos": "TradeDesk or Stubhub",
    "listings": "non-negative integer",
    "seats": "non-negative integer",
}

SHOWTIMES: tuple[tuple[str, int, int], ...] = (
    ("10-21-2026 17:30", 71, 535),
    ("10-21-2026 20:00", 69, 512),
    ("10-22-2026 17:30", 78, 630),
    ("10-22-2026 20:00", 71, 575),
    ("10-23-2026 17:30", 74, 542),
    ("10-23-2026 20:00", 78, 641),
    ("10-24-2026 17:30", 74, 501),
    ("10-24-2026 20:00", 66, 547),
    ("10-25-2026 13:30", 69, 593),
)


class EventRow(BaseModel):
    event_date: str
    event_name: str
    pos: str
    listings: int
    seats: int


class DataIssue(BaseModel):
    row: int
    field: str
    value: str
    expected_format: str


class DiagnosisReport(BaseModel):
    ok: bool
    issues: list[DataIssue] = Field(default_factory=list)


class RepairResult(BaseModel):
    field: str
    format: str
    rows_changed: int
    unparsed: list[DataIssue] = Field(default_factory=list)


class FetchReport(BaseModel):
    ok: bool
    rows: list[EventRow] = Field(default_factory=list)
    message: str = ""


class InvalidEvents(Exception):
    """The CSV failed the report contract."""

    def __init__(self, report: DiagnosisReport) -> None:
        self.report = report
        super().__init__("event report failed validation")


def default_csv_path() -> Path:
    return ROOT / "data" / "events.csv"


def canonical_rows() -> list[dict[str, str]]:
    return [
        {
            "event_date": when,
            "event_name": EVENT_NAME,
            "pos": POS,
            "listings": str(listings),
            "seats": str(seats),
        }
        for when, listings, seats in SHOWTIMES
    ]


def is_contract_date(value: str) -> bool:
    try:
        parsed = datetime.strptime(value, CONTRACT_FORMAT)
    except ValueError:
        return False
    return parsed.strftime(CONTRACT_FORMAT) == value


def parse_event_date(value: str) -> datetime | None:
    for fmt in ACCEPTED_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def read_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        rows = [{key: (value or "") for key, value in row.items()} for row in reader]
    return header, rows


def write_table(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def diagnose_file(path: Path) -> DiagnosisReport:
    """Report every cell that breaks the event-report contract."""
    if not path.is_file():
        return DiagnosisReport(
            ok=False,
            issues=[
                DataIssue(
                    row=0,
                    field="file",
                    value=str(path),
                    expected_format="CSV file",
                )
            ],
        )
    header, rows = read_table(path)
    issues: list[DataIssue] = []
    if header != COLUMNS:
        issues.append(
            DataIssue(
                row=0,
                field="header",
                value=",".join(header),
                expected_format=",".join(COLUMNS),
            )
        )
        return DiagnosisReport(ok=False, issues=issues)
    for index, row in enumerate(rows, start=1):
        issues.extend(_row_issues(index, row))
    return DiagnosisReport(ok=not issues, issues=issues)


def fetch_report(path: Path) -> FetchReport:
    """Return the report rows, or a generic failure when the file is invalid."""
    try:
        rows = load_events(path)
    except InvalidEvents:
        return FetchReport(ok=False, message="Cannot load the report")
    count = len(rows)
    noun = "event" if count == 1 else "events"
    return FetchReport(ok=True, rows=rows, message=f"Loaded {count} {noun}.")


def load_events(path: Path) -> list[EventRow]:
    report = diagnose_file(path)
    if not report.ok:
        raise InvalidEvents(report)
    _, rows = read_table(path)
    return [
        EventRow(
            event_date=row["event_date"],
            event_name=row["event_name"],
            pos=row["pos"],
            listings=int(row["listings"]),
            seats=int(row["seats"]),
        )
        for row in rows
    ]


def explicit_value(message: str, field: str) -> str:
    """Return a valid replacement named in a repair request."""
    if field != "event_date":
        return ""
    found = ""
    for match in re.finditer(
        r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\s+\d{1,2}:\d{2}",
        message,
    ):
        normalized = _normalize_date(match.group(0))
        if normalized is not None:
            found = normalized
    return found


def repair_dates(path: Path, field: str, replacement: str = "") -> RepairResult:
    """Rewrite one column into its contract form."""
    expected = FIELD_FORMATS.get(field)
    if expected is None:
        raise ValueError(f"unknown field {field}")
    explicit = _normalize(field, replacement) if replacement else None
    if replacement and explicit is None:
        raise ValueError(f"invalid replacement for {field}")
    header, rows = read_table(path)
    if header != COLUMNS:
        raise ValueError("unexpected CSV header")
    changed = 0
    unparsed: list[DataIssue] = []
    for index, row in enumerate(rows, start=1):
        raw = row.get(field, "")
        rewritten = _normalize(field, raw)
        if rewritten is None:
            if explicit is None:
                unparsed.append(
                    DataIssue(
                        row=index,
                        field=field,
                        value=raw,
                        expected_format=expected,
                    )
                )
                continue
            rewritten = explicit
        if rewritten != raw:
            row[field] = rewritten
            changed += 1
    write_table(path, rows)
    return RepairResult(
        field=field,
        format=expected,
        rows_changed=changed,
        unparsed=unparsed,
    )


def corrupt_first_event_date(path: Path) -> None:
    """Write the out-of-band bad date used in the live demo."""
    _header, rows = read_table(path)
    if not rows:
        raise ValueError("CSV has no event rows")
    rows[0][REPAIR_FIELD] = CORRUPT_DATE
    write_table(path, rows)


def restore_events(path: Path) -> None:
    write_table(path, canonical_rows())


def _row_issues(index: int, row: dict[str, str]) -> list[DataIssue]:
    issues: list[DataIssue] = []
    raw_date = row.get(REPAIR_FIELD, "")
    if not is_contract_date(raw_date):
        issues.append(
            DataIssue(
                row=index,
                field=REPAIR_FIELD,
                value=raw_date,
                expected_format=REQUIRED_FORMAT,
            )
        )
    for field in ("listings", "seats"):
        raw_number = row.get(field, "")
        if not raw_number.isdigit():
            issues.append(
                DataIssue(
                    row=index,
                    field=field,
                    value=raw_number,
                    expected_format=FIELD_FORMATS[field],
                )
            )
    parts = [part for part in row.get("pos", "").split("|") if part]
    if not parts or any(part not in KNOWN_POS for part in parts):
        issues.append(
            DataIssue(
                row=index,
                field="pos",
                value=row.get("pos", ""),
                expected_format=FIELD_FORMATS["pos"],
            )
        )
    if not row.get("event_name", "").strip():
        issues.append(
            DataIssue(
                row=index,
                field="event_name",
                value=row.get("event_name", ""),
                expected_format=FIELD_FORMATS["event_name"],
            )
        )
    return issues


def _normalize(field: str, raw: str) -> str | None:
    if field == "event_date":
        return _normalize_date(raw)
    if field == "event_name":
        return _normalize_name(raw)
    if field == "pos":
        return _normalize_pos(raw)
    if field in {"listings", "seats"}:
        return _normalize_number(raw)
    return None


def _normalize_date(raw: str) -> str | None:
    if is_contract_date(raw):
        return raw
    parsed = parse_event_date(raw)
    if parsed is None:
        return None
    return parsed.strftime(CONTRACT_FORMAT)


def _normalize_name(raw: str) -> str | None:
    stripped = raw.strip()
    if not stripped:
        return None
    return stripped


def _normalize_pos(raw: str) -> str | None:
    parts = [part.strip() for part in raw.split("|") if part.strip()]
    if not parts:
        return None
    canonical: list[str] = []
    for part in parts:
        mapped = POS_CANONICAL.get(part.lower())
        if mapped is None:
            return None
        canonical.append(mapped)
    return "|".join(canonical)


def _normalize_number(raw: str) -> str | None:
    text = raw.strip()
    if text.isdigit():
        return text
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return None
