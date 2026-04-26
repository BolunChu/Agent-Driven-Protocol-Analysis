"""Protocol analysis tool functions for agent function-calling.

Each tool has a clear input/output schema and returns structured JSON.
These tools are the core building blocks that agents call via function calling.
"""

from __future__ import annotations
import json
import re
from typing import Any


def extract_message_types(input_sessions: list[dict]) -> dict:
    """Extract unique message types from parsed session events.

    Args:
        input_sessions: List of parsed protocol events, each with
            'message_type', 'direction', 'raw', 'fields', etc.

    Returns:
        {
            "message_types": [
                {"name": "USER", "count": 3, "directions": ["client_to_server"]},
                ...
            ]
        }
    """
    type_map: dict[str, dict] = {}
    for event in input_sessions:
        mt = event.get("message_type", "UNKNOWN")
        if mt not in type_map:
            type_map[mt] = {"name": mt, "count": 0, "directions": set()}
        type_map[mt]["count"] += 1
        direction = event.get("direction", "unknown")
        type_map[mt]["directions"].add(direction)

    result = []
    for mt_info in type_map.values():
        mt_info["directions"] = sorted(mt_info["directions"])
        result.append(mt_info)

    return {"message_types": sorted(result, key=lambda x: x["name"])}


def extract_fields_and_constraints(input_sessions: list[dict]) -> dict:
    """Extract field names and basic constraints for each message type.

    Returns:
        {
            "fields_by_type": {
                "USER": {
                    "fields": ["username"],
                    "constraints": ["username is required"]
                },
                ...
            }
        }
    """
    fields_by_type: dict[str, dict] = {}
    for event in input_sessions:
        mt = event.get("message_type", "UNKNOWN")
        fields = event.get("fields", {})
        if mt not in fields_by_type:
            fields_by_type[mt] = {"fields": set(), "constraints": []}
        for field_name in fields.keys():
            fields_by_type[mt]["fields"].add(field_name)

    # Convert sets to lists
    for mt in fields_by_type:
        fields_by_type[mt]["fields"] = sorted(fields_by_type[mt]["fields"])
        # Add basic constraint: all observed fields are required
        for f in fields_by_type[mt]["fields"]:
            fields_by_type[mt]["constraints"].append(f"{f} is present in all observed {mt} messages")

    return {"fields_by_type": fields_by_type}


def infer_candidate_states(input_sessions: list[list[dict]]) -> dict:
    """Infer candidate protocol states from session sequences.

    Uses response codes and message ordering to cluster states.

    Args:
        input_sessions: List of sessions, each session is a list of events.

    Returns:
        {
            "states": [
                {"name": "INIT", "description": "Initial connection state"},
                ...
            ]
        }
    """
    states = [
        {"name": "INIT", "description": "Initial connection state before any command"},
    ]
    seen_patterns: set[str] = set()

    for session in input_sessions:
        for i, event in enumerate(session):
            resp = event.get("response") or {}
            code = resp.get("code", "")
            mt = event.get("message_type", "")

            # Authentication detection
            if mt in ("USER", "PASS") and code.startswith("3"):
                if "AUTH_PENDING" not in seen_patterns:
                    states.append({"name": "AUTH_PENDING", "description": "Awaiting authentication completion"})
                    seen_patterns.add("AUTH_PENDING")
            if mt == "PASS" and code.startswith("2"):
                if "AUTHENTICATED" not in seen_patterns:
                    states.append({"name": "AUTHENTICATED", "description": "Successfully authenticated"})
                    seen_patterns.add("AUTHENTICATED")
            if mt == "QUIT":
                if "CLOSED" not in seen_patterns:
                    states.append({"name": "CLOSED", "description": "Session terminated"})
                    seen_patterns.add("CLOSED")
            if mt in ("PASV", "EPSV", "PORT", "EPRT") and code.startswith(("2", "3")):
                if "DATA_CHANNEL_READY" not in seen_patterns:
                    states.append({"name": "DATA_CHANNEL_READY", "description": "Data connection parameters negotiated; waiting for a transfer command"})
                    seen_patterns.add("DATA_CHANNEL_READY")
            # Data transfer state
            if mt in ("LIST", "RETR", "STOR", "NLST", "MLSD", "APPE"):
                if "DATA_TRANSFER" not in seen_patterns:
                    states.append({"name": "DATA_TRANSFER", "description": "Data transfer in progress"})
                    seen_patterns.add("DATA_TRANSFER")
            if mt == "RNFR":
                if "RENAME_PENDING" not in seen_patterns:
                    states.append({"name": "RENAME_PENDING", "description": "Rename source accepted, waiting for RNTO"})
                    seen_patterns.add("RENAME_PENDING")
            if mt == "REIN":
                if "RESETTING" not in seen_patterns:
                    states.append({"name": "RESETTING", "description": "Session reinitialization in progress"})
                    seen_patterns.add("RESETTING")

    return {"states": states}


def propose_transitions(states: list[dict], messages: list[dict]) -> dict:
    """Propose candidate state transitions based on states and message types.

    Args:
        states: List of candidate states.
        messages: List of message type dicts with 'name' field.

    Returns:
        {
            "transitions": [
                {
                    "from_state": "INIT",
                    "to_state": "AUTH_PENDING",
                    "message_type": "USER",
                    "confidence": 0.7
                },
                ...
            ]
        }
    """
    state_names = {s["name"] for s in states}
    transitions = []

    # FTP-specific heuristic transition proposals
    ftp_rules = [
        ("INIT", "AUTH_PENDING", "USER", 0.8),
        ("AUTH_PENDING", "AUTHENTICATED", "PASS", 0.75),
        ("AUTHENTICATED", "AUTHENTICATED", "ACCT", 0.62),
        ("AUTHENTICATED", "AUTHENTICATED", "PWD", 0.7),
        ("AUTHENTICATED", "AUTHENTICATED", "CWD", 0.7),
        ("AUTHENTICATED", "AUTHENTICATED", "CDUP", 0.68),
        ("AUTHENTICATED", "AUTHENTICATED", "XCWD", 0.66),
        ("AUTHENTICATED", "AUTHENTICATED", "XPWD", 0.66),
        ("AUTHENTICATED", "AUTHENTICATED", "XCUP", 0.66),
        ("AUTHENTICATED", "AUTHENTICATED", "MKD", 0.68),
        ("AUTHENTICATED", "AUTHENTICATED", "XMKD", 0.66),
        ("AUTHENTICATED", "AUTHENTICATED", "RMD", 0.68),
        ("AUTHENTICATED", "AUTHENTICATED", "XRMD", 0.66),
        ("AUTHENTICATED", "AUTHENTICATED", "DELE", 0.68),
        ("AUTHENTICATED", "AUTHENTICATED", "TYPE", 0.68),
        ("AUTHENTICATED", "AUTHENTICATED", "MODE", 0.64),
        ("AUTHENTICATED", "AUTHENTICATED", "STRU", 0.64),
        ("AUTHENTICATED", "AUTHENTICATED", "SMNT", 0.58),
        ("AUTHENTICATED", "AUTHENTICATED", "SYST", 0.66),
        ("AUTHENTICATED", "AUTHENTICATED", "FEAT", 0.66),
        ("AUTHENTICATED", "AUTHENTICATED", "HELP", 0.64),
        ("AUTHENTICATED", "AUTHENTICATED", "NOOP", 0.66),
        ("AUTHENTICATED", "AUTHENTICATED", "MLST", 0.72),
        ("AUTHENTICATED", "AUTHENTICATED", "SIZE", 0.72),
        ("AUTHENTICATED", "AUTHENTICATED", "STAT", 0.7),
        ("AUTHENTICATED", "RENAME_PENDING", "RNFR", 0.76),
        ("RENAME_PENDING", "AUTHENTICATED", "RNTO", 0.76),
        ("AUTHENTICATED", "RESETTING", "REIN", 0.74),
        ("RESETTING", "AUTH_PENDING", "USER", 0.66),
        ("AUTHENTICATED", "DATA_CHANNEL_READY", "PASV", 0.78),
        ("AUTHENTICATED", "DATA_CHANNEL_READY", "EPSV", 0.78),
        ("AUTHENTICATED", "DATA_CHANNEL_READY", "PORT", 0.74),
        ("AUTHENTICATED", "DATA_CHANNEL_READY", "EPRT", 0.74),
        ("AUTHENTICATED", "DATA_TRANSFER", "LIST", 0.7),
        ("AUTHENTICATED", "DATA_TRANSFER", "MLSD", 0.68),
        ("AUTHENTICATED", "DATA_TRANSFER", "RETR", 0.65),
        ("AUTHENTICATED", "DATA_TRANSFER", "STOR", 0.65),
        ("AUTHENTICATED", "DATA_TRANSFER", "APPE", 0.65),
        ("DATA_CHANNEL_READY", "DATA_TRANSFER", "LIST", 0.82),
        ("DATA_CHANNEL_READY", "DATA_TRANSFER", "NLST", 0.8),
        ("DATA_CHANNEL_READY", "DATA_TRANSFER", "MLSD", 0.82),
        ("DATA_CHANNEL_READY", "DATA_TRANSFER", "RETR", 0.8),
        ("DATA_CHANNEL_READY", "DATA_TRANSFER", "STOR", 0.8),
        ("DATA_CHANNEL_READY", "DATA_TRANSFER", "APPE", 0.78),
        ("DATA_TRANSFER", "AUTHENTICATED", "LIST", 0.6),  # after transfer completes
        ("DATA_TRANSFER", "AUTHENTICATED", "MLSD", 0.6),
        ("DATA_TRANSFER", "AUTHENTICATED", "RETR", 0.58),
        ("DATA_TRANSFER", "AUTHENTICATED", "STOR", 0.58),
        ("AUTHENTICATED", "CLOSED", "QUIT", 0.9),
        ("INIT", "CLOSED", "QUIT", 0.6),
    ]

    msg_names = {m["name"] for m in messages}
    for from_s, to_s, mt, conf in ftp_rules:
        if from_s in state_names and to_s in state_names and mt in msg_names:
            transitions.append({
                "from_state": from_s,
                "to_state": to_s,
                "message_type": mt,
                "confidence": conf,
            })

    return {"transitions": transitions}


def score_evidence(claim: dict, evidence_list: list[dict]) -> dict:
    """Score a list of evidence items against a claim.

    Args:
        claim: {"type": "transition", "description": "INIT -> AUTH_PENDING via USER"}
        evidence_list: [{"source_type": "trace", "snippet": "...", "source_ref": "..."}]

    Returns:
        {
            "claim": claim,
            "scored_evidence": [
                {"source_type": "trace", "snippet": "...", "score": 0.8, "source_ref": "..."},
                ...
            ],
            "aggregate_confidence": 0.75,
            "status": "supported"
        }
    """
    scored = []
    for ev in evidence_list:
        # Simple heuristic scoring based on source type
        base_score = {"doc": 0.7, "trace": 0.8, "probe": 0.9, "code": 0.75}.get(
            ev.get("source_type", ""), 0.5
        )
        scored.append({**ev, "score": base_score})

    if not scored:
        return {
            "claim": claim,
            "scored_evidence": [],
            "aggregate_confidence": 0.0,
            "status": "hypothesis",
        }

    avg = sum(e["score"] for e in scored) / len(scored)
    # Boost for multiple sources
    if len(set(e.get("source_type") for e in scored)) > 1:
        avg = min(avg + 0.1, 1.0)

    status = "hypothesis"
    if avg >= 0.7 and len(scored) >= 2:
        status = "supported"
    elif any(e.get("contradicts", False) for e in scored):
        status = "disputed"

    return {
        "claim": claim,
        "scored_evidence": scored,
        "aggregate_confidence": round(avg, 3),
        "status": status,
    }


def generate_probe(model_snapshot: dict, ambiguity: dict) -> dict:
    """Generate a probe request to resolve an ambiguity in the model.

    Args:
        model_snapshot: Current protocol model (states, transitions).
        ambiguity: Description of the ambiguity to resolve, e.g.,
            {"type": "transition_order", "description": "Is PASS required after USER?"}

    Returns:
        {
            "goal": "Verify PASS must follow USER",
            "probe_sequence": [
                {"command": "PASS test", "expected_behavior": "error if no prior USER"}
            ]
        }
    """
    desc = ambiguity.get("description", "")
    probes = []

    if "PASS" in desc and "USER" in desc:
        probes.append({
            "command": "PASS testpass",
            "expected_behavior": "Server should reject with 503 (bad sequence) if USER not sent first",
        })
    elif "LIST" in desc:
        probes.append({
            "command": "LIST",
            "expected_behavior": "Server should reject with 530 if not authenticated",
        })
    else:
        probes.append({
            "command": desc,
            "expected_behavior": "Observe server response to determine validity",
        })

    return {
        "goal": f"Resolve: {desc}",
        "probe_sequence": probes,
    }


def update_protocol_model(model_snapshot: dict, new_observation: dict) -> dict:
    """Update the protocol model based on a new observation (e.g., probe result).

    Args:
        model_snapshot: Current model dict.
        new_observation: Observation from probe or new evidence.

    Returns:
        Updated model snapshot with change log.
    """
    changes = []
    updated = json.loads(json.dumps(model_snapshot))  # deep copy

    obs_type = new_observation.get("type", "")
    if obs_type == "transition_confirmed":
        # Find and upgrade transition status
        for t in updated.get("transitions", []):
            if (t.get("from_state") == new_observation.get("from_state")
                    and t.get("to_state") == new_observation.get("to_state")
                    and t.get("message_type") == new_observation.get("message_type")):
                old_status = t.get("status", "hypothesis")
                t["status"] = "supported"
                t["confidence"] = min(t.get("confidence", 0) + 0.15, 1.0)
                changes.append(f"Transition {t['from_state']}->{t['to_state']} via {t['message_type']}: "
                               f"{old_status} -> supported")
    elif obs_type == "transition_disputed":
        for t in updated.get("transitions", []):
            if (t.get("from_state") == new_observation.get("from_state")
                    and t.get("to_state") == new_observation.get("to_state")
                    and t.get("message_type") == new_observation.get("message_type")):
                old_status = t.get("status", "hypothesis")
                t["status"] = "disputed"
                t["confidence"] = max(t.get("confidence", 0) - 0.2, 0.0)
                changes.append(f"Transition {t['from_state']}->{t['to_state']} via {t['message_type']}: "
                               f"{old_status} -> disputed")

    return {
        "updated_model": updated,
        "changes": changes,
    }
