"""四协议连续回归测试 — 连跑 N 轮，检测 message types / transitions / fallback 稳定性。

Usage:
    python3 scripts/run_regression.py [--rounds 3] [--protocols FTP SMTP RTSP HTTP]

Output:
    data/outputs/regression_report.json
    Console table: 每轮结果 + 跨轮抖动统计
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev

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
from sqlmodel import select

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("regression")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "data" / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

ALL_PROTOCOLS = ["FTP", "SMTP", "RTSP", "HTTP"]


# ---------------------------------------------------------------------------
# Single-protocol single-round pipeline
# ---------------------------------------------------------------------------

def _run_one(protocol: str, round_num: int, db: Session) -> dict:
    adapter = get_protocol_adapter(protocol)
    metadata = adapter.create_project_metadata()

    project = ProtocolProject(
        name=f"{metadata['name_prefix']} [regr-r{round_num}] {datetime.now().strftime('%H%M%S')}",
        protocol_name=protocol,
        description=metadata["description"],
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    pid = project.id

    for content in adapter.load_doc_inputs(str(PROJECT_ROOT)):
        db.add(SessionTrace(project_id=pid, source_type="doc", raw_content=content))
    for content in adapter.load_trace_inputs(str(PROJECT_ROOT)):
        db.add(SessionTrace(project_id=pid, source_type="trace", raw_content=content))
    for content in adapter.load_seed_inputs(str(PROJECT_ROOT)):
        db.add(SessionTrace(project_id=pid, source_type="trace", raw_content=content))
    db.commit()

    spec_r  = run_spec_agent(pid, db)
    trace_r = run_trace_agent(pid, db)
    db.expire_all()
    run_verifier(pid, db)
    probe_r = run_probe_agent(pid, db)

    msg_types  = db.exec(select(MessageType).where(MessageType.project_id == pid)).all()
    states     = db.exec(select(ProtocolState).where(ProtocolState.project_id == pid)).all()
    transitions = db.exec(select(Transition).where(Transition.project_id == pid)).all()
    evidence   = db.exec(select(Evidence).where(Evidence.project_id == pid)).all()

    # Provenance
    agent_ev   = sum(1 for e in evidence if "llm" in (e.source_ref or "").lower())
    probe_ev   = sum(1 for e in evidence if "probe_run:" in (e.source_ref or "").lower())
    t_supported = sum(1 for t in transitions if t.status == "supported")
    t_hypothesis = sum(1 for t in transitions if t.status == "hypothesis")
    t_disputed  = sum(1 for t in transitions if t.status == "disputed")

    return {
        "protocol": protocol,
        "round": round_num,
        "project_id": pid,
        "message_types": len(msg_types),
        "states": len(states),
        "transitions": len(transitions),
        "evidence_records": len(evidence),
        "probe_runs": len(db.exec(select(ProbeRun).where(ProbeRun.project_id == pid)).all()),
        "spec_fallback": spec_r.get("fallback_used", False),
        "trace_fallback": trace_r.get("fallback_used", False),
        "spec_llm_calls": spec_r.get("llm_tool_calls", 0),
        "trace_llm_calls": trace_r.get("llm_tool_calls", 0),
        "probe_llm_calls": probe_r.get("llm_tool_calls", 0),
        "llm_evidence": agent_ev,
        "probe_evidence": probe_ev,
        "transition_supported": t_supported,
        "transition_hypothesis": t_hypothesis,
        "transition_disputed": t_disputed,
    }


# ---------------------------------------------------------------------------
# Stability analysis
# ---------------------------------------------------------------------------

def _stability(rounds: list[dict], key: str) -> dict:
    vals = [r[key] for r in rounds]
    return {
        "min": min(vals),
        "max": max(vals),
        "mean": round(mean(vals), 2),
        "stdev": round(stdev(vals), 3) if len(vals) > 1 else 0.0,
        "stable": (max(vals) - min(vals)) <= max(1, round(mean(vals) * 0.15)),
    }


def _analyse(protocol: str, rounds: list[dict]) -> dict:
    keys = ["message_types", "states", "transitions", "evidence_records",
            "transition_supported", "transition_hypothesis"]
    return {
        "protocol": protocol,
        "rounds_run": len(rounds),
        "fallback_spikes": sum(1 for r in rounds if r["spec_fallback"] or r["trace_fallback"]),
        "stability": {k: _stability(rounds, k) for k in keys},
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-protocol regression test")
    parser.add_argument("--rounds", type=int, default=3, help="Rounds per protocol (default: 3)")
    parser.add_argument("--protocols", nargs="+", default=ALL_PROTOCOLS,
                        help="Protocols to test (default: all)")
    args = parser.parse_args()

    protocols = [p.upper() for p in args.protocols]
    rounds_n  = args.rounds

    logger.info("Regression: %d rounds × %s", rounds_n, protocols)
    create_db_and_tables()

    all_rounds: dict[str, list[dict]] = {p: [] for p in protocols}

    for proto in protocols:
        for r in range(1, rounds_n + 1):
            logger.info("=== %s  round %d/%d ===", proto, r, rounds_n)
            with Session(engine) as db:
                try:
                    result = _run_one(proto, r, db)
                    all_rounds[proto].append(result)
                    logger.info(
                        "[%s R%d] msg=%d states=%d trans=%d sup=%d hyp=%d disp=%d",
                        proto, r,
                        result["message_types"], result["states"], result["transitions"],
                        result["transition_supported"], result["transition_hypothesis"], result["transition_disputed"],
                    )
                except Exception as exc:
                    logger.error("[%s R%d] FAILED: %s", proto, r, exc)
                    sys.exit(1)

    # Analysis
    analyses = [_analyse(p, all_rounds[p]) for p in protocols if all_rounds[p]]

    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "rounds": rounds_n,
        "protocols": protocols,
        "analyses": {a["protocol"]: a for a in analyses},
        "per_round": {p: all_rounds[p] for p in protocols},
    }

    out_path = OUTPUT_DIR / "regression_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    logger.info("Regression report saved: %s", out_path)

    # Console table
    print("\n" + "=" * 90)
    print("  REGRESSION STABILITY REPORT")
    print("=" * 90)
    print(f"  {'Protocol':<8} {'Key':<20} {'Min':>5} {'Max':>5} {'Mean':>6} {'StDev':>6} {'Stable?':>8}")
    print("-" * 90)
    for a in analyses:
        proto = a["protocol"]
        for key, stat in a["stability"].items():
            stable_mark = "✅" if stat["stable"] else "⚠️ "
            print(
                f"  {proto:<8} {key:<20} {stat['min']:>5} {stat['max']:>5} "
                f"{stat['mean']:>6} {stat['stdev']:>6} {stable_mark:>8}"
            )
        if a["fallback_spikes"] > 0:
            print(f"  {proto:<8} {'[fallback spikes]':<20} {'':>5} {'':>5} {'':>6} {'':>6} {'⚠️  ' + str(a['fallback_spikes']) + 'x':>8}")
        print()
    print("=" * 90)
    print(f"\n  Full report: data/outputs/regression_report.json\n")


if __name__ == "__main__":
    main()
