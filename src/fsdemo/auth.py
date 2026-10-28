"""Bearer-token checks for the two demo scopes.

Production would replace these shared tokens with OAuth or mutual TLS.
Tokens are compared in constant time and never written to logs.
"""

from __future__ import annotations

import hmac
import os
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ASGIApp = Callable[[dict[str, Any], Any, Any], Awaitable[None]]

SCOPE_DELEGATE = "agent:delegate"
SCOPE_READ = "tools:events:read"
SCOPE_WRITE = "tools:events:write"

DEFAULT_DELEGATE_TOKEN = "demo-delegate-token"
DEFAULT_READ_TOKEN = "demo-events-read-token"
DEFAULT_WRITE_TOKEN = "demo-events-write-token"

active_scope: ContextVar[str | None] = ContextVar("active_scope", default=None)


class Unauthorized(Exception):
    """Raised when a bearer token is missing or does not match the scope."""

    def __init__(self, scope: str) -> None:
        self.scope = scope
        super().__init__(f"unauthorized for scope {scope}")


@dataclass(frozen=True)
class Settings:
    """Process configuration. Loaded from the environment at startup."""

    events_csv: str = ""
    mcp_url: str = "http://127.0.0.1:8000/mcp"
    coordinator_url: str = "http://127.0.0.1:8001"
    diagnosis_url: str = "http://127.0.0.1:8002"
    repair_url: str = "http://127.0.0.1:8003"
    fetch_url: str = "http://127.0.0.1:8004"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    delegate_token: str = DEFAULT_DELEGATE_TOKEN
    read_token: str = DEFAULT_READ_TOKEN
    write_token: str = DEFAULT_WRITE_TOKEN
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8000
    coordinator_host: str = "127.0.0.1"
    coordinator_port: int = 8001
    diagnosis_host: str = "127.0.0.1"
    diagnosis_port: int = 8002
    repair_host: str = "127.0.0.1"
    repair_port: int = 8003
    fetch_host: str = "127.0.0.1"
    fetch_port: int = 8004

    @classmethod
    def from_env(cls) -> Settings:
        default_csv = str(Path(__file__).resolve().parents[2] / "data" / "events.csv")
        return cls(
            events_csv=os.environ.get("EVENTS_CSV", default_csv),
            mcp_url=os.environ.get("MCP_URL", cls.mcp_url),
            coordinator_url=os.environ.get("COORDINATOR_URL", cls.coordinator_url),
            diagnosis_url=os.environ.get("DIAGNOSIS_URL", cls.diagnosis_url),
            repair_url=os.environ.get("REPAIR_URL", cls.repair_url),
            fetch_url=os.environ.get("FETCH_URL", cls.fetch_url),
            llm_base_url=os.environ.get("LLM_BASE_URL", cls.llm_base_url),
            llm_model=os.environ.get("LLM_MODEL", cls.llm_model),
            llm_api_key=os.environ.get("LLM_API_KEY", ""),
            delegate_token=os.environ.get(
                "AGENT_DELEGATE_TOKEN", DEFAULT_DELEGATE_TOKEN
            ),
            read_token=os.environ.get("MCP_READ_TOKEN", DEFAULT_READ_TOKEN),
            write_token=os.environ.get("MCP_WRITE_TOKEN", DEFAULT_WRITE_TOKEN),
            mcp_host=os.environ.get("MCP_HOST", cls.mcp_host),
            mcp_port=int(os.environ.get("MCP_PORT", str(cls.mcp_port))),
            coordinator_host=os.environ.get("COORDINATOR_HOST", cls.coordinator_host),
            coordinator_port=int(
                os.environ.get("COORDINATOR_PORT", str(cls.coordinator_port))
            ),
            diagnosis_host=os.environ.get("DIAGNOSIS_HOST", cls.diagnosis_host),
            diagnosis_port=int(
                os.environ.get("DIAGNOSIS_PORT", str(cls.diagnosis_port))
            ),
            repair_host=os.environ.get("REPAIR_HOST", cls.repair_host),
            repair_port=int(os.environ.get("REPAIR_PORT", str(cls.repair_port))),
            fetch_host=os.environ.get("FETCH_HOST", cls.fetch_host),
            fetch_port=int(os.environ.get("FETCH_PORT", str(cls.fetch_port))),
        )


def bearer_token(authorization: str | None) -> str:
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise Unauthorized("bearer")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise Unauthorized("bearer")
    return token


def require_token(authorization: str | None, expected: str, scope: str) -> None:
    """Reject a missing or mismatched bearer token before any work runs."""
    try:
        presented = bearer_token(authorization)
    except Unauthorized as exc:
        raise Unauthorized(scope) from exc
    if not hmac.compare_digest(presented, expected):
        raise Unauthorized(scope)


class BearerAuthMiddleware:
    """Reject HTTP requests that lack the expected bearer token.

    ``protected_prefix`` limits the check to one path family so a public
    Agent Card can sit beside a protected A2A endpoint.
    """

    def __init__(
        self,
        app: ASGIApp,
        expected_token: str,
        scope_name: str,
        protected_prefix: str = "",
    ) -> None:
        self.app = app
        self.expected_token = expected_token
        self.scope_name = scope_name
        self.protected_prefix = protected_prefix

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path", ""))
        if self.protected_prefix and not path.startswith(self.protected_prefix):
            await self.app(scope, receive, send)
            return
        raw_headers = scope.get("headers", [])
        headers = {
            key.decode("latin1").lower(): value.decode("latin1")
            for key, value in raw_headers
        }
        try:
            require_token(
                headers.get("authorization"),
                self.expected_token,
                self.scope_name,
            )
        except Unauthorized:
            body = b'{"error":"unauthorized"}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode("ascii")),
                        (
                            b"www-authenticate",
                            f'Bearer scope="{self.scope_name}"'.encode("ascii"),
                        ),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)


class ScopedBearerMiddleware:
    """Accept one of several bearer tokens and record its scope for the request."""

    def __init__(
        self,
        app: ASGIApp,
        tokens: dict[str, str],
        protected_prefix: str = "",
    ) -> None:
        self.app = app
        self.tokens = tokens
        self.protected_prefix = protected_prefix

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path", ""))
        if self.protected_prefix and not path.startswith(self.protected_prefix):
            await self.app(scope, receive, send)
            return
        raw_headers = scope.get("headers", [])
        headers = {
            key.decode("latin1").lower(): value.decode("latin1")
            for key, value in raw_headers
        }
        try:
            presented = bearer_token(headers.get("authorization"))
        except Unauthorized:
            await _send_unauthorized(send, "bearer")
            return
        matched = next(
            (
                scope_name
                for token, scope_name in self.tokens.items()
                if hmac.compare_digest(presented, token)
            ),
            None,
        )
        if matched is None:
            await _send_unauthorized(send, "bearer")
            return
        reset = active_scope.set(matched)
        try:
            await self.app(scope, receive, send)
        finally:
            active_scope.reset(reset)


def require_active_scope(expected: str) -> None:
    """Reject a tool call whose request token has a different scope."""
    if active_scope.get() != expected:
        raise Unauthorized(expected)


async def _send_unauthorized(send: Any, scope_name: str) -> None:
    body = b'{"error":"unauthorized"}'
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (
                    b"www-authenticate",
                    f'Bearer scope="{scope_name}"'.encode("ascii"),
                ),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
