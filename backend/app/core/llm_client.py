"""LLM client wrapper — OpenAI-compatible function calling for protocol agents."""

from __future__ import annotations
import json
import logging
from openai import OpenAI
from .config import settings

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            max_retries=0,
        )
    return _client


def call_with_tools(
    system_prompt: str,
    user_message: str,
    tools: list[dict],
    max_iterations: int = 1,
    model: str | None = None,
) -> list[dict]:
    """Call LLM with function calling tools in a single turn.

    Returns:
        List of {"tool": tool_name, "args": {...}} for every tool call made.
    """
    client = get_client()
    model_name = model or settings.OPENAI_MODEL

    all_tool_calls: list[dict] = []
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        tools=tools,
        tool_choice="required",
    )

    choice = response.choices[0]
    message = choice.message

    if not message.tool_calls:
        logger.warning("LLM returned no tool calls; finish_reason=%s content=%r",
                       choice.finish_reason, message.content)
        return all_tool_calls

    for tc in message.tool_calls:
        try:
            args = json.loads(tc.function.arguments)
        except json.JSONDecodeError:
            args = {"raw": tc.function.arguments}

        all_tool_calls.append({"tool": tc.function.name, "args": args})

    logger.info("LLM collected %d tool calls", len(all_tool_calls))
    return all_tool_calls


def call_simple(
    system_prompt: str,
    user_message: str,
    model: str | None = None,
) -> str:
    """Simple LLM call without tools — returns text content."""
    client = get_client()
    model_name = model or settings.OPENAI_MODEL
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content or ""
