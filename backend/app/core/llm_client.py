"""LLM client wrapper — OpenAI-compatible function calling for protocol agents."""

from __future__ import annotations
import json
import logging
import time
from openai import OpenAI
from .config import settings

logger = logging.getLogger(__name__)

_client: OpenAI | None = None

MAX_RETRIES = 5
RETRY_BASE_DELAY = 2.0  # seconds, doubles each attempt


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            max_retries=0,  # We handle retries ourselves
        )
    return _client


def call_with_tools(
    system_prompt: str,
    user_message: str,
    tools: list[dict],
    max_iterations: int = 1,
    model: str | None = None,
) -> list[dict]:
    """Call LLM with function calling tools, retrying up to MAX_RETRIES times.

    Raises RuntimeError after all retries are exhausted — no rule-based fallback.
    Returns:
        List of {"tool": tool_name, "args": {...}} for every tool call made.
    """
    client = get_client()
    model_name = model or settings.OPENAI_MODEL

    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
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
                raise RuntimeError(
                    f"LLM returned no tool calls (finish_reason={choice.finish_reason!r}, "
                    f"content={message.content!r})"
                )

            all_tool_calls: list[dict] = []
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {"raw": tc.function.arguments}
                all_tool_calls.append({"tool": tc.function.name, "args": args})

            logger.info("LLM collected %d tool calls (attempt %d)", len(all_tool_calls), attempt)
            return all_tool_calls

        except Exception as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "LLM call failed (attempt %d/%d): %s — retrying in %.1fs",
                    attempt, MAX_RETRIES, exc, delay,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "LLM call failed after %d attempts: %s — aborting (no fallback)",
                    MAX_RETRIES, exc,
                )

    raise RuntimeError(
        f"LLM call_with_tools failed after {MAX_RETRIES} attempts"
    ) from last_exc


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
