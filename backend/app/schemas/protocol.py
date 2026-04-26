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


class PipelineStageStatus(BaseModel):
    key: str
    label: str
    status: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    summary: dict = {}


class PipelineRuntimeRead(BaseModel):
    project_id: int
    run_status: str
    current_stage: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    error: str = ""
    stages: list[PipelineStageStatus] = []


class ArtifactSummaryRead(BaseModel):
    schema_message_count: int
    seed_count: int
    feedback_action_count: int
    recommended_actions: list[str] = []
    focus_commands: list[str] = []
    unused_message_types: list[str] = []


class AgentPathRead(BaseModel):
    """Agent-first path observability: provenance & fallback signals."""
    spec_fallback: bool = False
    trace_fallback: bool = False
    spec_llm_calls: int = 0
    trace_llm_calls: int = 0
    probe_llm_calls: int = 0
    transition_provenance_agent: int = 0
    transition_provenance_fallback: int = 0
    transition_provenance_mixed: int = 0
    # Granular fallback source breakdown (Task 4: 收紧 fallback 残留来源的可解释性)
    probe_evidence_count: int = 0       # Evidence records from probe runs
    llm_evidence_count: int = 0         # Evidence records directly from LLM agents
    # Transition status distribution
    transition_supported: int = 0
    transition_hypothesis: int = 0
    transition_disputed: int = 0


class AnalysisSummaryRead(BaseModel):
    dashboard: DashboardStats
    runtime: PipelineRuntimeRead
    artifacts: ArtifactSummaryRead
    agent_path: AgentPathRead = AgentPathRead()
