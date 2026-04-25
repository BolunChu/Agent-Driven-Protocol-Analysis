"""Verifier Agent — performs evidence binding and consistency checking.

Task 7: For conclusions from different sources, bind evidence and compute
confidence/status (hypothesis, supported, disputed).
"""

from __future__ import annotations
import logging
from sqlmodel import Session, select

from ..models.domain import Transition, Invariant, Evidence
from ..tools.protocol_tools import score_evidence
from ..core.llm_client import call_with_tools

logger = logging.getLogger(__name__)


VERIFY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "record_verification_review",
            "description": "Record verification decisions for transitions and invariants in one batch.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transition_reviews": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "suggested_status": {"type": "string", "enum": ["hypothesis", "supported", "disputed"]},
                                "confidence": {"type": "number"},
                                "rationale": {"type": "string"},
                            },
                            "required": ["description", "suggested_status", "confidence", "rationale"],
                        },
                    },
                    "invariant_reviews": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "suggested_status": {"type": "string", "enum": ["hypothesis", "supported", "disputed"]},
                                "confidence": {"type": "number"},
                                "rationale": {"type": "string"},
                            },
                            "required": ["description", "suggested_status", "confidence", "rationale"],
                        },
                    },
                },
                "required": ["transition_reviews", "invariant_reviews"],
            },
        },
    }
]

VERIFY_SYSTEM_PROMPT = """You are a conservative protocol-verification analyst.

Review the provided claims and their evidence, then call the tool exactly once.

Guidelines:
- Prefer supported only when the claim is directly evidenced by trace or probe behavior
- Use disputed when the evidence clearly contradicts the claim or shows invalid sequencing
- Use hypothesis when evidence is sparse or indirect
- Be conservative with confidence values
- Keep the description strings exactly unchanged so they can be matched back to claims"""


def _llm_review_claims(transition_claims: list[dict], invariant_claims: list[dict]) -> dict:
    user_message = """## Transition Claims

"""
    for claim in transition_claims:
        user_message += f"- description: {claim['description']}\n"
        user_message += f"  heuristic_status: {claim['heuristic_status']}\n"
        user_message += f"  heuristic_confidence: {claim['heuristic_confidence']}\n"
        user_message += f"  evidence:\n{claim['evidence_text']}\n"

    user_message += "\n## Invariant Claims\n\n"
    for claim in invariant_claims:
        user_message += f"- description: {claim['description']}\n"
        user_message += f"  heuristic_status: {claim['heuristic_status']}\n"
        user_message += f"  heuristic_confidence: {claim['heuristic_confidence']}\n"
        user_message += f"  evidence:\n{claim['evidence_text']}\n"

    try:
        tool_calls = call_with_tools(
            system_prompt=VERIFY_SYSTEM_PROMPT,
            user_message=user_message,
            tools=VERIFY_TOOLS,
            max_iterations=1,
        )
    except Exception as exc:
        logger.warning("Verifier LLM review failed, falling back to heuristic scoring: %s", exc)
        return {"transition_reviews": [], "invariant_reviews": []}
    if tool_calls and tool_calls[0]["tool"] == "record_verification_review":
        return tool_calls[0]["args"]
    return {"transition_reviews": [], "invariant_reviews": []}


def _merge_status(heuristic_status: str, heuristic_confidence: float,
                  llm_status: str | None, llm_confidence: float | None) -> tuple[str, float]:
    if not llm_status or llm_confidence is None:
        return heuristic_status, heuristic_confidence
    if heuristic_status == "disputed" or llm_status == "disputed":
        return "disputed", round(min(heuristic_confidence, llm_confidence), 3)
    if heuristic_status == "supported" or llm_status == "supported":
        return "supported", round(max(heuristic_confidence, llm_confidence), 3)
    return "hypothesis", round(max(heuristic_confidence, llm_confidence), 3)


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

    transition_reviews_input: list[dict] = []
    invariant_reviews_input: list[dict] = []
    transition_context: dict[int, dict] = {}
    invariant_context: dict[int, dict] = {}

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
        transition_context[trans.id] = {
            "trans": trans,
            "claim": claim,
            "scored": scored,
            "evidence_records": evidence_records,
            "evidence_list": evidence_list,
        }
        evidence_text = "\n".join(
            f"    - [{e['source_type']}] {e['source_ref']}: {e['snippet'][:240]}" for e in evidence_list
        ) or "    - (no evidence)"
        transition_reviews_input.append({
            "description": claim["description"],
            "heuristic_status": scored["status"],
            "heuristic_confidence": scored["aggregate_confidence"],
            "evidence_text": evidence_text,
        })

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
        invariant_context[inv.id] = {
            "inv": inv,
            "claim": claim,
            "scored": scored,
            "evidence_records": evidence_records,
            "evidence_list": evidence_list,
        }
        evidence_text = "\n".join(
            f"    - [{e['source_type']}] {e['source_ref']}: {e['snippet'][:240]}" for e in evidence_list
        ) or "    - (no evidence)"
        invariant_reviews_input.append({
            "description": claim["description"],
            "heuristic_status": scored["status"],
            "heuristic_confidence": scored["aggregate_confidence"],
            "evidence_text": evidence_text,
        })

    llm_payload = _llm_review_claims(transition_reviews_input, invariant_reviews_input)
    transition_review_map = {
        item["description"]: item for item in llm_payload.get("transition_reviews", [])
    }
    invariant_review_map = {
        item["description"]: item for item in llm_payload.get("invariant_reviews", [])
    }

    for context in transition_context.values():
        trans = context["trans"]
        claim = context["claim"]
        scored = context["scored"]
        evidence_records = context["evidence_records"]
        evidence_list = context["evidence_list"]
        review = transition_review_map.get(claim["description"], {})
        old_status = trans.status
        new_status, new_confidence = _merge_status(
            scored["status"],
            scored["aggregate_confidence"],
            review.get("suggested_status"),
            review.get("confidence"),
        )

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
                "rationale": review.get("rationale", ""),
            })

        for i, e in enumerate(evidence_records):
            if i < len(scored["scored_evidence"]):
                e.score = scored["scored_evidence"][i]["score"]
                session.add(e)

        results["transitions_verified"] += 1

    for context in invariant_context.values():
        inv = context["inv"]
        claim = context["claim"]
        scored = context["scored"]
        evidence_list = context["evidence_list"]
        review = invariant_review_map.get(claim["description"], {})
        old_status = inv.status
        new_status, new_confidence = _merge_status(
            scored["status"],
            scored["aggregate_confidence"],
            review.get("suggested_status"),
            review.get("confidence"),
        )

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
                "rationale": review.get("rationale", ""),
            })

        results["invariants_verified"] += 1

    session.commit()
    return results
