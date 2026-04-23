"""Pydantic schemas for request / response validation."""

from datetime import datetime
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------
class ProjectCreate(BaseModel):
    name: str
    protocol_name: str
    description: str = ""


class ProjectRead(BaseModel):
    id: int
    name: str
    protocol_name: str
    description: str
    created_at: datetime


# ---------------------------------------------------------------------------
# SessionTrace
# ---------------------------------------------------------------------------
class TraceImport(BaseModel):
    source_type: str  # doc | trace | probe | code
    raw_content: str


class TraceRead(BaseModel):
    id: int
    project_id: int
    source_type: str
    raw_content: str
    parsed_content: str
    created_at: datetime


# ---------------------------------------------------------------------------
# MessageType
# ---------------------------------------------------------------------------
class MessageTypeRead(BaseModel):
    id: int
    project_id: int
    name: str
    template: str
    fields_json: str
    confidence: float


# ---------------------------------------------------------------------------
# State / Transition / Invariant
# ---------------------------------------------------------------------------
class StateRead(BaseModel):
    id: int
    project_id: int
    name: str
    description: str
    confidence: float


class TransitionRead(BaseModel):
    id: int
    project_id: int
    from_state: str
    to_state: str
    message_type: str
    confidence: float
    status: str


class InvariantRead(BaseModel):
    id: int
    project_id: int
    rule_text: str
    rule_type: str
    confidence: float
    status: str


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------
class EvidenceRead(BaseModel):
    id: int
    project_id: int
    claim_type: str
    claim_id: int
    source_type: str
    source_ref: str
    snippet: str
    score: float


# ---------------------------------------------------------------------------
# ProbeRun
# ---------------------------------------------------------------------------
class ProbeRead(BaseModel):
    id: int
    project_id: int
    target_host: str
    target_port: int
    goal: str
    request_payload: str
    response_payload: str
    result_summary: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Model Export
# ---------------------------------------------------------------------------
class ModelExport(BaseModel):
    """Full protocol model snapshot for export."""
    project: ProjectRead
    message_types: list[MessageTypeRead] = []
    states: list[StateRead] = []
    transitions: list[TransitionRead] = []
    invariants: list[InvariantRead] = []
    evidence: list[EvidenceRead] = []
    probes: list[ProbeRead] = []


# ---------------------------------------------------------------------------
# Dashboard Stats
# ---------------------------------------------------------------------------
class DashboardStats(BaseModel):
    project_name: str
    protocol_name: str
    message_type_count: int
    state_count: int
    transition_count: int
    invariant_count: int
    probe_count: int
    disputed_count: int
