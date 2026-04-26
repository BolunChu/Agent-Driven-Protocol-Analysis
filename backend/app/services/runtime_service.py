from __future__ import annotations

from datetime import datetime
from threading import Lock

_STAGE_LABELS = {
    "spec": "Spec Agent",
    "trace": "Trace Agent",
    "verifier": "Verifier",
    "probe": "Probe Agent",
    "artifacts": "Protocol Schema",
    "seed_generation": "Seed Generation",
    "feedback": "Feedback Analysis",
}

_PIPELINE_ORDER = [
    "spec",
    "trace",
    "verifier",
    "probe",
    "artifacts",
    "seed_generation",
    "feedback",
]

_runtime_lock = Lock()
_runtime_state: dict[int, dict] = {}


def _empty_stage(stage_key: str) -> dict:
    return {
        "key": stage_key,
        "label": _STAGE_LABELS[stage_key],
        "status": "pending",
        "started_at": None,
        "ended_at": None,
        "summary": {},
    }


def _empty_runtime(project_id: int) -> dict:
    return {
        "project_id": project_id,
        "run_status": "idle",
        "current_stage": "",
        "started_at": None,
        "ended_at": None,
        "error": "",
        "stages": [_empty_stage(stage_key) for stage_key in _PIPELINE_ORDER],
    }


def get_pipeline_runtime(project_id: int) -> dict:
    with _runtime_lock:
        state = _runtime_state.get(project_id)
        if not state:
            return _empty_runtime(project_id)
        return {
            "project_id": state["project_id"],
            "run_status": state["run_status"],
            "current_stage": state["current_stage"],
            "started_at": state["started_at"],
            "ended_at": state["ended_at"],
            "error": state["error"],
            "stages": [
                {
                    "key": stage["key"],
                    "label": stage["label"],
                    "status": stage["status"],
                    "started_at": stage["started_at"],
                    "ended_at": stage["ended_at"],
                    "summary": dict(stage["summary"]),
                }
                for stage in state["stages"]
            ],
        }


def start_pipeline(project_id: int) -> None:
    now = datetime.utcnow()
    with _runtime_lock:
        state = _empty_runtime(project_id)
        state["run_status"] = "running"
        state["started_at"] = now
        _runtime_state[project_id] = state


def start_stage(project_id: int, stage_key: str) -> None:
    now = datetime.utcnow()
    with _runtime_lock:
        state = _runtime_state.setdefault(project_id, _empty_runtime(project_id))
        state["run_status"] = "running"
        state["current_stage"] = stage_key
        state["ended_at"] = None
        state["error"] = ""
        for stage in state["stages"]:
            if stage["key"] == stage_key:
                stage["status"] = "running"
                stage["started_at"] = now
                stage["ended_at"] = None
                stage["summary"] = {}
                break


def complete_stage(project_id: int, stage_key: str, summary: dict | None = None) -> None:
    now = datetime.utcnow()
    with _runtime_lock:
        state = _runtime_state.setdefault(project_id, _empty_runtime(project_id))
        for stage in state["stages"]:
            if stage["key"] == stage_key:
                stage["status"] = "completed"
                stage["ended_at"] = now
                stage["summary"] = dict(summary or {})
                break
        state["current_stage"] = ""


def fail_stage(project_id: int, stage_key: str, error: str) -> None:
    now = datetime.utcnow()
    with _runtime_lock:
        state = _runtime_state.setdefault(project_id, _empty_runtime(project_id))
        for stage in state["stages"]:
            if stage["key"] == stage_key:
                stage["status"] = "failed"
                stage["ended_at"] = now
                stage["summary"] = {"error": error}
                break
        state["run_status"] = "failed"
        state["current_stage"] = stage_key
        state["ended_at"] = now
        state["error"] = error


def complete_pipeline(project_id: int) -> None:
    now = datetime.utcnow()
    with _runtime_lock:
        state = _runtime_state.setdefault(project_id, _empty_runtime(project_id))
        state["run_status"] = "completed"
        state["current_stage"] = ""
        state["ended_at"] = now
        state["error"] = ""


def fail_pipeline(project_id: int, error: str, stage_key: str = "") -> None:
    now = datetime.utcnow()
    with _runtime_lock:
        state = _runtime_state.setdefault(project_id, _empty_runtime(project_id))
        state["run_status"] = "failed"
        state["current_stage"] = stage_key
        state["ended_at"] = now
        state["error"] = error
