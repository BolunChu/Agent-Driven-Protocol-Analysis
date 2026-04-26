"""Multi-protocol comparison runner.

Runs the full analysis pipeline for each of FTP, SMTP, RTSP, HTTP in sequence
and writes a unified comparison report to data/outputs/multi_protocol_comparison.json.

Usage:
    python3 scripts/compare_protocols.py [PROTOCOL1 PROTOCOL2 ...]

    # Run all four
    python3 scripts/compare_protocols.py

    # Run specific subset
    python3 scripts/compare_protocols.py FTP SMTP
"""
from __future__ import annotations

import json
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlmodel import Session
from app.core.database import engine, create_db_and_tables
from app.models.domain import (
    ProtocolProject, SessionTrace, MessageType, ProtocolState,
    Transition, Invariant, Evidence, ProbeRun,
)
from app.protocols.registry import get_protocol_adapter
from app.services.spec_agent_service import run_spec_agent
from app.services.trace_agent_service import run_trace_agent
from app.services.verifier_service import run_verifier
from app.services.probe_service import run_probe_agent
from app.services.artifact_service import (
    analyze_iteration_feedback, build_protocol_schema, generate_seed_corpus,
)
from sqlmodel import select

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("compare_protocols")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "data" / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

ALL_PROTOCOLS = ["FTP", "SMTP", "RTSP", "HTTP"]


# ---------------------------------------------------------------------------
# Per-protocol pipeline
# ---------------------------------------------------------------------------

def _run_protocol(protocol: str, db: Session) -> dict:
    adapter = get_protocol_adapter(protocol)
    metadata = adapter.create_project_metadata()

    # Create project
    project = ProtocolProject(
        name=f"{metadata['name_prefix']} [compare] {datetime.now().strftime('%H%M%S')}",
        protocol_name=protocol,
        description=metadata["description"],
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    pid = project.id
    logger.info("[%s] Created project id=%d", protocol, pid)

    # Import data
    import_stats: dict = {"doc": 0, "trace": 0, "seeds": 0}
    for content in adapter.load_doc_inputs(str(PROJECT_ROOT)):
        db.add(SessionTrace(project_id=pid, source_type="doc", raw_content=content))
        import_stats["doc"] += 1
    for content in adapter.load_trace_inputs(str(PROJECT_ROOT)):
        db.add(SessionTrace(project_id=pid, source_type="trace", raw_content=content))
        import_stats["trace"] += 1
    for content in adapter.load_seed_inputs(str(PROJECT_ROOT)):
        db.add(SessionTrace(project_id=pid, source_type="trace", raw_content=content))
        import_stats["seeds"] += 1
    db.commit()
    logger.info("[%s] Imported: %s", protocol, import_stats)

    # Pipeline — no fallback; errors propagate and abort this protocol's run
    spec_r = run_spec_agent(pid, db)
    trace_r = run_trace_agent(pid, db)
    db.expire_all()
    verif_r = run_verifier(pid, db)
    probe_r = run_probe_agent(pid, db)
    schema = build_protocol_schema(pid, db)
    seeds_out = generate_seed_corpus(pid, db, schema)
    feedback = analyze_iteration_feedback(pid, db, schema, seeds_out)


    # Collect metrics
    msg_types = db.exec(select(MessageType).where(MessageType.project_id == pid)).all()
    states = db.exec(select(ProtocolState).where(ProtocolState.project_id == pid)).all()
    transitions = db.exec(select(Transition).where(Transition.project_id == pid)).all()
    invariants = db.exec(select(Invariant).where(Invariant.project_id == pid)).all()
    evidence = db.exec(select(Evidence).where(Evidence.project_id == pid)).all()
    probes = db.exec(select(ProbeRun).where(ProbeRun.project_id == pid)).all()

    t_dist = {"hypothesis": 0, "supported": 0, "disputed": 0}
    for t in transitions:
        t_dist[t.status] = t_dist.get(t.status, 0) + 1

    # Provenance
    agent_trans = fallback_trans = 0
    for ev in evidence:
        if ev.claim_type != "transition":
            continue
        ref = (ev.source_ref or "").lower()
        if "fallback" in ref or "heuristic" in ref:
            fallback_trans += 1
        elif "llm" in ref:
            agent_trans += 1

    result = {
        "protocol": protocol,
        "project_id": pid,
        "timestamp": datetime.utcnow().isoformat(),
        "import_stats": import_stats,
        "metrics": {
            "message_types": len(msg_types),
            "states": len(states),
            "transitions": len(transitions),
            "invariants": len(invariants),
            "evidence_records": len(evidence),
            "probe_runs": len(probes),
        },
        "transition_status": t_dist,
        "agent_path": {
            "spec_fallback": spec_r.get("fallback_used", False),
            "trace_fallback": trace_r.get("fallback_used", False),
            "spec_llm_calls": spec_r.get("llm_tool_calls", 0),
            "trace_llm_calls": trace_r.get("llm_tool_calls", 0),
            "probe_llm_calls": probe_r.get("llm_tool_calls", 0),
            "transition_provenance": {
                "agent": agent_trans,
                "fallback": fallback_trans,
            },
        },
        "artifacts": {
            "schema_message_count": len(schema.get("messages", {})),
            "seed_count": seeds_out.get("seed_count", 0),
            "feedback_actions": len(feedback.get("recommended_actions", [])),
        },
        "message_types_list": [m.name for m in msg_types],
        "states_list": [s.name for s in states],
    }
    logger.info(
        "[%s] Done — msg_types=%d states=%d transitions=%d probes=%d",
        protocol, len(msg_types), len(states), len(transitions), len(probes),
    )
    return result


# ---------------------------------------------------------------------------
# Comparison summary
# ---------------------------------------------------------------------------

def _build_summary(results: list[dict]) -> dict:
    rows = []
    for r in results:
        m = r["metrics"]
        ap = r["agent_path"]
        rows.append({
            "protocol": r["protocol"],
            "message_types": m["message_types"],
            "states": m["states"],
            "transitions": m["transitions"],
            "evidence": m["evidence_records"],
            "probes": m["probe_runs"],
            "supported_transitions": r["transition_status"].get("supported", 0),
            "hypothesis_transitions": r["transition_status"].get("hypothesis", 0),
            "disputed_transitions": r["transition_status"].get("disputed", 0),
            "spec_agent_ok": not ap["spec_fallback"],
            "trace_agent_ok": not ap["trace_fallback"],
            "transition_provenance_agent": ap["transition_provenance"]["agent"],
            "transition_provenance_fallback": ap["transition_provenance"]["fallback"],
            "schema_messages": r["artifacts"]["schema_message_count"],
            "generated_seeds": r["artifacts"]["seed_count"],
        })

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "protocols_run": [r["protocol"] for r in results],
        "comparison_table": rows,
        "per_protocol": {r["protocol"]: r for r in results},
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    protocols = [p.upper() for p in sys.argv[1:]] if len(sys.argv) > 1 else ALL_PROTOCOLS

    logger.info("Starting multi-protocol comparison for: %s", protocols)
    create_db_and_tables()

    results: list[dict] = []
    for proto in protocols:
        logger.info("=" * 60)
        logger.info("Running pipeline for: %s", proto)
        logger.info("=" * 60)
        with Session(engine) as db:
            try:
                r = _run_protocol(proto, db)
                results.append(r)
            except Exception as exc:
                logger.error("[%s] Agent pipeline failed (no fallback): %s", proto, exc)
                sys.exit(1)

    summary = _build_summary(results)
    out_path = OUTPUT_DIR / "multi_protocol_comparison.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    logger.info("Comparison report saved: %s", out_path)

    # Print table
    print("\n" + "=" * 80)
    print("  MULTI-PROTOCOL COMPARISON RESULTS")
    print("=" * 80)
    hdr = f"  {'Protocol':<8} {'MsgTypes':>8} {'States':>6} {'Trans':>6} {'Probes':>6} {'SpecOK':>7} {'TraceOK':>8} {'Agent↑':>7} {'Fall↑':>6}"
    print(hdr)
    print("-" * 80)
    for row in summary["comparison_table"]:
        print(
            f"  {row['protocol']:<8}"
            f" {row['message_types']:>8}"
            f" {row['states']:>6}"
            f" {row['transitions']:>6}"
            f" {row['probes']:>6}"
            f" {'✓' if row['spec_agent_ok'] else '✗':>7}"
            f" {'✓' if row['trace_agent_ok'] else '✗':>8}"
            f" {row['transition_provenance_agent']:>7}"
            f" {row['transition_provenance_fallback']:>6}"
        )
    print("=" * 80)
    print(f"\n  Full report: data/outputs/multi_protocol_comparison.json")


if __name__ == "__main__":
    main()
