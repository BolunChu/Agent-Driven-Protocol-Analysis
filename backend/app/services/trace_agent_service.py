"""Trace Agent — recovers message patterns, states, and transitions from traces.

Task 6 (LLM-upgraded): Uses Gemini function calling to infer protocol states,
transitions, and message patterns from session trace data.
"""

from __future__ import annotations
import json
import logging
from sqlmodel import Session, select

from ..models.domain import (
    SessionTrace, ProtocolState, Transition, MessageType, Evidence,
)
from ..tools.protocol_tools import extract_message_types, infer_candidate_states
from ..tools.ftp_parser import parse_ftp_session, parse_ftp_session_pairs
from ..core.llm_client import call_with_tools

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

TRACE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "record_trace_analysis",
            "description": "Record the complete trace-derived protocol analysis in a single call.",
            "parameters": {
                "type": "object",
                "properties": {
                    "states": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "confidence": {"type": "number"},
                                "evidence": {"type": "string"},
                            },
                            "required": ["name", "description", "confidence"],
                        },
                    },
                    "transitions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "from_state": {"type": "string"},
                                "to_state": {"type": "string"},
                                "message_type": {"type": "string"},
                                "confidence": {"type": "number"},
                                "reasoning": {"type": "string"},
                                "response_codes": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["from_state", "to_state", "message_type", "confidence", "reasoning"],
                        },
                    },
                    "observed_message_types": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "observed_count": {"type": "integer"},
                                "typical_position": {"type": "string"},
                                "confidence": {"type": "number"},
                            },
                            "required": ["name", "observed_count", "confidence"],
                        },
                    },
                },
                "required": ["states", "transitions", "observed_message_types"],
            },
        },
    },
]

TRACE_SYSTEM_PROMPT = """You are an expert protocol analyst. Analyze the provided FTP session traces to recover the protocol state machine.

Your goal:
1. Identify distinct protocol states (e.g., INIT before login, AUTH_PENDING during authentication, AUTHENTICATED after successful login, DATA_TRANSFER during file operations, CLOSED after QUIT)
2. Identify state transitions triggered by specific FTP commands
3. Record observed message types with frequency information

Call record_trace_analysis exactly once.
Populate states, transitions, and observed_message_types comprehensively.
- Do not use server response pseudo-types such as RESP_220 or RESP_226 as message_type values in transitions
- Use response_codes to describe server outcomes while keeping the transition trigger as the client command
- Prefer states and transitions that are strongly grounded in repeated trace patterns, especially ProFuzzBench-observed commands

Focus on patterns: what command sequences lead to state changes? What response codes indicate successful vs failed transitions?"""


def _format_sessions_for_llm(all_sessions: list[list[dict]]) -> str:
    """Format parsed session events into readable text for LLM analysis."""
    lines = []
    for i, events in enumerate(all_sessions[:20]):
        lines.append(f"\n--- Session {i+1} ---")
        for ev in events:
            mt = ev.get("message_type", "?")
            resp = ev.get("response")
            if resp:
                code = resp.get("code", "?")
                text = resp.get("text", "")[:60]
                lines.append(f"  C→S: {mt}  |  S→C: {code} {text}")
            else:
                lines.append(f"  C→S: {mt}")
    return "\n".join(lines)


def run_trace_agent(project_id: int, session: Session) -> dict:
    """Run the LLM-powered Trace Agent.

    1. Parse all trace sessions
    2. Build frequency statistics (deterministic)
    3. Call LLM to infer states and transitions
    4. Store results with evidence
    """
    traces = session.exec(
        select(SessionTrace).where(
            SessionTrace.project_id == project_id,
            SessionTrace.source_type == "trace",
        )
    ).all()

    all_events: list[dict] = []
    all_sessions: list[list[dict]] = []

    for trace in traces:
        events = parse_ftp_session(trace.raw_content)
        if not events:
            events = parse_ftp_session_pairs(trace.raw_content)
        if events:
            all_events.extend(events)
            all_sessions.append(events)
            trace.parsed_content = json.dumps(events, ensure_ascii=False)
            session.add(trace)

    if not all_events:
        return {"agent": "trace", "message": "No events parsed from traces", "events": 0}

    # Deterministic message-type frequency counts (always reliable)
    mt_result = extract_message_types(all_events)
    created_mt: list[str] = []
    for mt_info in mt_result.get("message_types", []):
        name = mt_info["name"]
        if name.startswith("RESP_") or name == "UNKNOWN":
            continue
        existing = session.exec(
            select(MessageType).where(
                MessageType.project_id == project_id,
                MessageType.name == name,
            )
        ).first()
        if existing:
            existing.confidence = min(existing.confidence + 0.1, 1.0)
            session.add(existing)
        else:
            mt = MessageType(
                project_id=project_id,
                name=name,
                template="",
                fields_json="{}",
                confidence=min(0.5 + mt_info["count"] * 0.03, 0.9),
            )
            session.add(mt)
            session.commit()
            session.refresh(mt)
            ev = Evidence(
                project_id=project_id,
                claim_type="message_type",
                claim_id=mt.id,
                source_type="trace",
                source_ref=f"Observed {mt_info['count']}x in {len(all_sessions)} sessions",
                snippet=f"{name} seen {mt_info['count']} times",
                score=min(0.5 + mt_info["count"] * 0.03, 0.9),
            )
            session.add(ev)
            created_mt.append(name)

    session.commit()

    # LLM call for state/transition inference
    sessions_text = _format_sessions_for_llm(all_sessions)
    mt_freq = "\n".join(
        f"  {m['name']}: {m['count']} occurrences"
        for m in mt_result.get("message_types", [])
        if not m["name"].startswith("RESP_")
    )
    heuristic_states = infer_candidate_states(all_sessions).get("states", [])
    heuristic_state_text = "\n".join(
        f"  - {s['name']}: {s['description']}" for s in heuristic_states
    ) or "  (none)"

    user_message = f"""## FTP Session Trace Data

Total sessions: {len(all_sessions)}
Total events: {len(all_events)}

### Message Type Frequency
{mt_freq}

### Heuristic Candidate States
{heuristic_state_text}

### Session Command/Response Sequences
{sessions_text}

Analyze these traces and record all protocol states and transitions you can identify."""

    logger.info("Trace Agent: calling LLM for project %d (%d sessions)", project_id, len(all_sessions))
    tool_calls = call_with_tools(
        system_prompt=TRACE_SYSTEM_PROMPT,
        user_message=user_message,
        tools=TRACE_TOOLS,
        max_iterations=1,
    )
    logger.info("Trace Agent: received %d tool calls", len(tool_calls))

    created_states: list[str] = []
    created_trans: list[str] = []
    fallback_used = False
    payload = {}

    if tool_calls and tool_calls[0]["tool"] == "record_trace_analysis":
        payload = tool_calls[0]["args"]

    for args in payload.get("states", []):
        name = args.get("name", "").strip().upper()
        if not name:
            continue
        existing = session.exec(
            select(ProtocolState).where(
                ProtocolState.project_id == project_id,
                ProtocolState.name == name,
            )
        ).first()
        if not existing:
            state = ProtocolState(
                project_id=project_id,
                name=name,
                description=args.get("description", ""),
                confidence=float(args.get("confidence", 0.7)),
            )
            session.add(state)
            session.commit()
            session.refresh(state)
            ev = Evidence(
                project_id=project_id,
                claim_type="state",
                claim_id=state.id,
                source_type="trace",
                source_ref="LLM Trace Agent (Gemini function calling)",
                snippet=args.get("evidence", args.get("description", name))[:500],
                score=float(args.get("confidence", 0.7)),
            )
            session.add(ev)
            created_states.append(name)

    for args in payload.get("transitions", []):
        from_s = args.get("from_state", "").strip().upper()
        to_s = args.get("to_state", "").strip().upper()
        msg = args.get("message_type", "").strip().upper()
        if not (from_s and to_s and msg) or msg.startswith("RESP_"):
            continue
        existing = session.exec(
            select(Transition).where(
                Transition.project_id == project_id,
                Transition.from_state == from_s,
                Transition.to_state == to_s,
                Transition.message_type == msg,
            )
        ).first()
        if not existing:
            trans = Transition(
                project_id=project_id,
                from_state=from_s,
                to_state=to_s,
                message_type=msg,
                confidence=float(args.get("confidence", 0.7)),
                status="hypothesis",
            )
            session.add(trans)
            session.commit()
            session.refresh(trans)
            reasoning = args.get("reasoning", "")
            resp_codes = args.get("response_codes", [])
            snippet = reasoning
            if resp_codes:
                snippet += f" (response codes: {', '.join(resp_codes)})"
            ev = Evidence(
                project_id=project_id,
                claim_type="transition",
                claim_id=trans.id,
                source_type="trace",
                source_ref="LLM Trace Agent (Gemini function calling)",
                snippet=snippet[:500],
                score=float(args.get("confidence", 0.7)),
            )
            session.add(ev)
            created_trans.append(f"{from_s} → {to_s} via {msg}")

    for args in payload.get("observed_message_types", []):
        name = args.get("name", "").strip().upper()
        if name and not name.startswith("RESP_"):
            existing = session.exec(
                select(MessageType).where(
                    MessageType.project_id == project_id,
                    MessageType.name == name,
                )
            ).first()
            if existing:
                boost = min(existing.confidence + 0.05, 0.95)
                existing.confidence = boost
                session.add(existing)
            elif name not in created_mt:
                mt = MessageType(
                    project_id=project_id,
                    name=name,
                    template="",
                    fields_json="{}",
                    confidence=float(args.get("confidence", 0.6)),
                )
                session.add(mt)
                session.commit()
                session.refresh(mt)
                ev = Evidence(
                    project_id=project_id,
                    claim_type="message_type",
                    claim_id=mt.id,
                    source_type="trace",
                    source_ref="LLM Trace Agent observation",
                    snippet=f"{name} seen ~{args.get('observed_count', '?')} times",
                    score=float(args.get("confidence", 0.6)),
                )
                session.add(ev)
                created_mt.append(name)

    if not payload:
        logger.warning("Trace Agent: LLM returned no tool calls, using rule-based fallback")
        fallback_used = True
        _apply_state_fallback(project_id, session, created_states, created_trans)

    session.commit()

    return {
        "agent": "trace",
        "events_parsed": len(all_events),
        "sessions_processed": len(all_sessions),
        "llm_tool_calls": len(tool_calls),
        "fallback_used": fallback_used,
        "message_types_updated": created_mt,
        "states_created": created_states,
        "transitions_created": created_trans,
    }


def _apply_state_fallback(project_id: int, session: Session,
                           created_states: list, created_trans: list) -> None:
    """Rule-based fallback if LLM unavailable."""
    STATES = [
        ("INIT", "Initial connection state", 0.9),
        ("AUTH_PENDING", "Awaiting authentication", 0.85),
        ("AUTHENTICATED", "Successfully authenticated", 0.9),
        ("DATA_TRANSFER", "Data transfer in progress", 0.8),
        ("CLOSED", "Session terminated", 0.9),
    ]
    TRANSITIONS = [
        ("INIT", "AUTH_PENDING", "USER", 0.85),
        ("AUTH_PENDING", "AUTHENTICATED", "PASS", 0.85),
        ("AUTHENTICATED", "AUTHENTICATED", "PWD", 0.8),
        ("AUTHENTICATED", "AUTHENTICATED", "CWD", 0.8),
        ("AUTHENTICATED", "DATA_TRANSFER", "LIST", 0.8),
        ("AUTHENTICATED", "DATA_TRANSFER", "RETR", 0.75),
        ("AUTHENTICATED", "DATA_TRANSFER", "STOR", 0.75),
        ("DATA_TRANSFER", "AUTHENTICATED", "LIST", 0.7),
        ("AUTHENTICATED", "CLOSED", "QUIT", 0.9),
        ("INIT", "CLOSED", "QUIT", 0.7),
    ]
    for name, desc, conf in STATES:
        existing = session.exec(
            select(ProtocolState).where(
                ProtocolState.project_id == project_id,
                ProtocolState.name == name,
            )
        ).first()
        if not existing:
            s = ProtocolState(project_id=project_id, name=name,
                              description=desc, confidence=conf)
            session.add(s)
            session.commit()
            session.refresh(s)
            ev = Evidence(project_id=project_id, claim_type="state",
                          claim_id=s.id, source_type="trace",
                          source_ref="rule-based fallback", snippet=desc, score=conf)
            session.add(ev)
            created_states.append(name)
    for from_s, to_s, msg, conf in TRANSITIONS:
        existing = session.exec(
            select(Transition).where(
                Transition.project_id == project_id,
                Transition.from_state == from_s,
                Transition.to_state == to_s,
                Transition.message_type == msg,
            )
        ).first()
        if not existing:
            t = Transition(project_id=project_id, from_state=from_s,
                           to_state=to_s, message_type=msg,
                           confidence=conf, status="hypothesis")
            session.add(t)
            session.commit()
            session.refresh(t)
            ev = Evidence(project_id=project_id, claim_type="transition",
                          claim_id=t.id, source_type="trace",
                          source_ref="rule-based fallback",
                          snippet=f"{from_s}→{to_s} via {msg}", score=conf)
            session.add(ev)
            created_trans.append(f"{from_s}→{to_s} via {msg}")
