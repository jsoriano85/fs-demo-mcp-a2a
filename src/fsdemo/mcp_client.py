"""MCP client used by the diagnosis agent."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from mcp.types import CallToolResult
from pydantic import BaseModel


def payload_of(result: CallToolResult) -> object:
    """Return structured tool output, unwrapping a single result envelope."""
    if result.is_error:
        text = " ".join(getattr(block, "text", "") for block in result.content).strip()
        raise RuntimeError(text or "MCP tool call failed")
    payload = result.structured_content
    if isinstance(payload, dict) and set(payload) == {"result"}:
        return payload["result"]
    return payload


def parse_tool[ModelT: BaseModel](
    result: CallToolResult,
    model: type[ModelT],
) -> ModelT:
    return model.model_validate(payload_of(result))


@asynccontextmanager
async def open_mcp(url: str, token: str) -> AsyncIterator[Client]:
    """Connect to the event MCP server with one bearer token."""
    http_client = create_mcp_http_client(headers={"Authorization": f"Bearer {token}"})
    transport = streamable_http_client(url, http_client=http_client)
    try:
        async with Client(transport) as client:
            yield client
    finally:
        await http_client.aclose()
