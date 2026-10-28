import json
import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest

from fsdemo.events import corrupt_first_event_date, restore_events
from fsdemo.runtime import ROOT


def _port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait(url: str, status: int) -> None:
    deadline = time.monotonic() + 20
    last = ""
    while time.monotonic() < deadline:
        try:
            response = httpx.post(url, timeout=1.0)
            if response.status_code == status:
                return
            last = str(response.status_code)
        except httpx.HTTPError as exc:
            last = str(exc)
        time.sleep(0.2)
    raise AssertionError(f"{url} did not return {status}: {last}")


class _ModelHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length))
        messages = body["messages"]
        user = str(messages[-1]["content"]).lower()
        if "repair" in user or "fix" in user or "event_date" in user:
            decision = {"name": "Repair Agent", "field": "event_date"}
        elif "investigate" in user or "diagnos" in user or "why" in user:
            decision = {"name": "Diagnosis Agent", "field": None}
        else:
            decision = {"name": "Fetch Agent", "field": None}
        payload = json.dumps(
            {"choices": [{"message": {"content": json.dumps(decision)}}]}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture
def processes(tmp_path: Path) -> Iterator[dict[str, str]]:
    csv_path = tmp_path / "events.csv"
    restore_events(csv_path)
    llm_port = _port()
    model = ThreadingHTTPServer(("127.0.0.1", llm_port), _ModelHandler)
    thread = threading.Thread(target=model.serve_forever, daemon=True)
    thread.start()
    mcp_port, coordinator_port, diagnosis_port, repair_port, fetch_port = (
        _port(),
        _port(),
        _port(),
        _port(),
        _port(),
    )
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": os.pathsep.join(
                [str(ROOT / "src"), str(ROOT), env.get("PYTHONPATH", "")]
            ),
            "EVENTS_CSV": str(csv_path),
            "MCP_PORT": str(mcp_port),
            "COORDINATOR_PORT": str(coordinator_port),
            "DIAGNOSIS_PORT": str(diagnosis_port),
            "REPAIR_PORT": str(repair_port),
            "FETCH_PORT": str(fetch_port),
            "MCP_URL": f"http://127.0.0.1:{mcp_port}/mcp",
            "COORDINATOR_URL": f"http://127.0.0.1:{coordinator_port}",
            "DIAGNOSIS_URL": f"http://127.0.0.1:{diagnosis_port}",
            "REPAIR_URL": f"http://127.0.0.1:{repair_port}",
            "FETCH_URL": f"http://127.0.0.1:{fetch_port}",
            "MCP_READ_TOKEN": "demo-events-read-token",
            "MCP_WRITE_TOKEN": "demo-events-write-token",
            "AGENT_DELEGATE_TOKEN": "demo-delegate-token",
            "LLM_BASE_URL": f"http://127.0.0.1:{llm_port}/v1",
            "LLM_API_KEY": "test-key",
            "LLM_MODEL": "test-model",
        }
    )
    modules = (
        "mcp_server",
        "coordinator_agent",
        "diagnosis_agent",
        "repair_agent",
        "fetch_agent",
    )
    running = [
        subprocess.Popen(
            [sys.executable, "-m", module],
            env=env,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        for module in modules
    ]
    urls = {
        "events": f"http://127.0.0.1:{mcp_port}/events",
        "chat": f"http://127.0.0.1:{coordinator_port}/chat",
        "mcp": f"http://127.0.0.1:{mcp_port}/mcp",
        "diagnosis": f"http://127.0.0.1:{diagnosis_port}/a2a/jsonrpc",
    }
    try:
        _wait(urls["mcp"], 401)
        _wait(urls["diagnosis"], 401)
        yield urls | {"csv": str(csv_path)}
    finally:
        model.shutdown()
        thread.join(timeout=5)
        for process in running:
            process.kill()
            process.wait(timeout=10)


def test_coordinator_routes_diagnosis_and_repair(processes: dict[str, str]) -> None:
    csv_path = Path(processes["csv"])
    loaded = httpx.post(
        processes["chat"],
        json={"message": "Load the report"},
        timeout=30,
    )
    assert loaded.status_code == 200
    assert loaded.json()["specialist"] == "Fetch Agent"
    assert loaded.json()["artifact"]["ok"] is True
    assert len(loaded.json()["artifact"]["rows"]) == 9

    corrupt_first_event_date(csv_path)
    refreshed = httpx.post(
        processes["chat"],
        json={"message": "Refresh the report"},
        timeout=30,
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["artifact"]["message"] == "Cannot load the report"
    failed = httpx.get(processes["events"], timeout=5)
    assert failed.status_code == 422

    diagnosis = httpx.post(
        processes["chat"],
        json={"message": "Investigate the failed report"},
        timeout=20,
    )
    assert diagnosis.status_code == 200
    body = diagnosis.json()
    assert body["specialist"] == "Diagnosis Agent"
    assert body["artifact"]["issues"][0]["value"] == "10/21/26 17:30"

    repair = httpx.post(
        processes["chat"],
        json={"message": "Repair event_date data to MM-dd-yyyy HH:mm"},
        timeout=20,
    )
    assert repair.status_code == 200
    assert repair.json()["specialist"] == "Repair Agent"
    assert repair.json()["artifact"]["rows_changed"] == 1

    restored = httpx.get(processes["events"], timeout=5)
    assert restored.status_code == 200
    assert restored.json()[0]["event_date"] == "10-21-2026 17:30"

    denied = httpx.post(
        processes["diagnosis"],
        headers={"Authorization": "Bearer demo-events-read-token"},
        timeout=5,
    )
    assert denied.status_code == 401
