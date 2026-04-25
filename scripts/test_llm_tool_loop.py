"""Test multi-turn tool-calling loop while preserving the raw assistant message.

Purpose:
- Reproduce the second-round tool-calling request pattern used in llm_client.py
- Verify whether keeping the raw assistant message avoids provider errors such as
  missing `thought_signature`

Run:
    python3 scripts/test_llm_tool_loop.py
"""

from __future__ import annotations
import json
import os
import traceback
from pathlib import Path

from openai import OpenAI


def load_env() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    load_env()

    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        base_url=os.environ.get("OPENAI_BASE_URL", ""),
        max_retries=0,
    )
    model = os.environ.get("OPENAI_MODEL", "gemini-3-flash-preview")

    tools = [
        {
            "type": "function",
            "function": {
                "name": "greet",
                "description": "Greet someone by name",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                    },
                    "required": ["name"],
                },
            },
        }
    ]

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Call the greet tool for World, then continue normally."},
    ]

    print("=== Round 1 ===")
    try:
        first = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
    except Exception as e:
        print("Round 1 FAIL:", type(e).__name__, e)
        traceback.print_exc()
        return
    first_msg = first.choices[0].message
    print("finish_reason:", first.choices[0].finish_reason)
    print("tool_calls:", first_msg.tool_calls)

    if not first_msg.tool_calls:
        print("No tool calls returned in round 1.")
        return

    messages.append(first_msg.model_dump(exclude_none=True))
    for tc in first_msg.tool_calls:
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps({
                    "status": "ok",
                    "result": f"Hello, {json.loads(tc.function.arguments).get('name', 'unknown')}!",
                }),
            }
        )

    print()
    print("=== Round 2 ===")
    print("Sending messages:")
    print(json.dumps(messages, indent=2, ensure_ascii=False))
    print()

    try:
        second = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
    except Exception as e:
        print("Round 2 FAIL:", type(e).__name__, e)
        traceback.print_exc()
        return
    second_msg = second.choices[0].message
    print("finish_reason:", second.choices[0].finish_reason)
    print("content:", second_msg.content)
    print("tool_calls:", second_msg.tool_calls)


if __name__ == "__main__":
    main()
