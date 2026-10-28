"""Shared A2A JSON-RPC application setup."""

from __future__ import annotations

from a2a.helpers import new_task
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import a2a_pb2
from fastapi import FastAPI


def mount_jsonrpc(
    app: FastAPI,
    card: a2a_pb2.AgentCard,
    executor: AgentExecutor,
) -> None:
    """Expose the Agent Card and one JSON-RPC transport."""
    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(card),
        jsonrpc_routes=create_jsonrpc_routes(handler, rpc_url="/a2a/jsonrpc"),
    )


async def open_task(context: RequestContext, event_queue: EventQueue) -> TaskUpdater:
    """Publish the initial task, which later status events require."""
    task_id = context.task_id
    context_id = context.context_id
    if not task_id or not context_id:
        raise RuntimeError("A2A request is missing task_id or context_id")
    history = [context.message] if context.message is not None else []
    await event_queue.enqueue_event(
        new_task(
            task_id,
            context_id,
            a2a_pb2.TaskState.TASK_STATE_SUBMITTED,
            history=history,
        )
    )
    return TaskUpdater(
        event_queue=event_queue,
        task_id=task_id,
        context_id=context_id,
    )


def agent_interface(base_url: str) -> a2a_pb2.AgentInterface:
    return a2a_pb2.AgentInterface(
        protocol_binding="JSONRPC",
        protocol_version="1.0",
        url=f"{base_url.rstrip('/')}/a2a/jsonrpc",
    )
