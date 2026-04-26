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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlmodel import Session
from app.core.database import engine, create_db_and_tables
from app.models.domain import ProtocolProject, SessionTrace
from app.protocols.registry import get_protocol_adapter
from app.services.spec_agent_service import run_spec_agent
from app.services.trace_agent_service import run_trace_agent
from app.services.verifier_service import run_verifier
from app.services.probe_service import run_probe_agent
from app.services.artifact_service import (
    analyze_iteration_feedback,
    build_protocol_schema,
    generate_seed_corpus,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_full_analysis")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


def create_project(db: Session, protocol_name: str) -> ProtocolProject:
    adapter = get_protocol_adapter(protocol_name)
    metadata = adapter.create_project_metadata()
    project = ProtocolProject(
        name=f"{metadata['name_prefix']} {datetime.now().strftime('%Y%m%d_%H%M')}",
        protocol_name=protocol_name.upper(),
        description=metadata["description"],
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info("Created project id=%d: %s", project.id, project.name)
    return project


def import_data(project: ProtocolProject, db: Session) -> dict:
    adapter = get_protocol_adapter(project.protocol_name)
    stats = {"doc": 0, "trace_protocol_sessions": 0, "trace_profuzzbench": 0}

    for content in adapter.load_doc_inputs(str(PROJECT_ROOT)):
        doc = SessionTrace(project_id=project.id, source_type="doc", raw_content=content)
        db.add(doc)
        stats["doc"] += 1

    protocol_traces = adapter.load_trace_inputs(str(PROJECT_ROOT))
    logger.info("Loaded %d protocol-native trace entries", len(protocol_traces))
    for content in protocol_traces:
        t = SessionTrace(project_id=project.id, source_type="trace", raw_content=content)
        db.add(t)
        stats["trace_protocol_sessions"] += 1

    profuzzbench_seeds = adapter.load_seed_inputs(str(PROJECT_ROOT))
    logger.info("Loaded %d ProFuzzBench seed files", len(profuzzbench_seeds))
    for content in profuzzbench_seeds:
        t = SessionTrace(project_id=project.id, source_type="trace", raw_content=content)
        db.add(t)
        stats["trace_profuzzbench"] += 1

    db.commit()
    logger.info("Data imported: %s", stats)
    return stats


def run_pipeline(project_id: int, db: Session) -> dict:
    results = {}

    parallel_spec_trace = os.getenv("ANALYSIS_PARALLEL_SPEC_TRACE", "1") == "1"
    if parallel_spec_trace:
        logger.info("=== Running Spec + Trace Agents (parallel) ===")

        def _run_spec() -> dict:
            with Session(engine) as parallel_session:
                return run_spec_agent(project_id, parallel_session)

        def _run_trace() -> dict:
            with Session(engine) as parallel_session:
                return run_trace_agent(project_id, parallel_session)

        with ThreadPoolExecutor(max_workers=2) as executor:
            spec_future = executor.submit(_run_spec)
            trace_future = executor.submit(_run_trace)
            results["spec"] = spec_future.result()
            results["trace"] = trace_future.result()
    else:
        logger.info("=== Running Spec Agent (LLM) ===")
        results["spec"] = run_spec_agent(project_id, db)
        logger.info("=== Running Trace Agent (LLM) ===")
        results["trace"] = run_trace_agent(project_id, db)

    db.expire_all()
    logger.info("Spec: %d message types, %d invariants",
                len(results["spec"].get("message_types_created", [])),
                len(results["spec"].get("invariants_created", [])))
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

    logger.info("=== Building Protocol Schema Artifact ===")
    schema = build_protocol_schema(project_id, db)
    results["artifacts"] = {"protocol_schema": schema}
    logger.info("Artifact: %d message schemas exported", len(schema.get("messages", {})))

    logger.info("=== Generating Enhanced Seed Corpus ===")
    seed_corpus = generate_seed_corpus(project_id, db, schema)
    results["seed_generation"] = seed_corpus
    logger.info("Seed generation: %d candidate sessions", seed_corpus.get("seed_count", 0))

    logger.info("=== Analyzing Iteration Feedback ===")
    feedback = analyze_iteration_feedback(project_id, db, schema, seed_corpus)
    results["feedback"] = feedback
    logger.info("Feedback: %d recommended actions", len(feedback.get("recommended_actions", [])))

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

    def _claim_provenance(claim_type: str) -> dict[str, int]:
        groups: dict[int, set[str]] = {}
        for ev in evidence:
            if ev.claim_type != claim_type:
                continue
            claim_id = int(ev.claim_id)
            src = (ev.source_ref or "").lower()
            if "fallback" in src or "heuristic" in src:
                tag = "fallback"
            elif "llm" in src:
                tag = "agent"
            else:
                tag = "other"
            groups.setdefault(claim_id, set()).add(tag)

        counts = {"agent": 0, "fallback": 0, "mixed": 0, "other": 0}
        for tags in groups.values():
            if "agent" in tags and "fallback" in tags:
                counts["mixed"] += 1
            elif "agent" in tags:
                counts["agent"] += 1
            elif "fallback" in tags:
                counts["fallback"] += 1
            else:
                counts["other"] += 1
        return counts

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
            "probe_agent": pipeline_results.get("probe", {}).get("llm_tool_calls", 0),
        },
        "fallback_used": {
            "spec_agent": pipeline_results.get("spec", {}).get("fallback_used", False),
            "trace_agent": pipeline_results.get("trace", {}).get("fallback_used", False),
        },
        "derived_artifacts": {
            "schema_message_count": len(pipeline_results.get("artifacts", {}).get("protocol_schema", {}).get("messages", {})),
            "generated_seed_count": pipeline_results.get("seed_generation", {}).get("seed_count", 0),
            "feedback_actions": len(pipeline_results.get("feedback", {}).get("recommended_actions", [])),
        },
        "agent_path_signals": {
            "trace_observation_tool_used": bool(pipeline_results.get("trace", {}).get("observation_tool_used", False)),
            "probe_llm_plan_used": bool(pipeline_results.get("probe", {}).get("llm_plan_used", False)),
        },
        "claim_provenance_distribution": {
            "message_type": _claim_provenance("message_type"),
            "state": _claim_provenance("state"),
            "transition": _claim_provenance("transition"),
            "invariant": _claim_provenance("invariant"),
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
        "protocol_schema": pipeline_results.get("artifacts", {}).get("protocol_schema", {}),
        "generated_seed_corpus": pipeline_results.get("seed_generation", {}),
        "feedback_analysis": pipeline_results.get("feedback", {}),
        "pipeline_results": pipeline_results,
    }

    out_path = OUTPUT_DIR / f"evaluation_report_{project_id}.json"
    out_path.write_text(json.dumps(evaluation, indent=2, ensure_ascii=False))
    logger.info("Evaluation report saved: %s", out_path)

    schema_path = OUTPUT_DIR / f"protocol_schema_{project_id}.json"
    schema_path.write_text(json.dumps(pipeline_results.get("artifacts", {}).get("protocol_schema", {}), indent=2, ensure_ascii=False))
    logger.info("Protocol schema saved: %s", schema_path)

    seed_path = OUTPUT_DIR / f"generated_seeds_{project_id}.json"
    seed_path.write_text(json.dumps(pipeline_results.get("seed_generation", {}), indent=2, ensure_ascii=False))
    logger.info("Generated seeds saved: %s", seed_path)

    feedback_path = OUTPUT_DIR / f"feedback_report_{project_id}.json"
    feedback_path.write_text(json.dumps(pipeline_results.get("feedback", {}), indent=2, ensure_ascii=False))
    logger.info("Feedback report saved: %s", feedback_path)
    return evaluation


def print_summary(evaluation: dict):
    m = evaluation["metrics"]
    print("\n" + "=" * 60)
    print("  PROTOCOL ANALYSIS RESULTS SUMMARY")
    print("=" * 60)
    print(f"  Project ID        : {evaluation['project_id']}")
    print(f"  Run time          : {evaluation['run_timestamp']}")
    print(f"  Data: sessions    : {evaluation['data_import'].get('trace_protocol_sessions',0)} protocol + "
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
    print(f"  Schema messages   : {evaluation['derived_artifacts']['schema_message_count']}")
    print(f"  Generated seeds   : {evaluation['derived_artifacts']['generated_seed_count']}")
    print("-" * 60)
    print(f"  LLM calls (Spec)  : {evaluation['llm_tool_calls']['spec_agent']}")
    print(f"  LLM calls (Trace) : {evaluation['llm_tool_calls']['trace_agent']}")
    print(f"  LLM calls (Probe) : {evaluation['llm_tool_calls'].get('probe_agent', 0)}")
    tc_spec = evaluation['fallback_used']['spec_agent']
    tc_trace = evaluation['fallback_used']['trace_agent']
    print(f"  Fallback used     : Spec={tc_spec} Trace={tc_trace}")
    trace_agent_claims = evaluation['claim_provenance_distribution']['transition']['agent']
    trace_fallback_claims = evaluation['claim_provenance_distribution']['transition']['fallback']
    print(f"  Transition provenance: agent={trace_agent_claims} fallback={trace_fallback_claims}")
    print("=" * 60)
    print(f"\n  Full report: data/outputs/evaluation_report_{evaluation['project_id']}.json")


def main():
    protocol_name = sys.argv[1] if len(sys.argv) > 1 else "FTP"
    create_db_and_tables()
    with Session(engine) as db:
        project = create_project(db, protocol_name)
        stats = import_data(project, db)
        results = run_pipeline(project.id, db)
        evaluation = export_results(project.id, db, results, stats)
        print_summary(evaluation)


if __name__ == "__main__":
    main()
