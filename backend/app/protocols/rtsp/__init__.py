"""RTSP-specific protocol adapter with dedicated parser and probe executor."""
from __future__ import annotations

import re
import socket
from pathlib import Path

from ..generic_text_adapter import GenericTextProtocolAdapter
from ...core.config import settings


_RTSP_METHODS = frozenset([
    "OPTIONS", "DESCRIBE", "ANNOUNCE", "SETUP", "PLAY",
    "PAUSE", "RECORD", "REDIRECT", "TEARDOWN",
    "GET_PARAMETER", "SET_PARAMETER",
])

_RTSP_STATUS_RE = re.compile(r"^RTSP/[\d.]+\s+(\d{3})\s+(.*)")
_RTSP_REQUEST_RE = re.compile(r"^([A-Z_]+)\s+(rtsp://[^\s]+|[^\s]+)\s+RTSP/[\d.]+")
_CSEQ_RE = re.compile(r"^CSeq:\s*(\d+)", re.IGNORECASE)
_SESSION_RE = re.compile(r"^Session:\s*([^\s;]+)", re.IGNORECASE)


class RTSPProtocolAdapter(GenericTextProtocolAdapter):
    """RTSP-specific adapter with header-aware parser and live probe."""

    def __init__(self) -> None:
        super().__init__(
            name="RTSP",
            display_name="Real Time Streaming Protocol",
            default_port=554,
        )

    # ------------------------------------------------------------------
    # Parser
    # ------------------------------------------------------------------

    def parse_session(self, raw_text: str) -> list[dict]:
        """Parse an RTSP session log.

        Each request block ends at the next blank line / next RTSP message.
        Headers are extracted (CSeq, Session, Transport, Range).
        Server responses are paired with the preceding request.
        """
        events: list[dict] = []
        lines = raw_text.splitlines()
        i = 0
        pending_event: dict | None = None

        while i < len(lines):
            line = lines[i]
            i += 1

            if not line.strip():
                continue

            # Server response line
            m_resp = _RTSP_STATUS_RE.match(line)
            if m_resp:
                code = m_resp.group(1)
                reason = m_resp.group(2)[:100]
                if pending_event is not None:
                    pending_event["response"] = {"code": code, "text": reason}
                    pending_event = None
                continue

            # Request line
            m_req = _RTSP_REQUEST_RE.match(line)
            if m_req:
                method = m_req.group(1).upper()
                uri = m_req.group(2)
                fields: dict = {"uri": uri}

                # Read headers until blank line
                while i < len(lines) and lines[i].strip():
                    hdr = lines[i]
                    i += 1
                    m_cseq = _CSEQ_RE.match(hdr)
                    if m_cseq:
                        fields["cseq"] = m_cseq.group(1)
                        continue
                    m_sess = _SESSION_RE.match(hdr)
                    if m_sess:
                        fields["session"] = m_sess.group(1)
                        continue
                    if hdr.lower().startswith("transport:"):
                        fields["transport"] = hdr.split(":", 1)[1].strip()[:100]
                    elif hdr.lower().startswith("range:"):
                        fields["range"] = hdr.split(":", 1)[1].strip()

                ev = {"message_type": method, "fields": fields}
                events.append(ev)
                pending_event = ev
                continue

        return events

    # ------------------------------------------------------------------
    # State inference
    # ------------------------------------------------------------------

    def infer_candidate_states(self, sessions: list[list[dict]]) -> dict:
        return {
            "states": [
                {"name": "INIT", "description": "No session established"},
                {"name": "DESCRIBED", "description": "DESCRIBE completed, SDP received"},
                {"name": "READY", "description": "SETUP completed, resources allocated"},
                {"name": "PLAYING", "description": "PLAY active, media streaming"},
                {"name": "PAUSED", "description": "PAUSE issued, session held"},
                {"name": "RECORDING", "description": "RECORD active"},
                {"name": "CLOSED", "description": "TEARDOWN completed"},
            ]
        }

    def propose_transitions(self, states: list[dict], messages: list[dict]) -> dict:
        transitions = [
            {"from_state": "INIT", "to_state": "INIT", "message_type": "OPTIONS", "confidence": 0.90},
            {"from_state": "INIT", "to_state": "DESCRIBED", "message_type": "DESCRIBE", "confidence": 0.90},
            {"from_state": "DESCRIBED", "to_state": "READY", "message_type": "SETUP", "confidence": 0.90},
            {"from_state": "READY", "to_state": "PLAYING", "message_type": "PLAY", "confidence": 0.92},
            {"from_state": "PLAYING", "to_state": "PAUSED", "message_type": "PAUSE", "confidence": 0.88},
            {"from_state": "PAUSED", "to_state": "PLAYING", "message_type": "PLAY", "confidence": 0.85},
            {"from_state": "PLAYING", "to_state": "CLOSED", "message_type": "TEARDOWN", "confidence": 0.90},
            {"from_state": "READY", "to_state": "CLOSED", "message_type": "TEARDOWN", "confidence": 0.88},
            {"from_state": "READY", "to_state": "RECORDING", "message_type": "RECORD", "confidence": 0.70},
            {"from_state": "RECORDING", "to_state": "CLOSED", "message_type": "TEARDOWN", "confidence": 0.85},
            {"from_state": "PLAYING", "to_state": "PLAYING", "message_type": "GET_PARAMETER", "confidence": 0.75},
            {"from_state": "PLAYING", "to_state": "PLAYING", "message_type": "SET_PARAMETER", "confidence": 0.70},
            {"from_state": "INIT", "to_state": "READY", "message_type": "SETUP", "confidence": 0.70},
        ]
        return {"transitions": transitions}

    def trace_augmentation_min_transitions(self) -> int:
        return 10

    def trace_augmentation_priority_messages(self) -> list[str]:
        return ["OPTIONS", "DESCRIBE", "SETUP", "PLAY", "PAUSE", "TEARDOWN", "GET_PARAMETER", "RECORD"]

    # ------------------------------------------------------------------
    # Prompts
    # ------------------------------------------------------------------

    def spec_system_prompt(self) -> str:
        return (
            "You are an expert RTSP (RFC 2326/7826) protocol analyst. "
            "Extract all methods, mandatory headers (CSeq, Session, Transport), and state transitions. "
            "Emphasise the OPTIONS→DESCRIBE→SETUP→PLAY→TEARDOWN lifecycle. "
            "Call the provided tool exactly once with comprehensive results."
        )

    def probe_system_prompt(self) -> str:
        return (
            "You are a conservative RTSP probe planner. "
            "Choose probes that test state ordering (e.g. PLAY without SETUP, TEARDOWN from INIT). "
            "Call the tool exactly once."
        )

    # ------------------------------------------------------------------
    # Live probe executor
    # ------------------------------------------------------------------

    def execute_probe(self, commands: list[str]) -> list[dict]:
        host = settings.RTSP_PROBE_HOST
        port = settings.RTSP_PROBE_PORT
        return self._rtsp_exchange(host, port, commands)

    def probe_target_host(self) -> str:
        return settings.RTSP_PROBE_HOST

    def probe_target_port(self) -> int:
        return settings.RTSP_PROBE_PORT
