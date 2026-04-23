"""Unit tests for FTP parser and protocol tools."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.tools.ftp_parser import parse_ftp_command, parse_ftp_response, parse_ftp_session
from app.tools.protocol_tools import (
    extract_message_types, extract_fields_and_constraints,
    infer_candidate_states, propose_transitions, score_evidence,
    generate_probe, update_protocol_model,
)


def test_parse_ftp_command():
    result = parse_ftp_command("USER anonymous")
    assert result is not None
    assert result["message_type"] == "USER"
    assert result["fields"]["username"] == "anonymous"

    result = parse_ftp_command("PASS secret123")
    assert result["message_type"] == "PASS"
    assert result["fields"]["password"] == "secret123"

    result = parse_ftp_command("LIST")
    assert result["message_type"] == "LIST"

    result = parse_ftp_command("QUIT")
    assert result["message_type"] == "QUIT"

    result = parse_ftp_command("PWD")
    assert result["message_type"] == "PWD"
    print("✓ test_parse_ftp_command passed")


def test_parse_ftp_response():
    result = parse_ftp_response("331 User name okay, need password.")
    assert result["code"] == "331"
    assert "password" in result["text"].lower()

    result = parse_ftp_response("230 User logged in.")
    assert result["code"] == "230"
    print("✓ test_parse_ftp_response passed")


def test_parse_ftp_session():
    session_text = """220 Welcome
> USER anonymous
331 Need password.
> PASS test@test.com
230 Logged in.
> LIST
150 Opening connection.
226 Done.
> QUIT
221 Bye."""

    events = parse_ftp_session(session_text)
    assert len(events) >= 4
    # Check USER event
    user_events = [e for e in events if e.get("message_type") == "USER"]
    assert len(user_events) == 1
    assert user_events[0]["fields"]["username"] == "anonymous"
    assert user_events[0]["response"]["code"] == "331"
    print(f"✓ test_parse_ftp_session passed ({len(events)} events)")


def test_extract_message_types():
    events = [
        {"message_type": "USER", "direction": "client_to_server"},
        {"message_type": "PASS", "direction": "client_to_server"},
        {"message_type": "LIST", "direction": "client_to_server"},
        {"message_type": "USER", "direction": "client_to_server"},
        {"message_type": "QUIT", "direction": "client_to_server"},
    ]
    result = extract_message_types(events)
    types = result["message_types"]
    names = [t["name"] for t in types]
    assert "USER" in names
    assert "PASS" in names
    assert "LIST" in names
    assert "QUIT" in names
    user_info = next(t for t in types if t["name"] == "USER")
    assert user_info["count"] == 2
    print("✓ test_extract_message_types passed")


def test_infer_candidate_states():
    sessions = [[
        {"message_type": "USER", "response": {"code": "331"}},
        {"message_type": "PASS", "response": {"code": "230"}},
        {"message_type": "LIST", "response": {"code": "150"}},
        {"message_type": "QUIT", "response": {"code": "221"}},
    ]]
    result = infer_candidate_states(sessions)
    state_names = [s["name"] for s in result["states"]]
    assert "INIT" in state_names
    assert "AUTH_PENDING" in state_names
    assert "AUTHENTICATED" in state_names
    print(f"✓ test_infer_candidate_states passed (states: {state_names})")


def test_propose_transitions():
    states = [{"name": "INIT"}, {"name": "AUTH_PENDING"}, {"name": "AUTHENTICATED"}, {"name": "CLOSED"}]
    messages = [{"name": "USER"}, {"name": "PASS"}, {"name": "LIST"}, {"name": "QUIT"}]
    result = propose_transitions(states, messages)
    assert len(result["transitions"]) >= 3
    print(f"✓ test_propose_transitions passed ({len(result['transitions'])} transitions)")


def test_score_evidence():
    claim = {"type": "transition", "description": "INIT -> AUTH_PENDING via USER"}
    evidence = [
        {"source_type": "doc", "snippet": "USER command initiates auth", "source_ref": "rfc959"},
        {"source_type": "trace", "snippet": "Observed USER -> 331 in session", "source_ref": "trace:1"},
    ]
    result = score_evidence(claim, evidence)
    assert result["status"] == "supported"
    assert result["aggregate_confidence"] > 0.7
    print(f"✓ test_score_evidence passed (confidence={result['aggregate_confidence']})")


def test_generate_probe():
    model = {"states": ["INIT", "AUTH_PENDING"]}
    ambiguity = {"description": "Is PASS required after USER?"}
    result = generate_probe(model, ambiguity)
    assert "goal" in result
    assert len(result["probe_sequence"]) > 0
    print(f"✓ test_generate_probe passed")


if __name__ == "__main__":
    test_parse_ftp_command()
    test_parse_ftp_response()
    test_parse_ftp_session()
    test_extract_message_types()
    test_infer_candidate_states()
    test_propose_transitions()
    test_score_evidence()
    test_generate_probe()
    print("\n✅ All tests passed!")
