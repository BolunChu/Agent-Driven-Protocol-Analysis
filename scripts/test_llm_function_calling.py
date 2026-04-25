"""Standalone test script for LLM function calling.

Run:  python3 scripts/test_llm_function_calling.py
Adjust the TEST_* variables below to debug request format issues.
"""

import os
import sys
import json
import traceback
from pathlib import Path

# Load .env
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from openai import OpenAI

# ── Config (edit these to test variants) ──────────────────────────────────
API_KEY  = os.environ.get("OPENAI_API_KEY", "")
BASE_URL = os.environ.get("OPENAI_BASE_URL", "")
MODEL    = os.environ.get("OPENAI_MODEL", "gemini-3-flash-preview")

# ── Test payloads ──────────────────────────────────────────────────────────

SYSTEM = "You are a helpful assistant."
USER   = "Please call the greet tool with name='World'."

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "greet",
            "description": "Greet someone by name",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Person to greet"},
                },
                "required": ["name"],
            },
        },
    }
]

# ── Run test ───────────────────────────────────────────────────────────────

def main():
    print(f"BASE_URL : {BASE_URL}")
    print(f"MODEL    : {MODEL}")
    print(f"API_KEY  : {API_KEY[:12]}…")
    print()

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL, max_retries=0)

    # ── Test 1: plain chat (no tools) ──────────────────────────────────
    print("=== Test 1: Plain chat (no tools) ===")
    try:
        r = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user",   "content": "Say: hello world"},
            ],
        )
        print("OK:", r.choices[0].message.content)
    except Exception as e:
        print("FAIL:", type(e).__name__, e)
        traceback.print_exc()

    print()

    # ── Test 2: function calling with tool_choice=auto ─────────────────
    print("=== Test 2: Function calling (tool_choice=auto) ===")
    try:
        r = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user",   "content": USER},
            ],
            tools=TOOLS,
            tool_choice="auto",
        )
        msg = r.choices[0].message
        print("finish_reason:", r.choices[0].finish_reason)
        print("content:", msg.content)
        print("tool_calls:", msg.tool_calls)
    except Exception as e:
        print("FAIL:", type(e).__name__, e)
        traceback.print_exc()

    print()

    # ── Test 3: function calling with tool_choice=required ─────────────
    print("=== Test 3: Function calling (tool_choice=required) ===")
    try:
        r = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user",   "content": USER},
            ],
            tools=TOOLS,
            tool_choice="required",
        )
        msg = r.choices[0].message
        print("finish_reason:", r.choices[0].finish_reason)
        print("tool_calls:", msg.tool_calls)
        if msg.tool_calls:
            for tc in msg.tool_calls:
                print(f"  tool={tc.function.name} args={tc.function.arguments}")
    except Exception as e:
        print("FAIL:", type(e).__name__, e)
        traceback.print_exc()

    print()

    # ── Test 4: function calling with tool_choice=specific function ─────
    print("=== Test 4: Function calling (tool_choice={type:function, function:{name:greet}}) ===")
    try:
        r = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user",   "content": USER},
            ],
            tools=TOOLS,
            tool_choice={"type": "function", "function": {"name": "greet"}},
        )
        msg = r.choices[0].message
        print("finish_reason:", r.choices[0].finish_reason)
        print("tool_calls:", msg.tool_calls)
        if msg.tool_calls:
            for tc in msg.tool_calls:
                print(f"  tool={tc.function.name} args={tc.function.arguments}")
    except Exception as e:
        print("FAIL:", type(e).__name__, e)
        traceback.print_exc()

    print()

    # ── Test 5: raw request body dump (for inspection) ─────────────────
    print("=== Test 5: Raw request body (printed, not sent) ===")
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user",   "content": USER},
        ],
        "tools": TOOLS,
        "tool_choice": "auto",
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
