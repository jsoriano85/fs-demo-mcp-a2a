"""Ask an LLM which agent card should handle a terminal message."""

from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from fsdemo.auth import Settings
from fsdemo.events import FIELD_FORMATS, explicit_value
from fsdemo.routing import UnsupportedCommand

REPAIR_NAME = "Repair Agent"


class LlmNotConfigured(Exception):
    """The coordinator has no model credentials."""

    def __init__(self) -> None:
        super().__init__("Set LLM_API_KEY before asking the coordinator.")


class RouteDecision(BaseModel):
    name: str
    field: str | None = None


def parse_decision(content: str) -> RouteDecision:
    """Read the JSON object from a model reply."""
    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end < start:
        raise UnsupportedCommand()
    try:
        payload = json.loads(content[start : end + 1])
        decision = RouteDecision.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise UnsupportedCommand() from exc
    if decision.field is not None and decision.field not in FIELD_FORMATS:
        raise UnsupportedCommand()
    return decision


def delegation_text(decision: RouteDecision, message: str) -> str:
    """Use the user's words, except repair which must name one column."""
    if decision.name != REPAIR_NAME:
        return message
    if decision.field is None:
        raise UnsupportedCommand()
    value = explicit_value(message, decision.field)
    if value:
        return f"Repair {decision.field} data to {value}"
    expected = FIELD_FORMATS[decision.field]
    return f"Repair {decision.field} data to {expected}"


def _card_brief(card: dict[str, Any]) -> str:
    skills = card.get("skills") or []
    skill_bits: list[str] = []
    if isinstance(skills, list):
        for skill in skills:
            if not isinstance(skill, dict):
                continue
            name = skill.get("name", "")
            description = skill.get("description", "")
            skill_bits.append(f"{name}: {description}")
    skills_text = "; ".join(skill_bits) or "none"
    return (
        f"name: {card.get('name', '')}\n"
        f"description: {card.get('description', '')}\n"
        f"skills: {skills_text}"
    )


def route_prompt(cards: list[dict[str, Any]]) -> str:
    """Tell the model to pick one of the live agent cards."""
    listed = "\n\n".join(_card_brief(card) for card in cards)
    fields = ", ".join(FIELD_FORMATS)
    return (
        "Choose the agent card that should handle the user message. "
        "Reply with JSON only, shaped as "
        '{"name":"<agent card name>","field":null}. '
        f"Set field to one of {fields} only when the card is {REPAIR_NAME}. "
        "Otherwise field must be null.\n\n"
        f"Agent cards:\n{listed}"
    )


async def choose_agent(
    settings: Settings,
    cards: list[dict[str, Any]],
    message: str,
) -> RouteDecision:
    """Call the configured chat model and parse its agent-card choice."""
    if not settings.llm_api_key:
        raise LlmNotConfigured()
    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json={
                "model": settings.llm_model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": route_prompt(cards)},
                    {"role": "user", "content": message},
                ],
            },
        )
        response.raise_for_status()
    content = str(response.json()["choices"][0]["message"]["content"])
    decision = parse_decision(content)
    names = {str(card.get("name", "")) for card in cards}
    if decision.name not in names:
        raise UnsupportedCommand()
    if decision.name == REPAIR_NAME and decision.field is None:
        raise UnsupportedCommand()
    return decision
