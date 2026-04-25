"""Full analysis pipeline runner.

Orchestrates:
1. Project creation
2. Data import (doc + ftp_sessions.txt + ProFuzzBench seeds)
3. Spec Agent (LLM)
4. Trace Agent (LLM)
5. Verifier Agent
6. Probe Agent
7. Export results + evaluation report
"""

from __future__ import annotations
import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlmodel import Session
from app.core.database import engine, create_db_and_tables
from app.models.domain import ProtocolProject, SessionTrace
from app.services.spec_agent_service import run_spec_agent
from app.services.trace_agent_service import run_trace_agent
from app.services.verifier_service import run_verifier
from app.services.probe_service import run_probe_agent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_full_analysis")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


def load_profuzzbench_seeds() -> list[str]:
    """Load ProFuzzBench seed files as command-sequence traces."""
    seed_dir = DATA_DIR / "traces" / "profuzzbench"
    if not seed_dir.exists():
        logger.warning("ProFuzzBench seed dir not found: %s", seed_dir)
        return []
    sessions = []
    for seed_file in sorted(seed_dir.glob("*.raw")):
        try:
            content = seed_file.read_bytes().decode("utf-8", errors="replace")
            content = content.replace("\r\n", "\n").replace("\r", "\n").strip()
            if content:
                sessions.append(content)
        except Exception as e:
            logger.warning("Failed to read %s: %s", seed_file, e)
    logger.info("Loaded %d ProFuzzBench seed files", len(sessions))
    return sessions


def load_ftp_sessions() -> list[str]:
    """Load existing ftp_sessions.txt (split by ---)."""
    path = DATA_DIR / "traces" / "ftp_sessions.txt"
    if not path.exists():
        return []
    text = path.read_text()
    sessions = [s.strip() for s in text.split("---") if s.strip()]
    logger.info("Loaded %d ftp_sessions.txt entries", len(sessions))
    return sessions


def create_project(db: Session) -> ProtocolProject:
    project = ProtocolProject(
        name=f"FTP Protocol Analysis — ProFuzzBench Run {datetime.now().strftime('%Y%m%d_%H%M')}",
        protocol_name="FTP",
        description="LLM-driven protocol analysis using ProFuzzBench seed corpus + FTP RFC traces",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info("Created project id=%d: %s", project.id, project.name)
    return project


def import_data(project: ProtocolProject, db: Session) -> dict:
    stats = {"doc": 0, "trace_ftp_sessions": 0, "trace_profuzzbench": 0}

    doc_path = DATA_DIR / "docs" / "ftp_summary.md"
    if doc_path.exists():
        doc = SessionTrace(project_id=project.id, source_type="doc",
                           raw_content=doc_path.read_text())
        db.add(doc)
        stats["doc"] = 1
        logger.info("Imported doc: %s", doc_path.name)

    for content in load_ftp_sessions():
        t = SessionTrace(project_id=project.id, source_type="trace", raw_content=content)
        db.add(t)
        stats["trace_ftp_sessions"] += 1

    for content in load_profuzzbench_seeds():
        t = SessionTrace(project_id=project.id, source_type="trace", raw_content=content)
        db.add(t)
        stats["trace_profuzzbench"] += 1

    db.commit()
    logger.info("Data imported: %s", stats)
    return stats


def run_pipeline(project_id: int, db: Session) -> dict:
    results = {}

    logger.info("=== Running Spec Agent (LLM) ===")
    results["spec"] = run_spec_agent(project_id, db)
    logger.info("Spec: %d message types, %d invariants",
                len(results["spec"].get("message_types_created", [])),
                len(results["spec"].get("invariants_created", [])))

    logger.info("=== Running Trace Agent (LLM) ===")
    results["trace"] = run_trace_agent(project_id, db)
    logger.info("Trace: %d states, %d transitions",
                len(results["trace"].get("states_created", [])),
                len(results["trace"].get("transitions_created", [])))

    logger.info("=== Running Verifier Agent ===")
    results["verifier"] = run_verifier(project_id, db)
    logger.info("Verifier: %d transitions, %d invariants verified",
                results["verifier"].get("transitions_verified", 0),
                results["verifier"].get("invariants_verified", 0))

    logger.info("=== Running Probe Agent ===")
    results["probe"] = run_probe_agent(project_id, db)
    logger.info("Probe: %d probes executed", results["probe"].get("probes_executed", 0))

    return results


def export_results(project_id: int, db: Session, pipeline_results: dict,
                   import_stats: dict) -> dict:
    from app.models.domain import (MessageType, ProtocolState, Transition,
                                    Invariant, Evidence, ProbeRun)
    from sqlmodel import select

    msg_types = db.exec(select(MessageType).where(MessageType.project_id == project_id)).all()
    states = db.exec(select(ProtocolState).where(ProtocolState.project_id == project_id)).all()
    transitions = db.exec(select(Transition).where(Transition.project_id == project_id)).all()
    invariants = db.exec(select(Invariant).where(Invariant.project_id == project_id)).all()
    evidence = db.exec(select(Evidence).where(Evidence.project_id == project_id)).all()
    probes = db.exec(select(ProbeRun).where(ProbeRun.project_id == project_id)).all()

    status_dist = {"hypothesis": 0, "supported": 0, "disputed": 0}
    for t in transitions:
        status_dist[t.status] = status_dist.get(t.status, 0) + 1
    inv_status_dist = {"hypothesis": 0, "supported": 0, "disputed": 0}
    for inv in invariants:
        inv_status_dist[inv.status] = inv_status_dist.get(inv.status, 0) + 1

    evaluation = {
        "project_id": project_id,
        "run_timestamp": datetime.utcnow().isoformat(),
        "data_import": import_stats,
        "metrics": {
            "message_types": len(msg_types),
            "states": len(states),
            "transitions": len(transitions),
            "invariants": len(invariants),
            "evidence_records": len(evidence),
            "probe_runs": len(probes),
        },
        "transition_status_distribution": status_dist,
        "invariant_status_distribution": inv_status_dist,
        "llm_tool_calls": {
            "spec_agent": pipeline_results.get("spec", {}).get("llm_tool_calls", 0),
            "trace_agent": pipeline_results.get("trace", {}).get("llm_tool_calls", 0),
        },
        "fallback_used": {
            "spec_agent": pipeline_results.get("spec", {}).get("fallback_used", False),
            "trace_agent": pipeline_results.get("trace", {}).get("fallback_used", False),
        },
        "message_types_list": [m.name for m in msg_types],
        "states_list": [{"name": s.name, "description": s.description, "confidence": s.confidence}
                        for s in states],
        "transitions_list": [{"from": t.from_state, "to": t.to_state, "via": t.message_type,
                               "confidence": t.confidence, "status": t.status}
                              for t in transitions],
        "invariants_list": [{"rule": inv.rule_text, "type": inv.rule_type,
                              "confidence": inv.confidence, "status": inv.status}
                            for inv in invariants],
        "pipeline_results": pipeline_results,
    }

    out_path = OUTPUT_DIR / f"evaluation_report_{project_id}.json"
    out_path.write_text(json.dumps(evaluation, indent=2, ensure_ascii=False))
    logger.info("Evaluation report saved: %s", out_path)
    return evaluation


def print_summary(evaluation: dict):
    m = evaluation["metrics"]
    print("\n" + "=" * 60)
    print("  PROTOCOL ANALYSIS RESULTS SUMMARY")
    print("=" * 60)
    print(f"  Project ID        : {evaluation['project_id']}")
    print(f"  Run time          : {evaluation['run_timestamp']}")
    print(f"  Data: sessions    : {evaluation['data_import'].get('trace_ftp_sessions',0)} ftp + "
          f"{evaluation['data_import'].get('trace_profuzzbench',0)} ProFuzzBench")
    print("-" * 60)
    print(f"  Message types     : {m['message_types']}")
    print(f"  States            : {m['states']}")
    print(f"  Transitions       : {m['transitions']}")
    print(f"    supported       : {evaluation['transition_status_distribution'].get('supported',0)}")
    print(f"    hypothesis      : {evaluation['transition_status_distribution'].get('hypothesis',0)}")
    print(f"    disputed        : {evaluation['transition_status_distribution'].get('disputed',0)}")
    print(f"  Invariants        : {m['invariants']}")
    print(f"  Evidence records  : {m['evidence_records']}")
    print(f"  Probe runs        : {m['probe_runs']}")
    print("-" * 60)
    print(f"  LLM calls (Spec)  : {evaluation['llm_tool_calls']['spec_agent']}")
    print(f"  LLM calls (Trace) : {evaluation['llm_tool_calls']['trace_agent']}")
    tc_spec = evaluation['fallback_used']['spec_agent']
    tc_trace = evaluation['fallback_used']['trace_agent']
    print(f"  Fallback used     : Spec={tc_spec} Trace={tc_trace}")
    print("=" * 60)
    print(f"\n  Full report: data/outputs/evaluation_report_{evaluation['project_id']}.json")


def main():
    create_db_and_tables()

    with Session(engine) as db:
        project = create_project(db)
        import_stats = import_data(project, db)
        pipeline_results = run_pipeline(project.id, db)
        evaluation = export_results(project.id, db, pipeline_results, import_stats)
        print_summary(evaluation)


if __name__ == "__main__":
    main()
