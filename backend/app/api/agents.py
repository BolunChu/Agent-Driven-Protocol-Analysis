"""Agent execution API routes — runs Spec/Trace/Verifier/Probe agents."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..core.database import get_session
from ..models.domain import ProtocolProject, SessionTrace
from ..services.spec_agent_service import run_spec_agent
from ..services.trace_agent_service import run_trace_agent
from ..services.verifier_service import run_verifier
from ..services.probe_service import run_probe_agent
from ..services.pipeline_service import run_full_pipeline

router = APIRouter(prefix="/projects/{project_id}/run", tags=["agents"])


def _ensure_project(project_id: int, session: Session) -> ProtocolProject:
    project = session.get(ProtocolProject, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.post("/spec-agent")
def run_spec(project_id: int, session: Session = Depends(get_session)):
    _ensure_project(project_id, session)
    result = run_spec_agent(project_id, session)
    return {"status": "ok", "result": result}


@router.post("/trace-agent")
def run_trace(project_id: int, session: Session = Depends(get_session)):
    _ensure_project(project_id, session)
    result = run_trace_agent(project_id, session)
    return {"status": "ok", "result": result}


@router.post("/verifier")
def run_verify(project_id: int, session: Session = Depends(get_session)):
    _ensure_project(project_id, session)
    result = run_verifier(project_id, session)
    return {"status": "ok", "result": result}


@router.post("/probe")
def run_probe(project_id: int, session: Session = Depends(get_session)):
    _ensure_project(project_id, session)
    result = run_probe_agent(project_id, session)
    return {"status": "ok", "result": result}


@router.post("/full-pipeline")
def run_pipeline(project_id: int, session: Session = Depends(get_session)):
    _ensure_project(project_id, session)
    result = run_full_pipeline(project_id, session)
    return {"status": "ok", "result": result}
