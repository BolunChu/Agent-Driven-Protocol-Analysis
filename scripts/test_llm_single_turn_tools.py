"""Single-turn function-calling test.

This matches the new strategy in backend/app/core/llm_client.py:
- one request only
- tool_choice='required'
- no continuation turn
- no SDK retries

Run:
    python3 scripts/test_llm_single_turn_tools.py
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
                "name": "record_item",
                "description": "Record an item",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "category": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["name", "category", "confidence"],
                },
            },
        }
    ]

    system = "You are a protocol analyst. Call the provided tool for every FTP command you identify."
    user = "Identify these FTP commands and record them: USER, PASS, LIST, QUIT."

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=tools,
            tool_choice="required",
        )
    except Exception as e:
        print("FAIL:", type(e).__name__, e)
        traceback.print_exc()
        return

    choice = resp.choices[0]
    msg = choice.message
    print("finish_reason:", choice.finish_reason)
    print("content:", msg.content)
    print("tool_calls:", msg.tool_calls)
    if msg.tool_calls:
        parsed = []
        for tc in msg.tool_calls:
            parsed.append({
                "tool": tc.function.name,
                "args": json.loads(tc.function.arguments),
            })
        print("parsed:")
        print(json.dumps(parsed, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
