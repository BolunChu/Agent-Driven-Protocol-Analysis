const BASE = "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export interface Project {
  id: number;
  name: string;
  protocol_name: string;
  description: string;
  created_at: string;
}

export interface DashboardStats {
  project_name: string;
  protocol_name: string;
  message_type_count: number;
  state_count: number;
  transition_count: number;
  invariant_count: number;
  probe_count: number;
  disputed_count: number;
}

export interface PipelineStageStatus {
  key: string;
  label: string;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  summary: Record<string, unknown>;
}

export interface PipelineRuntime {
  project_id: number;
  run_status: string;
  current_stage: string;
  started_at: string | null;
  ended_at: string | null;
  error: string;
  stages: PipelineStageStatus[];
}

export interface ArtifactSummary {
  schema_message_count: number;
  seed_count: number;
  feedback_action_count: number;
  recommended_actions: string[];
  focus_commands: string[];
  unused_message_types: string[];
}

export interface AgentPath {
  spec_fallback: boolean;
  trace_fallback: boolean;
  spec_llm_calls: number;
  trace_llm_calls: number;
  probe_llm_calls: number;
  transition_provenance_agent: number;
  transition_provenance_fallback: number;
  transition_provenance_mixed: number;
  // Granular source breakdown
  probe_evidence_count: number;
  llm_evidence_count: number;
  // Transition status distribution
  transition_supported: number;
  transition_hypothesis: number;
  transition_disputed: number;
}

export interface AnalysisSummary {
  dashboard: DashboardStats;
  runtime: PipelineRuntime;
  artifacts: ArtifactSummary;
  agent_path: AgentPath;
}

export interface StateItem {
  id: number;
  project_id: number;
  name: string;
  description: string;
  confidence: number;
}

export interface TransitionItem {
  id: number;
  project_id: number;
  from_state: string;
  to_state: string;
  message_type: string;
  confidence: number;
  status: string;
}

export interface MessageTypeItem {
  id: number;
  project_id: number;
  name: string;
  template: string;
  fields_json: string;
  confidence: number;
}

export interface InvariantItem {
  id: number;
  project_id: number;
  rule_text: string;
  rule_type: string;
  confidence: number;
  status: string;
}

export interface EvidenceItem {
  id: number;
  project_id: number;
  claim_type: string;
  claim_id: number;
  source_type: string;
  source_ref: string;
  snippet: string;
  score: number;
}

export interface ProbeItem {
  id: number;
  project_id: number;
  target_host: string;
  target_port: number;
  goal: string;
  request_payload: string;
  response_payload: string;
  result_summary: string;
  created_at: string;
}

// API functions
export const api = {
  listProjects: () => request<Project[]>("/projects"),
  getProject: (id: number) => request<Project>(`/projects/${id}`),
  createProject: (data: { name: string; protocol_name: string; description?: string }) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(data) }),

  getDashboard: (id: number) => request<DashboardStats>(`/projects/${id}/dashboard`),
  getRuntime: (id: number) => request<PipelineRuntime>(`/projects/${id}/runtime`),
  getAnalysisSummary: (id: number) => request<AnalysisSummary>(`/projects/${id}/analysis-summary`),
  getStates: (id: number) => request<StateItem[]>(`/projects/${id}/states`),
  getTransitions: (id: number) => request<TransitionItem[]>(`/projects/${id}/transitions`),
  getMessageTypes: (id: number) => request<MessageTypeItem[]>(`/projects/${id}/message-types`),
  getInvariants: (id: number) => request<InvariantItem[]>(`/projects/${id}/invariants`),
  getEvidence: (id: number) => request<EvidenceItem[]>(`/projects/${id}/evidence`),
  getProbes: (id: number) => request<ProbeItem[]>(`/projects/${id}/probes`),

  importDoc: (id: number, content: string) =>
    request(`/projects/${id}/import/doc`, {
      method: "POST",
      body: JSON.stringify({ source_type: "doc", raw_content: content }),
    }),
  importTrace: (id: number, content: string) =>
    request(`/projects/${id}/import/trace`, {
      method: "POST",
      body: JSON.stringify({ source_type: "trace", raw_content: content }),
    }),

  runSpecAgent: (id: number) => request(`/projects/${id}/run/spec-agent`, { method: "POST" }),
  runTraceAgent: (id: number) => request(`/projects/${id}/run/trace-agent`, { method: "POST" }),
  runVerifier: (id: number) => request(`/projects/${id}/run/verifier`, { method: "POST" }),
  runProbe: (id: number) => request(`/projects/${id}/run/probe`, { method: "POST" }),
  runPipeline: (id: number) => request(`/projects/${id}/run/full-pipeline`, { method: "POST" }),

  exportModel: (id: number) => request(`/projects/${id}/model/export`),
};
