"""Domain models for the Protocol Analysis system.

These SQLModel classes serve as both Pydantic models and SQLAlchemy ORM models.
They cover all core entities: projects, session traces, message types,
protocol states, transitions, invariants, evidence, and probe runs.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


# ---------------------------------------------------------------------------
# ProtocolProject
# ---------------------------------------------------------------------------
class ProtocolProject(SQLModel, table=True):
    """A top-level analysis project targeting a specific protocol."""

    __tablename__ = "protocol_projects"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    protocol_name: str = Field(index=True)
    description: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# SessionTrace
# ---------------------------------------------------------------------------
class SessionTrace(SQLModel, table=True):
    """A raw protocol session or document imported into the project."""

    __tablename__ = "session_traces"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="protocol_projects.id", index=True)
    source_type: str = Field(description="doc | trace | probe | code")
    raw_content: str = ""
    parsed_content: str = ""  # JSON string of parsed events
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# MessageType
# ---------------------------------------------------------------------------
class MessageType(SQLModel, table=True):
    """A recognized protocol message type (e.g., USER, PASS, LIST)."""

    __tablename__ = "message_types"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="protocol_projects.id", index=True)
    name: str
    template: str = ""
    fields_json: str = "{}"  # JSON string describing fields
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# ProtocolState
# ---------------------------------------------------------------------------
class ProtocolState(SQLModel, table=True):
    """A candidate state in the protocol state machine."""

    __tablename__ = "protocol_states"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="protocol_projects.id", index=True)
    name: str
    description: str = ""
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Transition
# ---------------------------------------------------------------------------
class Transition(SQLModel, table=True):
    """A candidate transition edge in the protocol state machine."""

    __tablename__ = "transitions"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="protocol_projects.id", index=True)
    from_state: str
    to_state: str
    message_type: str
    confidence: float = 0.0
    status: str = "hypothesis"  # hypothesis | supported | disputed


# ---------------------------------------------------------------------------
# Invariant
# ---------------------------------------------------------------------------
class Invariant(SQLModel, table=True):
    """A protocol invariant / rule discovered during analysis."""

    __tablename__ = "invariants"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="protocol_projects.id", index=True)
    rule_text: str
    rule_type: str = ""  # ordering | field_constraint | conditional
    confidence: float = 0.0
    status: str = "hypothesis"  # hypothesis | supported | disputed


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------
class Evidence(SQLModel, table=True):
    """An evidence record linking a claim to its source material."""

    __tablename__ = "evidence"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="protocol_projects.id", index=True)
    claim_type: str  # transition | invariant | field_constraint
    claim_id: int
    source_type: str  # doc | trace | probe | code
    source_ref: str = ""
    snippet: str = ""
    score: float = 0.0


# ---------------------------------------------------------------------------
# ProbeRun
# ---------------------------------------------------------------------------
class ProbeRun(SQLModel, table=True):
    """Record of an online probe execution."""

    __tablename__ = "probe_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="protocol_projects.id", index=True)
    target_host: str = ""
    target_port: int = 0
    goal: str = ""
    request_payload: str = ""
    response_payload: str = ""
    result_summary: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
