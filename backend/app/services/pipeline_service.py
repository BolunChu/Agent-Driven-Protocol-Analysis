"""Full pipeline service — orchestrates all agents in sequence."""

from sqlmodel import Session
from .spec_agent_service import run_spec_agent
from .trace_agent_service import run_trace_agent
from .verifier_service import run_verifier
from .probe_service import run_probe_agent


def run_full_pipeline(project_id: int, session: Session) -> dict:
    """Execute the full analysis pipeline: Spec -> Trace -> Verifier -> Probe."""
    results = {}
    results["spec"] = run_spec_agent(project_id, session)
    results["trace"] = run_trace_agent(project_id, session)
    results["verifier"] = run_verifier(project_id, session)
    results["probe"] = run_probe_agent(project_id, session)
    return results
