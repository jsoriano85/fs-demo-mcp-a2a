"""Column names the repair agent accepts."""

from __future__ import annotations

REPAIR_FIELDS = ("event_date", "event_name", "listings", "seats", "pos")


class UnsupportedCommand(Exception):
    """The coordinator does not have a specialist for this message."""

    def __init__(self) -> None:
        super().__init__(
            "Send 'Investigate the failed report' or "
            "'Repair <field> data to <format>'."
        )


def repair_field_of(message: str) -> str | None:
    """Return the column named in a repair command."""
    text = " ".join(message.lower().split())
    for field in REPAIR_FIELDS:
        if field in text:
            return field
    return None
