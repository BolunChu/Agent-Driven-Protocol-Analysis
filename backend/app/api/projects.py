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
)

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
