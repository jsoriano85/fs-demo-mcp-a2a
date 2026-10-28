"""Shared A2A executor for a specialist that calls one MCP tool."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable

from a2a.helpers import new_data_part, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks.task_updater import TaskUpdater

from fsdemo.a2a_app import open_task
from fsdemo.auth import Settings

Work = Callable[[Settings, str], Awaitable[dict[str, object]]]


class SpecialistExecutor(AgentExecutor):
    """Run one specialist task and return its JSON artifact."""

    def __init__(
        self,
        settings: Settings,
        work: Work,
        logger: logging.Logger,
        working_text: str,
    ) -> None:
        self._settings = settings
        self._work = work
        self._logger = logger
        self._working_text = working_text
        self._running: set[str] = set()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id = context.task_id or ""
        self._running.discard(task_id)
        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=task_id,
            context_id=context.context_id or "",
        )
        await updater.cancel()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id = context.task_id or ""
        self._running.add(task_id)
        updater = await open_task(context, event_queue)
        try:
            await updater.start_work(
                message=updater.new_agent_message(
                    parts=[new_text_part(self._working_text)]
                )
            )
            payload = await self._work(self._settings, context.get_user_input())
            await updater.add_artifact(
                parts=[
                    new_data_part(payload),
                    new_text_part(json.dumps(payload)),
                ],
                name="result",
                last_chunk=True,
            )
            await updater.complete()
            self._logger.info("completed")
        except Exception:
            self._logger.exception("specialist failed")
            await updater.failed(
                message=updater.new_agent_message(
                    parts=[new_text_part("The specialist failed before a result.")]
                )
            )
        finally:
            self._running.discard(task_id)
