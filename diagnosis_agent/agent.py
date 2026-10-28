"""A2A agent that diagnoses the event CSV and does not change it."""

from __future__ import annotations

import logging

from a2a.types import a2a_pb2
from fastapi import FastAPI

from fsdemo.a2a_app import agent_interface, mount_jsonrpc
from fsdemo.auth import SCOPE_DELEGATE, BearerAuthMiddleware, Settings
from fsdemo.events import DiagnosisReport
from fsdemo.mcp_client import open_mcp, parse_tool
from fsdemo.runtime import bootstrap, serve
from fsdemo.specialist import SpecialistExecutor

logger = logging.getLogger("diagnosis")


def diagnosis_card(base_url: str) -> a2a_pb2.AgentCard:
    return a2a_pb2.AgentCard(
        name="Diagnosis Agent",
        description="Diagnoses invalid cells in the event CSV.",
        version="1.0.0",
        capabilities=a2a_pb2.AgentCapabilities(
            streaming=True,
            push_notifications=False,
        ),
        default_input_modes=["text"],
        default_output_modes=["application/json"],
        skills=[
            a2a_pb2.AgentSkill(
                id="diagnose_events",
                name="Diagnose events",
                description="Run a data check on the event CSV.",
                tags=["events", "diagnosis"],
                examples=["Investigate the failed report."],
                input_modes=["text"],
                output_modes=["application/json"],
            )
        ],
        supported_interfaces=[agent_interface(base_url)],
    )


async def diagnose(settings: Settings, _user_text: str) -> dict[str, object]:
    async with open_mcp(settings.mcp_url, settings.read_token) as client:
        listed = await client.list_tools()
        names = ", ".join(tool.name for tool in listed.tools)
        logger.info("listed tools: %s", names)
        logger.info("called diagnose_events")
        report = parse_tool(
            await client.call_tool("diagnose_events", {}),
            DiagnosisReport,
        )
    return report.model_dump()


def create_app(settings: Settings | None = None) -> FastAPI:
    current = settings or Settings.from_env()
    card = diagnosis_card(current.diagnosis_url)
    app = FastAPI(title=card.name)
    mount_jsonrpc(
        app,
        card,
        SpecialistExecutor(
            current,
            diagnose,
            logger,
            "Checking the event CSV.",
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
    serve(create_app(settings), settings.diagnosis_host, settings.diagnosis_port)


if __name__ == "__main__":
    main()
