"""Send one user message to an A2A agent and collect its data artifact."""

from __future__ import annotations

from typing import Any

import httpx
from a2a.client import ClientCallContext, ClientConfig, ClientFactory
from a2a.helpers import get_data_parts, new_text_message
from a2a.types import a2a_pb2

TERMINAL_FAILURES = {
    a2a_pb2.TaskState.TASK_STATE_FAILED,
    a2a_pb2.TaskState.TASK_STATE_REJECTED,
    a2a_pb2.TaskState.TASK_STATE_CANCELED,
}


def state_name(state: int) -> str:
    name = str(a2a_pb2.TaskState.Name(state))
    return name.removeprefix("TASK_STATE_").lower()


def _payloads(event: a2a_pb2.StreamResponse) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if event.HasField("artifact_update"):
        found.extend(_dicts(event.artifact_update.artifact.parts))
    if event.HasField("task"):
        for artifact in event.task.artifacts:
            found.extend(_dicts(artifact.parts))
    return found


def _dicts(parts: Any) -> list[dict[str, Any]]:
    return [item for item in get_data_parts(parts) if isinstance(item, dict)]


def _failed(event: a2a_pb2.StreamResponse) -> bool:
    if event.HasField("status_update"):
        return event.status_update.status.state in TERMINAL_FAILURES
    if event.HasField("task"):
        return event.task.status.state in TERMINAL_FAILURES
    return False


async def send_user_text(
    base_url: str,
    text: str,
    token: str | None = None,
) -> dict[str, Any]:
    """Call an agent and return the last structured data artifact."""
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
    factory = ClientFactory(ClientConfig(streaming=True, httpx_client=http_client))
    client = await factory.create_from_url(base_url.rstrip("/"))
    request = a2a_pb2.SendMessageRequest(
        message=new_text_message(text, role=a2a_pb2.Role.ROLE_USER)
    )
    call_context = None
    if token is not None:
        call_context = ClientCallContext(
            service_parameters={"Authorization": f"Bearer {token}"}
        )
    found: dict[str, Any] | None = None
    states: list[str] = []
    try:
        async for event in client.send_message(request, context=call_context):
            if event.HasField("status_update"):
                states.append(state_name(event.status_update.status.state))
            if event.HasField("task") and event.task.HasField("status"):
                states.append(state_name(event.task.status.state))
            for payload in _payloads(event):
                found = payload
            if _failed(event):
                raise RuntimeError("agent task failed; states=" + ",".join(states))
    finally:
        await client.close()
        await http_client.aclose()
    if found is None:
        raise RuntimeError(
            "agent returned no data artifact; states=" + ",".join(states)
        )
    return found
