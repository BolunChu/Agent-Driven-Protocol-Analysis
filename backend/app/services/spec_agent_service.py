"""Spec Agent — extracts protocol knowledge from documentation summaries.

Task 5: From protocol document summaries, extract message types, field
semantics, ordering rules, and candidate protocol rules.
"""

from __future__ import annotations
import json
from sqlmodel import Session, select

from ..models.domain import SessionTrace, MessageType, Invariant, Evidence
from ..tools.protocol_tools import extract_message_types, extract_fields_and_constraints
from ..tools.ftp_parser import parse_ftp_session

# FTP spec knowledge base (used when no LLM is available)
FTP_SPEC_KNOWLEDGE = {
    "message_types": [
        {"name": "USER", "template": "USER <username>", "fields": {"username": "string"},
         "description": "Specify the user for authentication"},
        {"name": "PASS", "template": "PASS <password>", "fields": {"password": "string"},
         "description": "Specify the password for authentication"},
        {"name": "QUIT", "template": "QUIT", "fields": {},
         "description": "Terminate the FTP session"},
        {"name": "PWD", "template": "PWD", "fields": {},
         "description": "Print working directory"},
        {"name": "CWD", "template": "CWD <directory>", "fields": {"directory": "string"},
         "description": "Change working directory"},
        {"name": "LIST", "template": "LIST [<path>]", "fields": {"path": "string (optional)"},
         "description": "List files in directory"},
        {"name": "RETR", "template": "RETR <filename>", "fields": {"filename": "string"},
         "description": "Retrieve a file"},
        {"name": "STOR", "template": "STOR <filename>", "fields": {"filename": "string"},
         "description": "Store a file on server"},
        {"name": "DELE", "template": "DELE <filename>", "fields": {"filename": "string"},
         "description": "Delete a file"},
        {"name": "TYPE", "template": "TYPE <type>", "fields": {"transfer_type": "A|I"},
         "description": "Set transfer type (ASCII/Binary)"},
        {"name": "PASV", "template": "PASV", "fields": {},
         "description": "Enter passive mode"},
        {"name": "PORT", "template": "PORT <h1,h2,h3,h4,p1,p2>", "fields": {"host": "string", "port": "int"},
         "description": "Specify data connection port"},
        {"name": "SYST", "template": "SYST", "fields": {},
         "description": "Query system type"},
        {"name": "FEAT", "template": "FEAT", "fields": {},
         "description": "List supported features"},
        {"name": "NOOP", "template": "NOOP", "fields": {},
         "description": "No operation / keep alive"},
    ],
    "ordering_rules": [
        "PASS must appear after USER",
        "LIST, RETR, STOR require prior successful authentication (USER + PASS)",
        "QUIT can be sent from any state",
        "Data commands (LIST, RETR, STOR) typically require PASV or PORT first",
    ],
}


def run_spec_agent(project_id: int, session: Session) -> dict:
    """Run the Spec Agent to extract protocol knowledge from doc sources.

    Looks at all doc-type SessionTraces, tries to parse them, then
    creates MessageType and Invariant records with evidence bindings.
    """
    # Gather doc sources
    docs = session.exec(
        select(SessionTrace).where(
            SessionTrace.project_id == project_id,
            SessionTrace.source_type == "doc",
        )
    ).all()

    # Extract knowledge from docs + built-in FTP spec
    created_message_types = []
    created_invariants = []

    # Use built-in FTP knowledge as baseline
    for mt_info in FTP_SPEC_KNOWLEDGE["message_types"]:
        # Check if already exists
        existing = session.exec(
            select(MessageType).where(
                MessageType.project_id == project_id,
                MessageType.name == mt_info["name"],
            )
        ).first()

        if not existing:
            mt = MessageType(
                project_id=project_id,
                name=mt_info["name"],
                template=mt_info["template"],
                fields_json=json.dumps(mt_info["fields"]),
                confidence=0.7,  # from spec, moderate confidence
            )
            session.add(mt)
            session.commit()
            session.refresh(mt)
            created_message_types.append(mt.name)

            # Create evidence binding
            ev = Evidence(
                project_id=project_id,
                claim_type="message_type",
                claim_id=mt.id,
                source_type="doc",
                source_ref="FTP RFC 959 spec summary",
                snippet=f"{mt_info['name']}: {mt_info['description']}",
                score=0.7,
            )
            session.add(ev)

    # Create ordering invariants
    for rule in FTP_SPEC_KNOWLEDGE["ordering_rules"]:
        existing = session.exec(
            select(Invariant).where(
                Invariant.project_id == project_id,
                Invariant.rule_text == rule,
            )
        ).first()

        if not existing:
            inv = Invariant(
                project_id=project_id,
                rule_text=rule,
                rule_type="ordering",
                confidence=0.7,
                status="hypothesis",
            )
            session.add(inv)
            session.commit()
            session.refresh(inv)
            created_invariants.append(rule)

            ev = Evidence(
                project_id=project_id,
                claim_type="invariant",
                claim_id=inv.id,
                source_type="doc",
                source_ref="FTP RFC 959 spec summary",
                snippet=rule,
                score=0.7,
            )
            session.add(ev)

    # Also parse any doc text for additional message types
    for doc in docs:
        try:
            events = parse_ftp_session(doc.raw_content)
            if events:
                result = extract_message_types(events)
                for mt_info in result.get("message_types", []):
                    existing = session.exec(
                        select(MessageType).where(
                            MessageType.project_id == project_id,
                            MessageType.name == mt_info["name"],
                        )
                    ).first()
                    if not existing:
                        mt = MessageType(
                            project_id=project_id,
                            name=mt_info["name"],
                            template="",
                            fields_json="{}",
                            confidence=0.5,
                        )
                        session.add(mt)
                        created_message_types.append(mt_info["name"])
                # Update parsed content
                doc.parsed_content = json.dumps(events, ensure_ascii=False)
                session.add(doc)
        except Exception:
            pass

    session.commit()

    return {
        "agent": "spec",
        "message_types_created": created_message_types,
        "invariants_created": created_invariants,
        "docs_processed": len(docs),
    }
