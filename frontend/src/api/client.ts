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
