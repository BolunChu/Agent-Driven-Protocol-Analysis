"""Probe Agent — generates discriminative probes and executes them online."""

from __future__ import annotations
import json
import socket
from sqlmodel import Session, select
from ..models.domain import Transition, Invariant, Evidence, ProbeRun
from ..core.config import settings


def _ftp_exchange(host: str, port: int, commands: list[str], timeout: float = 5.0) -> list[dict]:
    results = []
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        greeting = sock.recv(4096).decode("utf-8", errors="replace").strip()
        results.append({"command": "(connect)", "response": greeting})
        for cmd in commands:
            sock.sendall((cmd + "\r\n").encode("utf-8"))
            response = sock.recv(4096).decode("utf-8", errors="replace").strip()
            results.append({"command": cmd, "response": response})
        sock.sendall(b"QUIT\r\n")
        try:
            final = sock.recv(4096).decode("utf-8", errors="replace").strip()
            results.append({"command": "QUIT", "response": final})
        except Exception:
            pass
        sock.close()
    except Exception as e:
        results.append({"command": "(error)", "response": str(e)})
    return results


def _generate_probe_commands(target: dict) -> list[str]:
    claim = target["claim"]
    if target["type"] == "transition":
        mt = claim.message_type
        if claim.from_state == "INIT" and mt == "USER":
            return ["USER anonymous"]
        elif claim.from_state == "AUTH_PENDING" and mt == "PASS":
            return ["USER anonymous", "PASS anonymous@test.com"]
        elif mt in ("LIST", "PWD", "CWD"):
            return ["USER anonymous", "PASS anonymous@test.com", mt if mt != "CWD" else "CWD /"]
        elif mt == "QUIT":
            return ["QUIT"]
        else:
            return ["USER anonymous", "PASS anonymous@test.com", mt]
    elif target["type"] == "invariant":
        rule = target["claim"].rule_text
        if "PASS" in rule and "USER" in rule:
            return ["PASS testpass"]
        elif "LIST" in rule and "auth" in rule.lower():
            return ["LIST"]
        return ["USER anonymous", "PASS anonymous@test.com"]
    return ["NOOP"]


def run_probe_agent(project_id: int, session: Session) -> dict:
    results = {"agent": "probe", "probes_executed": 0, "model_updates": []}

    transitions = session.exec(select(Transition).where(Transition.project_id == project_id)).all()
    invariants = session.exec(select(Invariant).where(Invariant.project_id == project_id)).all()

    probe_targets = []
    for t in transitions:
        if t.status == "disputed" or t.confidence < 0.5:
            probe_targets.append({"type": "transition", "claim": t,
                                  "description": f"{t.from_state} -> {t.to_state} via {t.message_type}"})
    for inv in invariants:
        if inv.status == "disputed" or inv.confidence < 0.5:
            probe_targets.append({"type": "invariant", "claim": inv, "description": inv.rule_text})

    if not probe_targets:
        for t in transitions:
            if t.status == "hypothesis":
                probe_targets.append({"type": "transition", "claim": t,
                                      "description": f"{t.from_state} -> {t.to_state} via {t.message_type}"})
                if len(probe_targets) >= 3:
                    break

    for target in probe_targets:
        cmds = _generate_probe_commands(target)
        exchange = _ftp_exchange(settings.FTP_PROBE_HOST, settings.FTP_PROBE_PORT, cmds)

        probe_run = ProbeRun(
            project_id=project_id, target_host=settings.FTP_PROBE_HOST,
            target_port=settings.FTP_PROBE_PORT, goal=f"Verify: {target['description']}",
            request_payload=json.dumps(cmds), response_payload=json.dumps(exchange),
            result_summary=f"Executed {len(exchange)} exchanges",
        )
        session.add(probe_run)
        session.commit()
        session.refresh(probe_run)

        update = _apply_probe_result(target, exchange, session, project_id, probe_run.id)
        results["model_updates"].append(update)
        results["probes_executed"] += 1

    session.commit()
    return results


def _apply_probe_result(target, exchange, session, project_id, probe_id):
    update = {"target": target["description"], "action": "no_change"}
    has_error = any("error" in e.get("command", "") for e in exchange)
    if has_error:
        update["action"] = "probe_failed"
        return update

    claim = target["claim"]
    if target["type"] == "transition":
        for ex in exchange:
            cmd = ex.get("command", "")
            resp = ex.get("response", "")
            if cmd.upper().startswith(claim.message_type):
                code = resp[:3] if resp else ""
                if code.startswith(("2", "3")):
                    claim.status = "supported"
                    claim.confidence = min(claim.confidence + 0.15, 1.0)
                    update["action"] = "confirmed"
                elif code.startswith(("4", "5")):
                    claim.status = "disputed"
                    claim.confidence = max(claim.confidence - 0.1, 0.0)
                    update["action"] = "disputed"
                session.add(claim)
    elif target["type"] == "invariant":
        for ex in exchange:
            resp = ex.get("response", "")
            code = resp[:3] if resp else ""
            if code.startswith("5"):
                claim.status = "supported"
                claim.confidence = min(claim.confidence + 0.2, 1.0)
                update["action"] = "invariant_supported"
                session.add(claim)
                break
            elif code.startswith(("2", "3")):
                claim.status = "disputed"
                claim.confidence = max(claim.confidence - 0.2, 0.0)
                update["action"] = "invariant_disputed"
                session.add(claim)
                break

    ev = Evidence(
        project_id=project_id, claim_type=target["type"], claim_id=claim.id,
        source_type="probe", source_ref=f"probe_run:{probe_id}",
        snippet=json.dumps(exchange[-2:] if len(exchange) >= 2 else exchange),
        score=0.9 if "supported" in update["action"] or update["action"] == "confirmed" else 0.5,
    )
    session.add(ev)
    return update
