"""Coordinator HTTP chat API and A2A delegation."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from a2a.types import a2a_pb2
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from fsdemo.a2a_app import agent_interface, mount_jsonrpc
from fsdemo.a2a_messages import send_user_text
from fsdemo.auth import Settings
from fsdemo.llm_route import (
    LlmNotConfigured,
    choose_agent,
    delegation_text,
)
from fsdemo.routing import UnsupportedCommand
from fsdemo.runtime import bootstrap, serve
from fsdemo.specialist import SpecialistExecutor

logger = logging.getLogger("coordinator")
UI_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    specialist: str
    artifact: dict[str, Any]


def coordinator_card(base_url: str) -> a2a_pb2.AgentCard:
    return a2a_pb2.AgentCard(
        name="Coordinator Agent",
        description=(
            "Uses a model to choose the fetch, diagnosis, or repair agent card."
        ),
        version="1.0.0",
        capabilities=a2a_pb2.AgentCapabilities(
            streaming=True,
            push_notifications=False,
        ),
        default_input_modes=["text"],
        default_output_modes=["application/json"],
        skills=[
            a2a_pb2.AgentSkill(
                id="coordinate_event_report",
                name="Coordinate event report",
                description="Delegate fetch, diagnosis, or column repair.",
                tags=["coordination"],
                examples=[
                    "Load the report.",
                    "Refresh the report.",
                    "Why did the report fail?",
                    "Fix the event dates.",
                ],
                input_modes=["text"],
                output_modes=["application/json"],
            )
        ],
        supported_interfaces=[agent_interface(base_url)],
    )


async def _read_card(http: httpx.AsyncClient, url: str) -> tuple[str, dict[str, Any]]:
    response = await http.get(f"{url.rstrip('/')}/.well-known/agent-card.json")
    response.raise_for_status()
    card = response.json()
    if not isinstance(card, dict):
        raise UnsupportedCommand()
    return url, card


async def delegate(settings: Settings, message: str) -> ChatResponse:
    urls = (settings.fetch_url, settings.diagnosis_url, settings.repair_url)
    async with httpx.AsyncClient(timeout=5.0) as http:
        loaded = await asyncio.gather(*(_read_card(http, url) for url in urls))
    cards = [card for _url, card in loaded]
    decision = await choose_agent(settings, cards, message)
    match = next(
        (item for item in loaded if item[1].get("name") == decision.name),
        None,
    )
    if match is None:
        raise UnsupportedCommand()
    base, card = match
    specialist = str(card.get("name", decision.name))
    logger.info("selected %s at %s", specialist, base)
    artifact = await send_user_text(
        base.rstrip("/"),
        delegation_text(decision, message),
        token=settings.delegate_token,
    )
    logger.info("completed via %s", specialist)
    return ChatResponse(specialist=specialist, artifact=artifact)


def create_app(settings: Settings | None = None) -> FastAPI:
    current = settings or Settings.from_env()
    card = coordinator_card(current.coordinator_url)
    app = FastAPI(title=card.name)

    @app.post("/chat")
    async def chat(body: ChatRequest) -> JSONResponse:
        try:
            result = await delegate(current, body.message)
        except LlmNotConfigured as exc:
            return JSONResponse({"error": str(exc)}, status_code=503)
        except UnsupportedCommand as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse(result.model_dump())

    mount_jsonrpc(
        app,
        card,
        SpecialistExecutor(
            current,
            coordinate,
            logger,
            "Delegating the event-report request.",
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=UI_ORIGINS,
        allow_methods=["POST", "GET", "OPTIONS"],
        allow_headers=["*"],
    )
    return app


async def coordinate(settings: Settings, user_text: str) -> dict[str, object]:
    result = await delegate(settings, user_text)
    return result.model_dump()


def main() -> None:
    settings = bootstrap()
    serve(create_app(settings), settings.coordinator_host, settings.coordinator_port)


if __name__ == "__main__":
    main()
