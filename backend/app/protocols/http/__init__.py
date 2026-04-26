"""HTTP/1.1-specific protocol adapter with dedicated parser and probe executor."""
from __future__ import annotations

import re
import socket
from pathlib import Path

from ..generic_text_adapter import GenericTextProtocolAdapter
from ...core.config import settings


_HTTP_METHODS = frozenset([
    "GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS",
    "PATCH", "CONNECT", "TRACE",
])

_HTTP_REQUEST_RE = re.compile(
    r"^(GET|POST|PUT|DELETE|HEAD|OPTIONS|PATCH|CONNECT|TRACE)\s+(\S+)\s+HTTP/([\d.]+)",
    re.IGNORECASE,
)
_HTTP_RESPONSE_RE = re.compile(r"^HTTP/([\d.]+)\s+(\d{3})\s+(.*)")
_HEADER_RE = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)")


class HTTPProtocolAdapter(GenericTextProtocolAdapter):
    """HTTP/1.1-specific adapter: request-line parser, header extraction, live probe."""

    def __init__(self) -> None:
        super().__init__(
            name="HTTP",
            display_name="Hypertext Transfer Protocol",
            default_port=80,
        )

    # ------------------------------------------------------------------
    # Parser
    # ------------------------------------------------------------------

    def parse_session(self, raw_text: str) -> list[dict]:
        """Parse an HTTP/1.1 session log.

        Extracts request method, path, version, selected headers (Host,
        Content-Type, Content-Length, Authorization, Location) and response code.
        """
        events: list[dict] = []
        lines = raw_text.splitlines()
        i = 0
        pending_event: dict | None = None

        while i < len(lines):
            line = lines[i]
            i += 1

            if not line.strip():
                # Blank line – end of headers block
                pending_event = None
                continue

            # Response status line
            m_resp = _HTTP_RESPONSE_RE.match(line)
            if m_resp:
                code = m_resp.group(2)
                reason = m_resp.group(3)[:80]
                if events:
                    events[-1]["response"] = {"code": code, "text": reason}
                    pending_event = None
                # Read response headers (we just skip them, logging Location)
                while i < len(lines) and lines[i].strip():
                    hdr = lines[i]
                    i += 1
                    if events:
                        m_hdr = _HEADER_RE.match(hdr)
                        if m_hdr:
                            name_lower = m_hdr.group(1).lower()
                            if name_lower == "location":
                                events[-1].setdefault("response", {})["location"] = m_hdr.group(2)
                continue

            # Request line
            m_req = _HTTP_REQUEST_RE.match(line)
            if m_req:
                method = m_req.group(1).upper()
                path = m_req.group(2)
                version = m_req.group(3)
                fields: dict = {"path": path, "version": version}

                # Consume request headers
                while i < len(lines) and lines[i].strip():
                    hdr = lines[i]
                    i += 1
                    m_hdr = _HEADER_RE.match(hdr)
                    if not m_hdr:
                        continue
                    hname = m_hdr.group(1).lower()
                    hval = m_hdr.group(2)
                    if hname == "host":
                        fields["host"] = hval
                    elif hname == "content-type":
                        fields["content_type"] = hval
                    elif hname == "content-length":
                        fields["content_length"] = hval
                    elif hname == "authorization":
                        fields["authorization"] = hval[:30] + "..."
                    elif hname == "connection":
                        fields["connection"] = hval

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
                {"name": "INIT", "description": "No TCP connection"},
                {"name": "CONNECTED", "description": "TCP connection established"},
                {"name": "REQUEST_SENT", "description": "Request awaiting response"},
                {"name": "RESPONSE_RECEIVED", "description": "Response received; keep-alive"},
                {"name": "AUTH_REQUIRED", "description": "401 received, credentials needed"},
                {"name": "REDIRECT", "description": "3xx redirect received"},
                {"name": "ERROR", "description": "4xx/5xx error received"},
                {"name": "CLOSED", "description": "Connection closed"},
            ]
        }

    def propose_transitions(self, states: list[dict], messages: list[dict]) -> dict:
        transitions = [
            {"from_state": "INIT", "to_state": "CONNECTED", "message_type": "TCP_CONNECT", "confidence": 0.95},
            {"from_state": "CONNECTED", "to_state": "REQUEST_SENT", "message_type": "GET", "confidence": 0.95},
            {"from_state": "CONNECTED", "to_state": "REQUEST_SENT", "message_type": "POST", "confidence": 0.90},
            {"from_state": "CONNECTED", "to_state": "REQUEST_SENT", "message_type": "PUT", "confidence": 0.85},
            {"from_state": "CONNECTED", "to_state": "REQUEST_SENT", "message_type": "DELETE", "confidence": 0.85},
            {"from_state": "CONNECTED", "to_state": "REQUEST_SENT", "message_type": "HEAD", "confidence": 0.80},
            {"from_state": "CONNECTED", "to_state": "REQUEST_SENT", "message_type": "OPTIONS", "confidence": 0.80},
            {"from_state": "CONNECTED", "to_state": "REQUEST_SENT", "message_type": "PATCH", "confidence": 0.75},
            {"from_state": "RESPONSE_RECEIVED", "to_state": "REQUEST_SENT", "message_type": "GET", "confidence": 0.90},
            {"from_state": "RESPONSE_RECEIVED", "to_state": "REQUEST_SENT", "message_type": "POST", "confidence": 0.88},
            {"from_state": "REQUEST_SENT", "to_state": "RESPONSE_RECEIVED", "message_type": "200_OK", "confidence": 0.90},
            {"from_state": "REQUEST_SENT", "to_state": "AUTH_REQUIRED", "message_type": "401_UNAUTHORIZED", "confidence": 0.90},
            {"from_state": "AUTH_REQUIRED", "to_state": "REQUEST_SENT", "message_type": "GET", "confidence": 0.85},
            {"from_state": "REQUEST_SENT", "to_state": "REDIRECT", "message_type": "301_REDIRECT", "confidence": 0.85},
            {"from_state": "REDIRECT", "to_state": "REQUEST_SENT", "message_type": "GET", "confidence": 0.85},
            {"from_state": "REQUEST_SENT", "to_state": "ERROR", "message_type": "404_NOT_FOUND", "confidence": 0.88},
            {"from_state": "REQUEST_SENT", "to_state": "ERROR", "message_type": "500_ERROR", "confidence": 0.85},
            {"from_state": "RESPONSE_RECEIVED", "to_state": "CLOSED", "message_type": "CONNECTION_CLOSE", "confidence": 0.85},
        ]
        return {"transitions": transitions}

    def trace_augmentation_min_transitions(self) -> int:
        return 12

    def trace_augmentation_priority_messages(self) -> list[str]:
        return ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"]

    # ------------------------------------------------------------------
    # Prompts
    # ------------------------------------------------------------------

    def spec_system_prompt(self) -> str:
        return (
            "You are an expert HTTP/1.1 (RFC 7230-7235) protocol analyst. "
            "Extract all request methods, header semantics, status code groups, and state transitions. "
            "Focus on the request-response cycle, authentication (401→retry), and redirects (3xx). "
            "Call the provided tool exactly once with comprehensive results."
        )

    def probe_system_prompt(self) -> str:
        return (
            "You are a conservative HTTP probe planner. "
            "Choose probes that test important state transitions: "
            "e.g. GET without Host header, POST without Content-Length, "
            "DELETE on protected resource without auth. "
            "Call the tool exactly once."
        )

    # ------------------------------------------------------------------
    # Live probe executor
    # ------------------------------------------------------------------

    def execute_probe(self, commands: list[str]) -> list[dict]:
        host = settings.HTTP_PROBE_HOST
        port = settings.HTTP_PROBE_PORT
        return self._http_exchange(host, port, commands)

    def probe_target_host(self) -> str:
        return settings.HTTP_PROBE_HOST

    def probe_target_port(self) -> int:
        return settings.HTTP_PROBE_PORT
