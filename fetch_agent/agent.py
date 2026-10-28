"""A2A agent that loads the event report and does not change it."""

from __future__ import annotations

import logging

from a2a.types import a2a_pb2
from fastapi import FastAPI

from fsdemo.a2a_app import agent_interface, mount_jsonrpc
from fsdemo.auth import SCOPE_DELEGATE, BearerAuthMiddleware, Settings
from fsdemo.events import FetchReport
from fsdemo.mcp_client import open_mcp, parse_tool
from fsdemo.runtime import bootstrap, serve
from fsdemo.specialist import SpecialistExecutor

logger = logging.getLogger("fetch")


def fetch_card(base_url: str) -> a2a_pb2.AgentCard:
    return a2a_pb2.AgentCard(
        name="Fetch Agent",
        description="Loads or refreshes the event report from the CSV.",
        version="1.0.0",
        capabilities=a2a_pb2.AgentCapabilities(
            streaming=True,
            push_notifications=False,
        ),
        default_input_modes=["text"],
        default_output_modes=["application/json"],
        skills=[
            a2a_pb2.AgentSkill(
                id="fetch_events",
                name="Fetch events",
                description="Read the current event report through MCP.",
                tags=["events", "fetch"],
                examples=[
                    "Load the report.",
                    "Refresh the report.",
                ],
                input_modes=["text"],
                output_modes=["application/json"],
            )
        ],
        supported_interfaces=[agent_interface(base_url)],
    )


async def fetch(settings: Settings, _user_text: str) -> dict[str, object]:
    async with open_mcp(settings.mcp_url, settings.read_token) as client:
        logger.info("called fetch_events")
        report = parse_tool(await client.call_tool("fetch_events", {}), FetchReport)
    logger.info("ok=%s rows=%s", report.ok, len(report.rows))
    return report.model_dump()


def create_app(settings: Settings | None = None) -> FastAPI:
    current = settings or Settings.from_env()
    card = fetch_card(current.fetch_url)
    app = FastAPI(title=card.name)
    mount_jsonrpc(
        app,
        card,
        SpecialistExecutor(
            current,
            fetch,
            logger,
            "Loading the event report.",
        ),
    )
    app.add_middleware(
        BearerAuthMiddleware,
        expected_token=current.delegate_token,
        scope_name=SCOPE_DELEGATE,
        protected_prefix="/a2a",
    )
    return app


def main() -> None:
    settings = bootstrap()
    serve(create_app(settings), settings.fetch_host, settings.fetch_port)


if __name__ == "__main__":
    main()
