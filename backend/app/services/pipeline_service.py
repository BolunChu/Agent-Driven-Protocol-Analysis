"""Full pipeline service — orchestrates all agents in sequence."""

from sqlmodel import Session
from .spec_agent_service import run_spec_agent
from .trace_agent_service import run_trace_agent
from .verifier_service import run_verifier
from .probe_service import run_probe_agent
from .artifact_service import analyze_iteration_feedback, build_protocol_schema, generate_seed_corpus
from .runtime_service import (
    complete_pipeline,
    complete_stage,
    fail_pipeline,
    fail_stage,
    start_pipeline,
    start_stage,
)


def run_full_pipeline(project_id: int, session: Session) -> dict:
    """Execute the full analysis pipeline: Spec -> Trace -> Verifier -> Probe."""
    results = {}
    start_pipeline(project_id)
    try:
        start_stage(project_id, "spec")
        results["spec"] = run_spec_agent(project_id, session)
        complete_stage(project_id, "spec", {
            "message_types_created": len(results["spec"].get("message_types_created", [])),
            "invariants_created": len(results["spec"].get("invariants_created", [])),
            "fallback_used": results["spec"].get("fallback_used", False),
        })

        start_stage(project_id, "trace")
        results["trace"] = run_trace_agent(project_id, session)
        complete_stage(project_id, "trace", {
            "states_created": len(results["trace"].get("states_created", [])),
            "transitions_created": len(results["trace"].get("transitions_created", [])),
            "fallback_used": results["trace"].get("fallback_used", False),
        })

        start_stage(project_id, "verifier")
        results["verifier"] = run_verifier(project_id, session)
        complete_stage(project_id, "verifier", {
            "transitions_verified": results["verifier"].get("transitions_verified", 0),
            "invariants_verified": results["verifier"].get("invariants_verified", 0),
            "status_changes": len(results["verifier"].get("status_changes", [])),
        })

        start_stage(project_id, "probe")
        results["probe"] = run_probe_agent(project_id, session)
        complete_stage(project_id, "probe", {
            "probes_executed": results["probe"].get("probes_executed", 0),
            "model_updates": len(results["probe"].get("model_updates", [])),
        })

        start_stage(project_id, "artifacts")
        schema = build_protocol_schema(project_id, session)
        results["artifacts"] = {"protocol_schema": schema}
        complete_stage(project_id, "artifacts", {
            "schema_message_count": len(schema.get("messages", {})),
            "state_count": len(schema.get("states", [])),
        })

        start_stage(project_id, "seed_generation")
        seed_corpus = generate_seed_corpus(project_id, session, schema)
        results["seed_generation"] = seed_corpus
        complete_stage(project_id, "seed_generation", {
            "seed_count": seed_corpus.get("seed_count", 0),
            "categories": len(seed_corpus.get("categories", [])),
        })

        start_stage(project_id, "feedback")
        results["feedback"] = analyze_iteration_feedback(project_id, session, schema, seed_corpus)
        complete_stage(project_id, "feedback", {
            "recommended_actions": len(results["feedback"].get("recommended_actions", [])),
            "focus_commands": len(results["feedback"].get("suggested_campaign", {}).get("focus_commands", [])),
        })
        complete_pipeline(project_id)
    except Exception as exc:
        stage_key = ""
        if results.get("feedback") is None and results.get("seed_generation") is not None:
            stage_key = "feedback"
        elif results.get("seed_generation") is None and results.get("artifacts") is not None:
            stage_key = "seed_generation"
        elif results.get("artifacts") is None and results.get("probe") is not None:
            stage_key = "artifacts"
        elif results.get("probe") is None and results.get("verifier") is not None:
            stage_key = "probe"
        elif results.get("verifier") is None and results.get("trace") is not None:
            stage_key = "verifier"
        elif results.get("trace") is None and results.get("spec") is not None:
            stage_key = "trace"
        elif results.get("spec") is None:
            stage_key = "spec"
        if stage_key:
            fail_stage(project_id, stage_key, str(exc))
        fail_pipeline(project_id, str(exc), stage_key)
        raise
    return results
