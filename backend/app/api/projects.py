"""Project management API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..core.database import get_session
from ..models.domain import (
    ProtocolProject, MessageType, ProtocolState,
    Transition, Invariant, Evidence, ProbeRun, SessionTrace,
)
from ..schemas.protocol import (
    ProjectCreate, ProjectRead, DashboardStats, ModelExport,
    MessageTypeRead, StateRead, TransitionRead,
    InvariantRead, EvidenceRead, ProbeRead, TraceRead, TraceImport,
    AnalysisSummaryRead, ArtifactSummaryRead, PipelineRuntimeRead, AgentPathRead,
)
from ..services.artifact_service import analyze_iteration_feedback, build_protocol_schema, generate_seed_corpus
from ..services.runtime_service import get_pipeline_runtime

router = APIRouter(prefix="/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------
@router.post("", response_model=ProjectRead, status_code=201)
def create_project(body: ProjectCreate, session: Session = Depends(get_session)):
    project = ProtocolProject(**body.model_dump())
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.get("", response_model=list[ProjectRead])
def list_projects(session: Session = Depends(get_session)):
    return session.exec(select(ProtocolProject)).all()


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, session: Session = Depends(get_session)):
    project = session.get(ProtocolProject, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


# ---------------------------------------------------------------------------
# Data Import
# ---------------------------------------------------------------------------
@router.post("/{project_id}/import/doc", response_model=TraceRead, status_code=201)
def import_doc(project_id: int, body: TraceImport, session: Session = Depends(get_session)):
    _ensure_project(project_id, session)
    trace = SessionTrace(project_id=project_id, source_type="doc", raw_content=body.raw_content)
    session.add(trace)
    session.commit()
    session.refresh(trace)
    return trace


@router.post("/{project_id}/import/trace", response_model=TraceRead, status_code=201)
def import_trace(project_id: int, body: TraceImport, session: Session = Depends(get_session)):
    _ensure_project(project_id, session)
    trace = SessionTrace(project_id=project_id, source_type="trace", raw_content=body.raw_content)
    session.add(trace)
    session.commit()
    session.refresh(trace)
    return trace


@router.post("/{project_id}/import/code", response_model=TraceRead, status_code=201)
def import_code(project_id: int, body: TraceImport, session: Session = Depends(get_session)):
    _ensure_project(project_id, session)
    trace = SessionTrace(project_id=project_id, source_type="code", raw_content=body.raw_content)
    session.add(trace)
    session.commit()
    session.refresh(trace)
    return trace


# ---------------------------------------------------------------------------
# Result Queries
# ---------------------------------------------------------------------------
@router.get("/{project_id}/states", response_model=list[StateRead])
def list_states(project_id: int, session: Session = Depends(get_session)):
    _ensure_project(project_id, session)
    return session.exec(
        select(ProtocolState).where(ProtocolState.project_id == project_id)
    ).all()


@router.get("/{project_id}/transitions", response_model=list[TransitionRead])
def list_transitions(project_id: int, session: Session = Depends(get_session)):
    _ensure_project(project_id, session)
    return session.exec(
        select(Transition).where(Transition.project_id == project_id)
    ).all()


@router.get("/{project_id}/message-types", response_model=list[MessageTypeRead])
def list_message_types(project_id: int, session: Session = Depends(get_session)):
    _ensure_project(project_id, session)
    return session.exec(
        select(MessageType).where(MessageType.project_id == project_id)
    ).all()


@router.get("/{project_id}/invariants", response_model=list[InvariantRead])
def list_invariants(project_id: int, session: Session = Depends(get_session)):
    _ensure_project(project_id, session)
    return session.exec(
        select(Invariant).where(Invariant.project_id == project_id)
    ).all()


@router.get("/{project_id}/evidence", response_model=list[EvidenceRead])
def list_evidence(project_id: int, session: Session = Depends(get_session)):
    _ensure_project(project_id, session)
    return session.exec(
        select(Evidence).where(Evidence.project_id == project_id)
    ).all()


@router.get("/{project_id}/probes", response_model=list[ProbeRead])
def list_probes(project_id: int, session: Session = Depends(get_session)):
    _ensure_project(project_id, session)
    return session.exec(
        select(ProbeRun).where(ProbeRun.project_id == project_id)
    ).all()


@router.get("/{project_id}/traces", response_model=list[TraceRead])
def list_traces(project_id: int, session: Session = Depends(get_session)):
    _ensure_project(project_id, session)
    return session.exec(
        select(SessionTrace).where(SessionTrace.project_id == project_id)
    ).all()


# ---------------------------------------------------------------------------
# Dashboard Stats
# ---------------------------------------------------------------------------
@router.get("/{project_id}/dashboard", response_model=DashboardStats)
def dashboard(project_id: int, session: Session = Depends(get_session)):
    project = _ensure_project(project_id, session)
    return _build_dashboard_stats(project, project_id, session)


@router.get("/{project_id}/runtime", response_model=PipelineRuntimeRead)
def get_runtime(project_id: int, session: Session = Depends(get_session)):
    _ensure_project(project_id, session)
    return PipelineRuntimeRead(**get_pipeline_runtime(project_id))


@router.get("/{project_id}/analysis-summary", response_model=AnalysisSummaryRead)
def analysis_summary(project_id: int, session: Session = Depends(get_session)):
    project = _ensure_project(project_id, session)
    dashboard_stats = _build_dashboard_stats(project, project_id, session)
    runtime = PipelineRuntimeRead(**get_pipeline_runtime(project_id))
    schema = build_protocol_schema(project_id, session)
    seed_corpus = generate_seed_corpus(project_id, session, schema)
    feedback = analyze_iteration_feedback(project_id, session, schema, seed_corpus)
    artifacts = ArtifactSummaryRead(
        schema_message_count=len(schema.get("messages", {})),
        seed_count=seed_corpus.get("seed_count", 0),
        feedback_action_count=len(feedback.get("recommended_actions", [])),
        recommended_actions=feedback.get("recommended_actions", []),
        focus_commands=feedback.get("suggested_campaign", {}).get("focus_commands", []),
        unused_message_types=feedback.get("unused_message_types", []),
    )
    agent_path = _build_agent_path(project_id, runtime, session)
    return AnalysisSummaryRead(
        dashboard=dashboard_stats,
        runtime=runtime,
        artifacts=artifacts,
        agent_path=agent_path,
    )


def _build_dashboard_stats(project: ProtocolProject, project_id: int, session: Session) -> DashboardStats:
    mt = len(session.exec(select(MessageType).where(MessageType.project_id == project_id)).all())
    st = len(session.exec(select(ProtocolState).where(ProtocolState.project_id == project_id)).all())
    tr = session.exec(select(Transition).where(Transition.project_id == project_id)).all()
    inv = len(session.exec(select(Invariant).where(Invariant.project_id == project_id)).all())
    pr = len(session.exec(select(ProbeRun).where(ProbeRun.project_id == project_id)).all())
    disputed = len([t for t in tr if t.status == "disputed"])
    # Also count disputed invariants
    disputed += len([
        i for i in session.exec(select(Invariant).where(Invariant.project_id == project_id)).all()
        if i.status == "disputed"
    ])
    return DashboardStats(
        project_name=project.name,
        protocol_name=project.protocol_name,
        message_type_count=mt,
        state_count=st,
        transition_count=len(tr),
        invariant_count=inv,
        probe_count=pr,
        disputed_count=disputed,
    )


def _build_agent_path(project_id: int, runtime: PipelineRuntimeRead, session: Session) -> AgentPathRead:
    """Compute agent-path signals from pipeline stage summaries and evidence provenance."""
    # Per-stage fallback / call counts from runtime summaries
    spec_stage = next((s for s in runtime.stages if s.key == "spec"), None)
    trace_stage = next((s for s in runtime.stages if s.key == "trace"), None)
    probe_stage = next((s for s in runtime.stages if s.key == "probe"), None)

    spec_fallback = bool(spec_stage.summary.get("fallback_used")) if spec_stage else False
    trace_fallback = bool(trace_stage.summary.get("fallback_used")) if trace_stage else False
    spec_llm_calls = int(spec_stage.summary.get("llm_tool_calls", 0)) if spec_stage else 0
    trace_llm_calls = int(trace_stage.summary.get("llm_tool_calls", 0)) if trace_stage else 0
    probe_llm_calls = int(probe_stage.summary.get("llm_tool_calls", 0)) if probe_stage else 0

    # All evidence records for this project
    all_evidence = session.exec(
        select(Evidence).where(Evidence.project_id == project_id)
    ).all()

    # Transition provenance: group by claim_id, classify by source_ref tag
    evidence_rows = [e for e in all_evidence if e.claim_type == "transition"]
    groups: dict[int, set[str]] = {}
    for ev in evidence_rows:
        ref = (ev.source_ref or "").lower()
        if "fallback" in ref or "heuristic" in ref:
            tag = "fallback"
        elif "llm" in ref:
            tag = "agent"
        else:
            tag = "other"
        groups.setdefault(int(ev.claim_id), set()).add(tag)

    agent_count = fallback_count = mixed_count = 0
    for tags in groups.values():
        if "agent" in tags and "fallback" in tags:
            mixed_count += 1
        elif "agent" in tags:
            agent_count += 1
        elif "fallback" in tags:
            fallback_count += 1

    # Granular source breakdown
    probe_evidence_count = sum(
        1 for e in all_evidence if "probe_run:" in (e.source_ref or "").lower()
    )
    llm_evidence_count = sum(
        1 for e in all_evidence if "llm" in (e.source_ref or "").lower()
    )

    # Transition status distribution
    transitions = session.exec(
        select(Transition).where(Transition.project_id == project_id)
    ).all()
    t_supported = sum(1 for t in transitions if t.status == "supported")
    t_hypothesis = sum(1 for t in transitions if t.status == "hypothesis")
    t_disputed = sum(1 for t in transitions if t.status == "disputed")

    return AgentPathRead(
        spec_fallback=spec_fallback,
        trace_fallback=trace_fallback,
        spec_llm_calls=spec_llm_calls,
        trace_llm_calls=trace_llm_calls,
        probe_llm_calls=probe_llm_calls,
        transition_provenance_agent=agent_count,
        transition_provenance_fallback=fallback_count,
        transition_provenance_mixed=mixed_count,
        probe_evidence_count=probe_evidence_count,
        llm_evidence_count=llm_evidence_count,
        transition_supported=t_supported,
        transition_hypothesis=t_hypothesis,
        transition_disputed=t_disputed,
    )


# ---------------------------------------------------------------------------
# Model Export
# ---------------------------------------------------------------------------
@router.get("/{project_id}/model/export", response_model=ModelExport)
def export_model(project_id: int, session: Session = Depends(get_session)):
    project = _ensure_project(project_id, session)
    return ModelExport(
        project=ProjectRead(**project.model_dump()),
        message_types=session.exec(select(MessageType).where(MessageType.project_id == project_id)).all(),
        states=session.exec(select(ProtocolState).where(ProtocolState.project_id == project_id)).all(),
        transitions=session.exec(select(Transition).where(Transition.project_id == project_id)).all(),
        invariants=session.exec(select(Invariant).where(Invariant.project_id == project_id)).all(),
        evidence=session.exec(select(Evidence).where(Evidence.project_id == project_id)).all(),
        probes=session.exec(select(ProbeRun).where(ProbeRun.project_id == project_id)).all(),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ensure_project(project_id: int, session: Session) -> ProtocolProject:
    project = session.get(ProtocolProject, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project
