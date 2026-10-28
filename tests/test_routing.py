import pytest

from fsdemo.events import explicit_value
from fsdemo.llm_route import RouteDecision, delegation_text, parse_decision
from fsdemo.routing import UnsupportedCommand, repair_field_of


def test_model_json_selects_a_card() -> None:
    decision = parse_decision('Sure. {"name": "Fetch Agent", "field": null}')
    assert decision == RouteDecision(name="Fetch Agent", field=None)


def test_model_json_can_name_a_repair_column() -> None:
    decision = parse_decision('{"name":"Repair Agent","field":"seats"}')
    assert decision.field == "seats"
    assert repair_field_of("Repair seats data to a non-negative integer") == "seats"


def test_a_requested_date_is_forwarded_to_repair() -> None:
    message = "can you repair the event_date value to 10-25-2026 13:30?"
    decision = RouteDecision(name="Repair Agent", field="event_date")
    forwarded = delegation_text(decision, message)
    assert explicit_value(forwarded, "event_date") == "10-25-2026 13:30"
    assert explicit_value(message, "event_date") == "10-25-2026 13:30"


def test_model_json_rejects_an_unknown_column() -> None:
    with pytest.raises(UnsupportedCommand):
        parse_decision('{"name":"Repair Agent","field":"venue"}')
