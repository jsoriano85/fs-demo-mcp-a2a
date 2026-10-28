from pathlib import Path

import httpx
from mcp import Client
from mcp_server.server import build_server, create_app

from fsdemo.auth import SCOPE_READ, SCOPE_WRITE, Settings, active_scope
from fsdemo.events import corrupt_first_event_date, restore_events


def _settings(path: Path) -> Settings:
    return Settings(events_csv=str(path))


async def test_events_route_returns_rows_then_422(tmp_path: Path) -> None:
    path = tmp_path / "events.csv"
    restore_events(path)
    app = create_app(_settings(path))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        loaded = await client.get("/events")
        assert loaded.status_code == 200
        assert loaded.json()[0]["event_date"] == "10-21-2026 17:30"
        corrupt_first_event_date(path)
        failed = await client.get("/events")
    assert failed.status_code == 422
    issue = failed.json()["issues"][0]
    assert issue["field"] == "event_date"
    assert issue["value"] == "10/21/26 17:30"


async def test_mcp_requires_a_token(tmp_path: Path) -> None:
    path = tmp_path / "events.csv"
    restore_events(path)
    app = create_app(_settings(path))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        missing = await client.post("/mcp")
        wrong = await client.post("/mcp", headers={"Authorization": "Bearer nope"})
    assert missing.status_code == 401
    assert wrong.status_code == 401


async def test_tool_scope_rejects_the_wrong_token(tmp_path: Path) -> None:
    path = tmp_path / "events.csv"
    restore_events(path)
    server = build_server(_settings(path))
    read = active_scope.set(SCOPE_READ)
    try:
        async with Client(server) as client:
            denied = await client.call_tool(
                "repair_event_dates", {"field": "event_date"}
            )
    finally:
        active_scope.reset(read)
    assert denied.is_error

    write = active_scope.set(SCOPE_WRITE)
    try:
        async with Client(server) as client:
            allowed = await client.call_tool(
                "diagnose_events",
                {},
            )
            repaired = await client.call_tool(
                "repair_event_dates",
                {"field": "seats"},
            )
            unknown = await client.call_tool(
                "repair_event_dates",
                {"field": "venue"},
            )
    finally:
        active_scope.reset(write)
    assert allowed.is_error
    assert repaired.is_error is False
    assert unknown.is_error
