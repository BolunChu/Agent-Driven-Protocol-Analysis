"""FTP protocol parser — converts raw FTP session text into ProtocolEvents.

Supports parsing FTP command/response pairs from text logs or raw session
transcripts. This is the Task 3 implementation for FTP protocol parsing.
"""

from __future__ import annotations
import re
from typing import Any


# FTP command patterns
FTP_COMMAND_RE = re.compile(
    r'^(?P<command>[A-Z]{3,4})(?:\s+(?P<args>.*))?$', re.IGNORECASE
)
FTP_RESPONSE_RE = re.compile(
    r'^(?P<code>\d{3})[\s-](?P<text>.*)$'
)

# Field extraction rules per command
FIELD_EXTRACTORS: dict[str, callable] = {
    "USER": lambda args: {"username": args.strip()},
    "PASS": lambda args: {"password": args.strip()},
    "ACCT": lambda args: {"account": args.strip()},
    "CWD": lambda args: {"directory": args.strip()},
    "XCWD": lambda args: {"directory": args.strip()},
    "RETR": lambda args: {"filename": args.strip()},
    "STOR": lambda args: {"filename": args.strip()},
    "APPE": lambda args: {"filename": args.strip()},
    "DELE": lambda args: {"filename": args.strip()},
    "SIZE": lambda args: {"filename": args.strip()},
    "MKD": lambda args: {"directory": args.strip()},
    "XMKD": lambda args: {"directory": args.strip()},
    "RMD": lambda args: {"directory": args.strip()},
    "XRMD": lambda args: {"directory": args.strip()},
    "RNFR": lambda args: {"filename": args.strip()},
    "RNTO": lambda args: {"filename": args.strip()},
    "TYPE": lambda args: {"transfer_type": args.strip()},
    "MODE": lambda args: {"transfer_mode": args.strip()},
    "STRU": lambda args: {"file_structure": args.strip()},
    "PORT": lambda args: _parse_port_args(args),
    "EPRT": lambda args: _parse_eprt_args(args),
    "PASV": lambda args: {},
    "EPSV": lambda args: {},
    "LIST": lambda args: {"path": args.strip()} if args.strip() else {},
    "NLST": lambda args: {"path": args.strip()} if args.strip() else {},
    "MLST": lambda args: {"path": args.strip()} if args.strip() else {},
    "MLSD": lambda args: {"path": args.strip()} if args.strip() else {},
    "PWD": lambda args: {},
    "XPWD": lambda args: {},
    "CDUP": lambda args: {},
    "XCUP": lambda args: {},
    "REIN": lambda args: {},
    "SMNT": lambda args: {"mount_path": args.strip()} if args.strip() else {},
    "QUIT": lambda args: {},
    "NOOP": lambda args: {},
    "SYST": lambda args: {},
    "FEAT": lambda args: {},
    "HELP": lambda args: {"topic": args.strip()} if args.strip() else {},
    "STAT": lambda args: {"path": args.strip()} if args.strip() else {},
}


def _parse_port_args(args: str) -> dict:
    """Parse PORT command arguments (h1,h2,h3,h4,p1,p2)."""
    parts = args.strip().split(",")
    if len(parts) == 6:
        host = ".".join(parts[:4])
        port = int(parts[4]) * 256 + int(parts[5])
        return {"host": host, "port": port}
    return {"raw_args": args.strip()}


def _parse_eprt_args(args: str) -> dict:
    value = args.strip()
    parts = value.split("|")
    if len(parts) >= 5:
        try:
            return {
                "protocol": parts[1],
                "host": parts[2],
                "port": int(parts[3]),
            }
        except ValueError:
            return {"raw_args": value}
    return {"raw_args": value}


def parse_ftp_command(line: str) -> dict | None:
    """Parse a single FTP command line.

    Returns:
        {"message_type": "USER", "args": "anonymous", "fields": {"username": "anonymous"}}
        or None if the line is not a valid FTP command.
    """
    line = line.strip()
    if not line:
        return None

    m = FTP_COMMAND_RE.match(line)
    if not m:
        return None

    cmd = m.group("command").upper()
    args = (m.group("args") or "").strip()
    extractor = FIELD_EXTRACTORS.get(cmd, lambda a: {"args": a} if a else {})
    fields = extractor(args)

    return {
        "message_type": cmd,
        "args": args,
        "fields": fields,
    }


def parse_ftp_response(line: str) -> dict | None:
    """Parse a single FTP response line.

    Returns:
        {"code": "331", "text": "User name okay, need password."}
        or None if the line is not a valid FTP response.
    """
    line = line.strip()
    if not line:
        return None

    m = FTP_RESPONSE_RE.match(line)
    if not m:
        return None

    return {
        "code": m.group("code"),
        "text": m.group("text").strip(),
    }


def parse_ftp_session(raw_text: str) -> list[dict]:
    """Parse a complete FTP session transcript into a list of protocol events.

    Expects a text format where client commands and server responses alternate.
    Lines starting with '>' or 'C:' are client commands.
    Lines starting with '<' or 'S:' are server responses.
    Lines starting with a 3-digit code are also treated as server responses.

    Returns:
        List of ProtocolEvent dicts:
        [
            {
                "direction": "client_to_server",
                "raw": "USER anonymous",
                "message_type": "USER",
                "fields": {"username": "anonymous"},
                "response": {"code": "331", "text": "User name okay, need password."}
            },
            ...
        ]
    """
    events = []
    lines = raw_text.strip().split("\n")
    current_command = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Detect direction
        is_client = False
        is_server = False
        clean_line = line

        if line.startswith(">") or line.upper().startswith("C:"):
            is_client = True
            clean_line = re.sub(r'^[>]\s*|^C:\s*', '', line).strip()
        elif line.startswith("<") or line.upper().startswith("S:"):
            is_server = True
            clean_line = re.sub(r'^[<]\s*|^S:\s*', '', line).strip()
        elif FTP_RESPONSE_RE.match(line):
            is_server = True
            clean_line = line
        elif FTP_COMMAND_RE.match(line):
            is_client = True
            clean_line = line

        if is_client:
            # If there's a pending command without response, save it
            if current_command:
                events.append(current_command)

            parsed = parse_ftp_command(clean_line)
            if parsed:
                current_command = {
                    "direction": "client_to_server",
                    "raw": clean_line,
                    "message_type": parsed["message_type"],
                    "fields": parsed["fields"],
                    "response": None,
                }
            else:
                current_command = {
                    "direction": "client_to_server",
                    "raw": clean_line,
                    "message_type": "UNKNOWN",
                    "fields": {},
                    "response": None,
                }

        elif is_server:
            resp = parse_ftp_response(clean_line)
            if resp and current_command:
                current_command["response"] = resp
                events.append(current_command)
                current_command = None
            elif resp:
                # Server greeting or standalone response
                events.append({
                    "direction": "server_to_client",
                    "raw": clean_line,
                    "message_type": f"RESP_{resp['code']}",
                    "fields": {},
                    "response": resp,
                })

    # Don't forget the last command if it has no response
    if current_command:
        events.append(current_command)

    return events


def parse_ftp_session_pairs(raw_text: str) -> list[dict]:
    """Parse FTP session where commands and responses are on consecutive lines.

    Format: Each command line is followed by its response line.
    Example:
        USER anonymous
        331 User name okay, need password.
        PASS test@example.com
        230 User logged in, proceed.
    """
    events = []
    lines = [l.strip() for l in raw_text.strip().split("\n") if l.strip()]

    i = 0
    while i < len(lines):
        cmd_parsed = parse_ftp_command(lines[i])
        if cmd_parsed:
            event = {
                "direction": "client_to_server",
                "raw": lines[i],
                "message_type": cmd_parsed["message_type"],
                "fields": cmd_parsed["fields"],
                "response": None,
            }
            # Check if next line is a response
            if i + 1 < len(lines):
                resp = parse_ftp_response(lines[i + 1])
                if resp:
                    event["response"] = resp
                    i += 1
            events.append(event)
        else:
            # Might be a server greeting
            resp = parse_ftp_response(lines[i])
            if resp:
                events.append({
                    "direction": "server_to_client",
                    "raw": lines[i],
                    "message_type": f"RESP_{resp['code']}",
                    "fields": {},
                    "response": resp,
                })
        i += 1

    return events
