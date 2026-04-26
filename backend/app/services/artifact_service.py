from __future__ import annotations

import json
from collections import defaultdict

from sqlmodel import Session, select

from ..models.domain import Invariant, MessageType, ProbeRun, ProtocolProject, ProtocolState, SessionTrace, Transition
from ..protocols.registry import get_protocol_adapter


def _load_trace_sessions(project_id: int, session: Session) -> list[list[dict]]:
    project = session.get(ProtocolProject, project_id)
    adapter = get_protocol_adapter(project.protocol_name if project else "FTP")
    traces = session.exec(
        select(SessionTrace).where(
            SessionTrace.project_id == project_id,
            SessionTrace.source_type == "trace",
        )
    ).all()
    sessions: list[list[dict]] = []
    for trace in traces:
        events: list[dict] = []
        if trace.parsed_content:
            try:
                parsed = json.loads(trace.parsed_content)
                if isinstance(parsed, list):
                    events = parsed
            except Exception:
                events = []
        if not events:
            try:
                events = adapter.parse_session(trace.raw_content)
            except Exception:
                events = []
        if not events:
            try:
                events = adapter.parse_session_pairs(trace.raw_content)
            except Exception:
                events = []
        if events:
            sessions.append(events)
    return sessions


def _default_template(message_type: str, field_names: list[str]) -> str:
    if not field_names:
        return f"{message_type}\\r\\n"
    placeholders = " ".join(f"<{field_name}>" for field_name in field_names)
    return f"{message_type} {placeholders}\\r\\n"


def _guess_field_kind(field_name: str, examples: list[str]) -> str:
    lowered = field_name.lower()
    if lowered in {"port"}:
        return "integer"
    if lowered in {"host"}:
        return "host"
    if lowered in {"filename", "directory", "path", "mount_path"}:
        return "path"
    if lowered in {"transfer_type", "transfer_mode", "file_structure", "protocol"}:
        return "enum"
    if examples and all(example.isdigit() for example in examples if example):
        return "integer"
    return "string"


def _boundary_cases(field_name: str, field_kind: str) -> list[str]:
    lowered = field_name.lower()
    if field_kind == "integer":
        return ["0", "1", "65535", "70000"]
    if field_kind == "host":
        return ["127.0.0.1", "0.0.0.0", "256.256.256.256"]
    if field_kind == "path":
        return ["/", "../", "/tmp/" + "A" * 64, "./nested/dir"]
    if lowered in {"username", "account", "topic"}:
        return ["", "anonymous", "admin", "A" * 128]
    if lowered == "password":
        return ["", "anonymous@test.com", "wrongpass", "P" * 128]
    return ["", "A" * 128, "%s%s%s", "../"]


def _dangerous_inputs(message_type: str, field_names: list[str]) -> list[str]:
    cases = []
    if any(name in field_names for name in {"filename", "directory", "path", "mount_path"}):
        cases.extend(["long path", "parent traversal", "nested directory chain"])
    if any(name in field_names for name in {"username", "password", "account"}):
        cases.extend(["empty credential", "overlong credential", "credential retry loop"])
    if message_type in {"PORT", "EPRT", "PASV", "EPSV"}:
        cases.extend(["invalid data endpoint", "unreachable port", "mismatched address family"])
    if message_type in {"TYPE", "MODE", "STRU"}:
        cases.extend(["invalid enum token", "lowercase enum", "missing parameter"])
    if message_type in {"HELP", "STAT", "SMNT"}:
        cases.extend(["unexpected optional argument", "empty optional argument"])
    if not cases:
        cases.extend(["unexpected extra argument", "repeated command", "oversized token"])
    return list(dict.fromkeys(cases))


def build_protocol_schema(project_id: int, session: Session) -> dict:
    project = session.get(ProtocolProject, project_id)
    message_types = session.exec(
        select(MessageType).where(MessageType.project_id == project_id)
    ).all()
    states = session.exec(
        select(ProtocolState).where(ProtocolState.project_id == project_id)
    ).all()
    transitions = session.exec(
        select(Transition).where(Transition.project_id == project_id)
    ).all()
    invariants = session.exec(
        select(Invariant).where(Invariant.project_id == project_id)
    ).all()
    trace_sessions = _load_trace_sessions(project_id, session)

    observed_fields: dict[str, set[str]] = defaultdict(set)
    field_examples: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    observed_counts: dict[str, int] = defaultdict(int)
    for events in trace_sessions:
        for event in events:
            message_type = event.get("message_type", "").upper()
            if not message_type or message_type.startswith("RESP_") or message_type == "UNKNOWN":
                continue
            observed_counts[message_type] += 1
            fields = event.get("fields") or {}
            for field_name, value in fields.items():
                observed_fields[message_type].add(field_name)
                rendered = str(value)
                samples = field_examples[message_type][field_name]
                if rendered and rendered not in samples and len(samples) < 5:
                    samples.append(rendered)

    transitions_by_message: dict[str, list[Transition]] = defaultdict(list)
    for transition in transitions:
        transitions_by_message[transition.message_type].append(transition)

    messages: dict[str, dict] = {}
    for message_type in sorted(message_types, key=lambda item: item.name):
        stored_fields = {}
        if message_type.fields_json:
            try:
                parsed_fields = json.loads(message_type.fields_json)
                if isinstance(parsed_fields, dict):
                    stored_fields = parsed_fields
            except Exception:
                stored_fields = {}
        field_names = sorted(set(stored_fields.keys()) | observed_fields.get(message_type.name, set()))
        field_schema = {}
        for field_name in field_names:
            examples = field_examples.get(message_type.name, {}).get(field_name, [])
            if not examples and field_name in stored_fields and stored_fields[field_name]:
                examples = [str(stored_fields[field_name])]
            field_kind = _guess_field_kind(field_name, examples)
            field_schema[field_name] = {
                "type": field_kind,
                "examples": examples,
                "boundary_cases": _boundary_cases(field_name, field_kind),
            }

        transitions_for_message = transitions_by_message.get(message_type.name, [])
        messages[message_type.name] = {
            "template": message_type.template or _default_template(message_type.name, field_names),
            "fields": field_schema,
            "preconditions": sorted({transition.from_state for transition in transitions_for_message}),
            "postconditions": sorted({transition.to_state for transition in transitions_for_message}),
            "dangerous_inputs": _dangerous_inputs(message_type.name, field_names),
            "observed_count": observed_counts.get(message_type.name, 0),
            "confidence": round(message_type.confidence, 3),
        }

    ordering_rules = [
        invariant.rule_text
        for invariant in invariants
        if invariant.rule_type in {"ordering", "conditional", "state_requirement"}
    ]

    field_constraints = [
        invariant.rule_text
        for invariant in invariants
        if invariant.rule_type == "field_constraint"
    ]

    return {
        "schema_version": 1,
        "project_id": project_id,
        "protocol": project.protocol_name if project else "FTP",
        "messages": messages,
        "states": [
            {
                "name": state.name,
                "description": state.description,
                "confidence": round(state.confidence, 3),
            }
            for state in sorted(states, key=lambda item: item.name)
        ],
        "transitions": [
            {
                "from_state": transition.from_state,
                "to_state": transition.to_state,
                "message_type": transition.message_type,
                "status": transition.status,
                "confidence": round(transition.confidence, 3),
            }
            for transition in transitions
        ],
        "ordering_rules": ordering_rules,
        "field_constraints": field_constraints,
        "dangerous_input_families": sorted(
            {
                dangerous
                for message in messages.values()
                for dangerous in message["dangerous_inputs"]
            }
        ),
    }


def _supported(message_names: set[str], *required: str) -> bool:
    return all(message in message_names for message in required)


def _seed_record(name: str, category: str, commands: list[str], expected_states: list[str], focus_messages: list[str]) -> dict:
    return {
        "name": name,
        "category": category,
        "commands": commands,
        "expected_states": expected_states,
        "focus_messages": focus_messages,
    }


def generate_seed_corpus(project_id: int, session: Session, schema: dict | None = None) -> dict:
    schema = schema or build_protocol_schema(project_id, session)
    message_names = set(schema.get("messages", {}).keys())
    generated_seeds: list[dict] = []

    login = ["USER anonymous", "PASS anonymous@test.com"] if _supported(message_names, "USER", "PASS") else []
    bad_login = ["USER admin", "PASS wrongpass"] if _supported(message_names, "USER", "PASS") else []

    if login:
        generated_seeds.append(_seed_record(
            "auth_basic_session",
            "state_progression",
            login + (["QUIT"] if "QUIT" in message_names else []),
            ["INIT", "AUTH_PENDING", "AUTHENTICATED", "CLOSED"],
            ["USER", "PASS", "QUIT"] if "QUIT" in message_names else ["USER", "PASS"],
        ))

    if login and "PWD" in message_names:
        generated_seeds.append(_seed_record(
            "auth_then_pwd",
            "post_auth_navigation",
            login + ["PWD"] + (["QUIT"] if "QUIT" in message_names else []),
            ["INIT", "AUTH_PENDING", "AUTHENTICATED"],
            ["USER", "PASS", "PWD"],
        ))

    if login and "LIST" in message_names:
        listing_prefix = []
        if "PASV" in message_names:
            listing_prefix.append("PASV")
        generated_seeds.append(_seed_record(
            "auth_then_list",
            "data_flow",
            login + listing_prefix + ["LIST"] + (["QUIT"] if "QUIT" in message_names else []),
            ["INIT", "AUTH_PENDING", "AUTHENTICATED", "DATA_TRANSFER"],
            ["USER", "PASS", *(["PASV"] if "PASV" in message_names else []), "LIST"],
        ))

    if login and _supported(message_names, "EPSV", "MLSD"):
        generated_seeds.append(_seed_record(
            "epsv_then_mlsd",
            "data_channel_negotiation",
            login + ["EPSV", "MLSD pub"] + (["QUIT"] if "QUIT" in message_names else []),
            ["INIT", "AUTH_PENDING", "AUTHENTICATED", "DATA_CHANNEL_READY", "DATA_TRANSFER"],
            ["USER", "PASS", "EPSV", "MLSD"],
        ))

    if login and _supported(message_names, "PASV", "RETR"):
        generated_seeds.append(_seed_record(
            "pasv_then_retr",
            "data_channel_negotiation",
            login + ["PASV", "RETR readme.txt"] + (["QUIT"] if "QUIT" in message_names else []),
            ["INIT", "AUTH_PENDING", "AUTHENTICATED", "DATA_CHANNEL_READY", "DATA_TRANSFER"],
            ["USER", "PASS", "PASV", "RETR"],
        ))

    if login and _supported(message_names, "PORT", "LIST"):
        generated_seeds.append(_seed_record(
            "port_then_list",
            "data_channel_negotiation",
            login + ["PORT <auto>", "LIST"] + (["QUIT"] if "QUIT" in message_names else []),
            ["INIT", "AUTH_PENDING", "AUTHENTICATED", "DATA_CHANNEL_READY", "DATA_TRANSFER"],
            ["USER", "PASS", "PORT", "LIST"],
        ))

    if login and _supported(message_names, "EPRT", "MLSD"):
        generated_seeds.append(_seed_record(
            "eprt_then_mlsd",
            "data_channel_negotiation",
            login + ["EPRT <auto>", "MLSD pub"] + (["QUIT"] if "QUIT" in message_names else []),
            ["INIT", "AUTH_PENDING", "AUTHENTICATED", "DATA_CHANNEL_READY", "DATA_TRANSFER"],
            ["USER", "PASS", "EPRT", "MLSD"],
        ))

    if login and _supported(message_names, "RNFR", "RNTO"):
        generated_seeds.append(_seed_record(
            "rename_flow",
            "state_progression",
            login + ["RNFR readme.txt", "RNTO readme_renamed.txt"] + (["QUIT"] if "QUIT" in message_names else []),
            ["INIT", "AUTH_PENDING", "AUTHENTICATED", "RENAME_PENDING"],
            ["USER", "PASS", "RNFR", "RNTO"],
        ))

    if login and any(message in message_names for message in {"ACCT", "SMNT"}):
        commands = login.copy()
        focus_messages = ["USER", "PASS"]
        if "ACCT" in message_names:
            commands.append("ACCT billing")
            focus_messages.append("ACCT")
        if "SMNT" in message_names:
            commands.append("SMNT /pub")
            focus_messages.append("SMNT")
        if "QUIT" in message_names:
            commands.append("QUIT")
        generated_seeds.append(_seed_record(
            "post_auth_account_mount",
            "post_auth_extensions",
            commands,
            ["INIT", "AUTH_PENDING", "AUTHENTICATED"],
            focus_messages,
        ))

    if login and _supported(message_names, "MKD", "CWD", "RMD"):
        commands = login + ["MKD fuzzdir", "CWD fuzzdir"]
        if "CDUP" in message_names:
            commands.append("CDUP")
        commands.append("RMD fuzzdir")
        if "QUIT" in message_names:
            commands.append("QUIT")
        generated_seeds.append(_seed_record(
            "directory_lifecycle",
            "filesystem_ops",
            commands,
            ["INIT", "AUTH_PENDING", "AUTHENTICATED"],
            ["USER", "PASS", "MKD", "CWD", "RMD"],
        ))

    if login and any(message in message_names for message in {"SIZE", "MLST", "RETR", "TYPE"}):
        commands = login.copy()
        focus_messages = ["USER", "PASS"]
        if "TYPE" in message_names:
            commands.append("TYPE I")
            focus_messages.append("TYPE")
        if "SIZE" in message_names:
            commands.append("SIZE readme.txt")
            focus_messages.append("SIZE")
        if "MLST" in message_names:
            commands.append("MLST readme.txt")
            focus_messages.append("MLST")
        if "RETR" in message_names:
            commands.append("RETR readme.txt")
            focus_messages.append("RETR")
        if "QUIT" in message_names:
            commands.append("QUIT")
        generated_seeds.append(_seed_record(
            "metadata_then_transfer",
            "data_flow",
            commands,
            ["INIT", "AUTH_PENDING", "AUTHENTICATED", "DATA_TRANSFER"],
            focus_messages,
        ))

    if login and "REIN" in message_names:
        commands = login + ["REIN"]
        if _supported(message_names, "USER", "PASS"):
            commands += ["USER anonymous", "PASS anonymous@test.com"]
        if "QUIT" in message_names:
            commands.append("QUIT")
        generated_seeds.append(_seed_record(
            "session_reset_retry",
            "state_reset",
            commands,
            ["INIT", "AUTH_PENDING", "AUTHENTICATED", "RESETTING", "AUTH_PENDING", "AUTHENTICATED"],
            ["USER", "PASS", "REIN"],
        ))

    if bad_login:
        commands = bad_login.copy()
        if login:
            commands += login
        if "QUIT" in message_names:
            commands.append("QUIT")
        generated_seeds.append(_seed_record(
            "auth_retry_sequence",
            "negative_auth",
            commands,
            ["INIT", "AUTH_PENDING", "AUTHENTICATED"],
            ["USER", "PASS"],
        ))

    if login and "CWD" in message_names:
        commands = login + ["CWD ../", "CWD /", "CWD ./nested/dir"]
        if "QUIT" in message_names:
            commands.append("QUIT")
        generated_seeds.append(_seed_record(
            "path_edge_cases",
            "boundary_case",
            commands,
            ["INIT", "AUTH_PENDING", "AUTHENTICATED"],
            ["USER", "PASS", "CWD"],
        ))

    if _supported(message_names, "USER", "PASS"):
        commands = ["USER " + "A" * 64, "PASS " + "P" * 64]
        if "QUIT" in message_names:
            commands.append("QUIT")
        generated_seeds.append(_seed_record(
            "overlong_credentials",
            "boundary_case",
            commands,
            ["INIT", "AUTH_PENDING"],
            ["USER", "PASS"],
        ))

    deduped: list[dict] = []
    seen = set()
    for seed in generated_seeds:
        key = tuple(seed["commands"])
        if key not in seen:
            deduped.append(seed)
            seen.add(key)

    categories = sorted({seed["category"] for seed in deduped})
    return {
        "project_id": project_id,
        "generated_seeds": deduped,
        "categories": categories,
        "seed_count": len(deduped),
    }


def analyze_iteration_feedback(project_id: int, session: Session, schema: dict | None = None, seed_corpus: dict | None = None) -> dict:
    schema = schema or build_protocol_schema(project_id, session)
    seed_corpus = seed_corpus or generate_seed_corpus(project_id, session, schema)

    states = session.exec(select(ProtocolState).where(ProtocolState.project_id == project_id)).all()
    transitions = session.exec(select(Transition).where(Transition.project_id == project_id)).all()
    invariants = session.exec(select(Invariant).where(Invariant.project_id == project_id)).all()
    probes = session.exec(select(ProbeRun).where(ProbeRun.project_id == project_id)).all()

    message_names = set(schema.get("messages", {}).keys())
    transition_messages = {transition.message_type for transition in transitions}
    unused_message_types = sorted(message_names - transition_messages)

    state_degree: dict[str, dict[str, int]] = {
        state.name: {"incoming": 0, "outgoing": 0}
        for state in states
    }
    for transition in transitions:
        if transition.from_state in state_degree:
            state_degree[transition.from_state]["outgoing"] += 1
        if transition.to_state in state_degree:
            state_degree[transition.to_state]["incoming"] += 1

    isolated_states = [
        {
            "state": state_name,
            "incoming": degree["incoming"],
            "outgoing": degree["outgoing"],
        }
        for state_name, degree in state_degree.items()
        if (state_name != "INIT" and degree["incoming"] == 0) or (state_name != "CLOSED" and degree["outgoing"] == 0)
    ]

    weak_transitions = [
        {
            "description": f"{transition.from_state} -> {transition.to_state} via {transition.message_type}",
            "status": transition.status,
            "confidence": round(transition.confidence, 3),
        }
        for transition in sorted(transitions, key=lambda item: item.confidence)
        if transition.status != "supported" or transition.confidence < 0.9
    ]

    supported_transitions = sum(1 for transition in transitions if transition.status == "supported")
    supported_ratio = supported_transitions / len(transitions) if transitions else 0.0
    probe_ratio = len(probes) / len(transitions) if transitions else 0.0

    recommended_actions = []
    if supported_ratio > 0.8 and probe_ratio < 0.5:
        recommended_actions.append(
            "Current model appears over-confirmed relative to probe coverage; keep low-confidence transitions as hypothesis until probe or repeated trace evidence strengthens them."
        )
    if unused_message_types:
        recommended_actions.append(
            "Several observed message types are not yet represented in the state machine; prioritize seeds and probes for: "
            + ", ".join(unused_message_types[:8])
        )
    if isolated_states:
        recommended_actions.append(
            "Some inferred states are weakly connected in the current model; add directed seeds for: "
            + ", ".join(item["state"] for item in isolated_states[:5])
        )
    if not probes:
        recommended_actions.append(
            "No probes were executed; schedule online validation for authentication, directory traversal, and rename flows."
        )
    if not recommended_actions:
        recommended_actions.append(
            "Next iteration should emphasize broader data-channel and post-auth file-operation seeds to improve message-to-transition coverage."
        )

    priority_order = ["PASS", "LIST", "RETR", "STOR", "PASV", "EPSV", "PORT", "EPRT", "RNFR", "RNTO", "REIN", "MLSD", "MLST", "APPE"]
    focus_commands = [message for message in priority_order if message in unused_message_types]
    if len(focus_commands) < 6:
        for item in weak_transitions:
            message_type = item["description"].split(" via ")[-1]
            if message_type not in focus_commands:
                focus_commands.append(message_type)
            if len(focus_commands) >= 6:
                break

    suggested_campaign = {
        "target": "ftp-local",
        "seed_strategy": "state_progression_then_file_ops",
        "num_generated_seeds": seed_corpus.get("seed_count", 0),
        "focus_commands": focus_commands[:6],
        "duration_minutes": 30,
        "objective": "Increase post-auth and data-channel coverage while validating weaker transitions.",
    }

    return {
        "project_id": project_id,
        "unused_message_types": unused_message_types,
        "isolated_states": isolated_states,
        "weak_transitions": weak_transitions[:10],
        "supported_ratio": round(supported_ratio, 3),
        "probe_to_transition_ratio": round(probe_ratio, 3),
        "generated_seed_count": seed_corpus.get("seed_count", 0),
        "recommended_actions": recommended_actions,
        "suggested_campaign": suggested_campaign,
        "fuzzing_observation": {
            "likely_stall_point": "authentication_or_post_auth_gap" if unused_message_types else "probe_validation_gap",
            "explanation": recommended_actions[0],
        },
    }
