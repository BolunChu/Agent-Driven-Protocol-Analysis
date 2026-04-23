"""Trace Agent — recovers message patterns, states, and transitions from traces.

Task 6: Analyse session traces to extract message patterns, response patterns,
and coarse-grained state clusters.
"""

from __future__ import annotations
import json
from sqlmodel import Session, select

from ..models.domain import (
    SessionTrace, ProtocolState, Transition, MessageType, Evidence,
)
from ..tools.protocol_tools import (
    extract_message_types, infer_candidate_states, propose_transitions,
)
from ..tools.ftp_parser import parse_ftp_session, parse_ftp_session_pairs


def run_trace_agent(project_id: int, session: Session) -> dict:
    """Run the Trace Agent on all trace-type sessions for this project.

    Steps:
    1. Parse all trace sessions into event lists
    2. Extract message types observed in traces
    3. Infer candidate states
    4. Propose transitions
    5. Write states, transitions, and evidence to DB
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
        # Try both parsing strategies
        events = parse_ftp_session(trace.raw_content)
        if not events:
            events = parse_ftp_session_pairs(trace.raw_content)
        if events:
            all_events.extend(events)
            all_sessions.append(events)
            # Update parsed content
            trace.parsed_content = json.dumps(events, ensure_ascii=False)
            session.add(trace)

    if not all_events:
        return {"agent": "trace", "message": "No events parsed from traces", "events": 0}

    # Step 1: Extract message types from traces
    mt_result = extract_message_types(all_events)
    created_mt = []
    for mt_info in mt_result.get("message_types", []):
        existing = session.exec(
            select(MessageType).where(
                MessageType.project_id == project_id,
                MessageType.name == mt_info["name"],
            )
        ).first()
        if existing:
            # Boost confidence if also seen in traces
            existing.confidence = min(existing.confidence + 0.1, 1.0)
            session.add(existing)
        else:
            mt = MessageType(
                project_id=project_id,
                name=mt_info["name"],
                template="",
                fields_json="{}",
                confidence=0.6,
            )
            session.add(mt)
            session.commit()
            session.refresh(mt)
            created_mt.append(mt_info["name"])

            # Evidence binding
            ev = Evidence(
                project_id=project_id,
                claim_type="message_type",
                claim_id=mt.id,
                source_type="trace",
                source_ref=f"Observed in {mt_info['count']} trace events",
                snippet=f"Message type {mt_info['name']} seen {mt_info['count']} times",
                score=0.6,
            )
            session.add(ev)

    # Step 2: Infer candidate states
    states_result = infer_candidate_states(all_sessions)
    created_states = []
    for state_info in states_result.get("states", []):
        existing = session.exec(
            select(ProtocolState).where(
                ProtocolState.project_id == project_id,
                ProtocolState.name == state_info["name"],
            )
        ).first()
        if not existing:
            state = ProtocolState(
                project_id=project_id,
                name=state_info["name"],
                description=state_info["description"],
                confidence=0.6,
            )
            session.add(state)
            session.commit()
            session.refresh(state)
            created_states.append(state_info["name"])

            # Evidence
            ev = Evidence(
                project_id=project_id,
                claim_type="state",
                claim_id=state.id,
                source_type="trace",
                source_ref="Inferred from session trace patterns",
                snippet=f"State {state_info['name']}: {state_info['description']}",
                score=0.6,
            )
            session.add(ev)

    # Step 3: Propose transitions
    all_mt = session.exec(
        select(MessageType).where(MessageType.project_id == project_id)
    ).all()
    all_states = session.exec(
        select(ProtocolState).where(ProtocolState.project_id == project_id)
    ).all()

    trans_result = propose_transitions(
        [{"name": s.name} for s in all_states],
        [{"name": m.name} for m in all_mt],
    )

    created_trans = []
    for t_info in trans_result.get("transitions", []):
        existing = session.exec(
            select(Transition).where(
                Transition.project_id == project_id,
                Transition.from_state == t_info["from_state"],
                Transition.to_state == t_info["to_state"],
                Transition.message_type == t_info["message_type"],
            )
        ).first()
        if not existing:
            trans = Transition(
                project_id=project_id,
                from_state=t_info["from_state"],
                to_state=t_info["to_state"],
                message_type=t_info["message_type"],
                confidence=t_info["confidence"],
                status="hypothesis",
            )
            session.add(trans)
            session.commit()
            session.refresh(trans)
            created_trans.append(f"{t_info['from_state']} -> {t_info['to_state']} via {t_info['message_type']}")

            # Evidence
            ev = Evidence(
                project_id=project_id,
                claim_type="transition",
                claim_id=trans.id,
                source_type="trace",
                source_ref="Proposed from trace analysis",
                snippet=f"Transition inferred from {len(all_sessions)} session(s)",
                score=t_info["confidence"],
            )
            session.add(ev)

    session.commit()

    return {
        "agent": "trace",
        "events_parsed": len(all_events),
        "sessions_processed": len(all_sessions),
        "message_types_created": created_mt,
        "states_created": created_states,
        "transitions_created": created_trans,
    }
