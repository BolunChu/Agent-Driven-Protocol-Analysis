"""Verifier Agent — performs evidence binding and consistency checking.

Task 7: For conclusions from different sources, bind evidence and compute
confidence/status (hypothesis, supported, disputed).
"""

from __future__ import annotations
import json
from sqlmodel import Session, select

from ..models.domain import Transition, Invariant, Evidence
from ..tools.protocol_tools import score_evidence


def run_verifier(project_id: int, session: Session) -> dict:
    """Run the Verifier Agent to check all transitions and invariants.

    For each claim:
    1. Gather all evidence bound to it
    2. Score the evidence
    3. Update the claim status and confidence
    """
    results = {
        "agent": "verifier",
        "transitions_verified": 0,
        "invariants_verified": 0,
        "status_changes": [],
    }

    # Verify transitions
    transitions = session.exec(
        select(Transition).where(Transition.project_id == project_id)
    ).all()

    for trans in transitions:
        evidence_records = session.exec(
            select(Evidence).where(
                Evidence.project_id == project_id,
                Evidence.claim_type == "transition",
                Evidence.claim_id == trans.id,
            )
        ).all()

        evidence_list = [
            {
                "source_type": e.source_type,
                "snippet": e.snippet,
                "source_ref": e.source_ref,
            }
            for e in evidence_records
        ]

        claim = {
            "type": "transition",
            "description": f"{trans.from_state} -> {trans.to_state} via {trans.message_type}",
        }

        scored = score_evidence(claim, evidence_list)
        old_status = trans.status
        new_status = scored["status"]
        new_confidence = scored["aggregate_confidence"]

        if old_status != new_status or abs(trans.confidence - new_confidence) > 0.01:
            trans.status = new_status
            trans.confidence = new_confidence
            session.add(trans)
            results["status_changes"].append({
                "type": "transition",
                "description": claim["description"],
                "old_status": old_status,
                "new_status": new_status,
                "confidence": new_confidence,
                "evidence_count": len(evidence_list),
            })

        # Update evidence scores
        for i, e in enumerate(evidence_records):
            if i < len(scored["scored_evidence"]):
                e.score = scored["scored_evidence"][i]["score"]
                session.add(e)

        results["transitions_verified"] += 1

    # Verify invariants
    invariants = session.exec(
        select(Invariant).where(Invariant.project_id == project_id)
    ).all()

    for inv in invariants:
        evidence_records = session.exec(
            select(Evidence).where(
                Evidence.project_id == project_id,
                Evidence.claim_type == "invariant",
                Evidence.claim_id == inv.id,
            )
        ).all()

        evidence_list = [
            {
                "source_type": e.source_type,
                "snippet": e.snippet,
                "source_ref": e.source_ref,
            }
            for e in evidence_records
        ]

        claim = {
            "type": "invariant",
            "description": inv.rule_text,
        }

        scored = score_evidence(claim, evidence_list)
        old_status = inv.status
        new_status = scored["status"]
        new_confidence = scored["aggregate_confidence"]

        if old_status != new_status or abs(inv.confidence - new_confidence) > 0.01:
            inv.status = new_status
            inv.confidence = new_confidence
            session.add(inv)
            results["status_changes"].append({
                "type": "invariant",
                "description": inv.rule_text,
                "old_status": old_status,
                "new_status": new_status,
                "confidence": new_confidence,
                "evidence_count": len(evidence_list),
            })

        results["invariants_verified"] += 1

    session.commit()
    return results
