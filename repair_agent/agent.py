"""A2A agent that repairs event_date and does not diagnose the file."""

from __future__ import annotations

import logging

from a2a.types import a2a_pb2
from fastapi import FastAPI

from fsdemo.a2a_app import agent_interface, mount_jsonrpc
from fsdemo.auth import SCOPE_DELEGATE, BearerAuthMiddleware, Settings
from fsdemo.events import RepairResult, explicit_value
from fsdemo.mcp_client import open_mcp, parse_tool
from fsdemo.routing import repair_field_of
from fsdemo.runtime import bootstrap, serve
from fsdemo.specialist import SpecialistExecutor

logger = logging.getLogger("repair")


def repair_card(base_url: str) -> a2a_pb2.AgentCard:
    return a2a_pb2.AgentCard(
        name="Repair Agent",
        description="Repairs one event column into its required format.",
        version="1.0.0",
        capabilities=a2a_pb2.AgentCapabilities(
            streaming=True,
            push_notifications=False,
        ),
        default_input_modes=["text"],
        default_output_modes=["application/json"],
        skills=[
            a2a_pb2.AgentSkill(
                id="repair_event_dates",
                name="Repair event dates",
                description=(
                    "Rewrite event_date, event_name, pos, listings, or seats."
                ),
                tags=["events", "repair"],
                examples=[
                    "Repair event_date data to MM-dd-yyyy HH:mm.",
                    "Repair seats data to a non-negative integer.",
                ],
                input_modes=["text"],
                output_modes=["application/json"],
            )
        ],
        supported_interfaces=[agent_interface(base_url)],
    )


async def repair(settings: Settings, user_text: str) -> dict[str, object]:
    field = repair_field_of(user_text)
    if field is None:
        raise ValueError("name the field to repair")
    replacement = explicit_value(user_text, field)
    async with open_mcp(settings.mcp_url, settings.write_token) as client:
        logger.info("called repair_event_dates field=%s", field)
        result = parse_tool(
            await client.call_tool(
                "repair_event_dates",
                {"field": field, "replacement": replacement},
            ),
            RepairResult,
        )
    logger.info("rows_changed=%s", result.rows_changed)
    return result.model_dump()


def create_app(settings: Settings | None = None) -> FastAPI:
    current = settings or Settings.from_env()
    card = repair_card(current.repair_url)
    app = FastAPI(title=card.name)
    mount_jsonrpc(
        app,
        card,
        SpecialistExecutor(
            current,
            repair,
            logger,
            "Repairing event_date values.",
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
    serve(create_app(settings), settings.repair_host, settings.repair_port)


if __name__ == "__main__":
    main()
