import { useEffect, useState } from "react";
import { Button, Spin, message, Tag, Tooltip } from "antd";
import {
  ThunderboltOutlined,
  PlayCircleOutlined,
  ExportOutlined,
  RobotOutlined,
  ApiOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";
import type { AnalysisSummary, AgentPath } from "../api/client";
import { useProjectContext } from "../context/ProjectContext";

export default function Dashboard() {
  const [summary, setSummary] = useState<AnalysisSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const { projectId } = useProjectContext();

  useEffect(() => {
    if (projectId) {
      setLoading(true);
      api.getAnalysisSummary(projectId).then(setSummary).finally(() => setLoading(false));
    }
  }, [projectId]);

  const handleRunPipeline = async () => {
    if (!projectId) return;
    setRunning(true);
    const timer = window.setInterval(() => {
      api.getAnalysisSummary(projectId).then(setSummary).catch(() => {});
    }, 1500);
    try {
      await api.getAnalysisSummary(projectId).then(setSummary).catch(() => {});
      await api.runPipeline(projectId);
      message.success("Pipeline completed successfully!");
      const s = await api.getAnalysisSummary(projectId);
      setSummary(s);
    } catch (err: any) {
      message.error(err.message || "Pipeline failed");
      api.getAnalysisSummary(projectId).then(setSummary).catch(() => {});
    } finally {
      window.clearInterval(timer);
      setRunning(false);
    }
  };

  const handleExport = async () => {
    if (!projectId) return;
    try {
      const data = await api.exportModel(projectId);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `protocol_model_${projectId}.json`;
      a.click();
      URL.revokeObjectURL(url);
      message.success("Model exported!");
    } catch (err: any) {
      message.error(err.message);
    }
  };

  const stats = summary?.dashboard ?? null;
  const runtime = summary?.runtime ?? null;
  const artifacts = summary?.artifacts ?? null;
  const agentPath = summary?.agent_path ?? null;

  const statCards = stats
    ? [
        { label: "Message Types", value: stats.message_type_count, color: "#60a5fa" },
        { label: "States", value: stats.state_count, color: "#a78bfa" },
        { label: "Transitions", value: stats.transition_count, color: "#22d3ee" },
        { label: "Invariants", value: stats.invariant_count, color: "#34d399" },
        { label: "Probe Runs", value: stats.probe_count, color: "#fb923c" },
        { label: "Disputed", value: stats.disputed_count, color: "#f87171" },
      ]
    : [];

  const statusColor =
    runtime?.run_status === "completed"
      ? "green"
      : runtime?.run_status === "failed"
        ? "red"
        : runtime?.run_status === "running"
          ? "blue"
          : "default";

  return (
    <div className="fade-in">
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1>Dashboard</h1>
          <p>Protocol analysis overview and control panel</p>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={handleRunPipeline}
            loading={running}
            style={{ background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)", border: "none", height: 36 }}
          >
            Run Pipeline
          </Button>
          <Button
            icon={<ExportOutlined />}
            onClick={handleExport}
            style={{ background: "var(--bg-card)", border: "1px solid var(--border-color)", color: "var(--text-primary)", height: 36 }}
          >
            Export
          </Button>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: 80 }}>
          <Spin size="large" />
        </div>
      ) : stats ? (
        <>
          <div className="glass-card" style={{ marginBottom: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
              <div>
                <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6 }}>Pipeline Runtime</div>
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <Tag color={statusColor}>{runtime?.run_status || "idle"}</Tag>
                  {runtime?.current_stage ? (
                    <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>Current stage: {runtime.current_stage}</span>
                  ) : null}
                  {runtime?.error ? (
                    <span style={{ fontSize: 13, color: "#f87171" }}>{runtime.error}</span>
                  ) : null}
                </div>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
                {(runtime?.stages || []).map((stage) => (
                  <Tag
                    key={stage.key}
                    color={stage.status === "completed" ? "green" : stage.status === "failed" ? "red" : stage.status === "running" ? "blue" : "default"}
                  >
                    {stage.label}
                  </Tag>
                ))}
              </div>
            </div>
          </div>

          <div className="stats-grid">
            {statCards.map((card, i) => (
              <div key={i} className="stat-card" style={{ animationDelay: `${i * 0.05}s` }}>
                <div className="stat-value" style={{ background: `linear-gradient(135deg, ${card.color}, ${card.color}cc)`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                  {card.value}
                </div>
                <div className="stat-label">{card.label}</div>
              </div>
            ))}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 8 }}>
            <div className="glass-card">
              <h3 style={{ color: "var(--text-secondary)", fontSize: 14, textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 16 }}>
                <ThunderboltOutlined style={{ marginRight: 8, color: "var(--accent-purple)" }} />
                Run Individual Agents
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {[
                  { label: "Spec Agent", desc: "Extract from docs", fn: () => api.runSpecAgent(projectId!) },
                  { label: "Trace Agent", desc: "Analyze traces", fn: () => api.runTraceAgent(projectId!) },
                  { label: "Verifier", desc: "Score evidence", fn: () => api.runVerifier(projectId!) },
                  { label: "Probe Agent", desc: "Online probing", fn: () => api.runProbe(projectId!) },
                ].map((agent, i) => (
                  <AgentButton
                    key={i}
                    label={agent.label}
                    desc={agent.desc}
                    fn={agent.fn}
                    projectId={projectId}
                    onDone={() => api.getAnalysisSummary(projectId!).then(setSummary)}
                  />
                ))}
              </div>
            </div>

            <div className="glass-card">
              <h3 style={{ color: "var(--text-secondary)", fontSize: 14, textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 16 }}>
                Project Info
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <InfoRow label="Project" value={stats.project_name} />
                <InfoRow label="Protocol" value={stats.protocol_name} />
                <InfoRow label="Coverage" value={`${stats.state_count} states, ${stats.transition_count} transitions`} />
                <InfoRow label="Schema / Seeds" value={`${artifacts?.schema_message_count || 0} schema msgs · ${artifacts?.seed_count || 0} seeds`} />
                <InfoRow
                  label="Health"
                  value={
                    stats.disputed_count === 0
                      ? "✅ No disputed claims"
                      : `⚠️ ${stats.disputed_count} disputed claim(s)`
                  }
                />
              </div>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>
            <div className="glass-card">
              <h3 style={{ color: "var(--text-secondary)", fontSize: 14, textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 16 }}>
                Artifact Summary
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <InfoRow label="Schema Messages" value={String(artifacts?.schema_message_count || 0)} />
                <InfoRow label="Generated Seeds" value={String(artifacts?.seed_count || 0)} />
                <InfoRow label="Feedback Actions" value={String(artifacts?.feedback_action_count || 0)} />
                <div>
                  <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 8 }}>Focus Commands</div>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {(artifacts?.focus_commands || []).map((command) => (
                      <Tag key={command} color="blue">{command}</Tag>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="glass-card">
              <h3 style={{ color: "var(--text-secondary)", fontSize: 14, textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 16 }}>
                Recommended Next Actions
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {(artifacts?.recommended_actions || []).length === 0 ? (
                  <div style={{ color: "var(--text-muted)", fontSize: 13 }}>No recommendations available yet. Run the full pipeline first.</div>
                ) : (
                  (artifacts?.recommended_actions || []).map((item, index) => (
                    <div key={index} style={{ padding: "10px 12px", background: "var(--bg-secondary)", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-color)", fontSize: 13 }}>
                      {item}
                    </div>
                  ))
                )}
                {(artifacts?.unused_message_types || []).length > 0 ? (
                  <div>
                    <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 8 }}>Still Unmodeled Messages</div>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      {(artifacts?.unused_message_types || []).slice(0, 10).map((item) => (
                        <Tag key={item}>{item}</Tag>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
          {/* Agent Path + Provenance */}
          <div style={{ marginTop: 16 }}>
            <AgentPathPanel agentPath={agentPath} />
          </div>

        </>
      ) : (
        <div className="glass-card" style={{ textAlign: "center", padding: 60 }}>
          <p style={{ color: "var(--text-muted)", fontSize: 16 }}>
            No project selected. Create a project and import data to begin.
          </p>
        </div>
      )}
    </div>
  );
}

function AgentButton({ label, desc, fn, projectId, onDone }: {
  label: string; desc: string; fn: () => Promise<any>; projectId: number | null; onDone: () => void | Promise<void>;
}) {
  const [loading, setLoading] = useState(false);
  const handleClick = async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      await fn();
      message.success(`${label} completed`);
      onDone();
    } catch (err: any) {
      message.error(err.message);
    }
    setLoading(false);
  };
  return (
    <div
      style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: "10px 14px", background: "var(--bg-secondary)", borderRadius: "var(--radius-sm)",
        border: "1px solid var(--border-color)",
      }}
    >
      <div>
        <div style={{ fontWeight: 600, fontSize: 14 }}>{label}</div>
        <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{desc}</div>
      </div>
      <Button size="small" loading={loading} onClick={handleClick}
        style={{ background: "var(--bg-card)", border: "1px solid var(--border-color)", color: "var(--text-primary)" }}>
        Run
      </Button>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between" }}>
      <span style={{ color: "var(--text-muted)", fontSize: 13 }}>{label}</span>
      <span style={{ fontWeight: 500, fontSize: 13 }}>{value}</span>
    </div>
  );
}

function AgentPathPanel({ agentPath }: { agentPath: AgentPath | null }) {
  if (!agentPath) return null;

  const total =
    agentPath.transition_provenance_agent +
    agentPath.transition_provenance_fallback +
    agentPath.transition_provenance_mixed;

  const agentPct = total > 0 ? Math.round((agentPath.transition_provenance_agent / total) * 100) : 0;
  const fallbackPct = total > 0 ? Math.round((agentPath.transition_provenance_fallback / total) * 100) : 0;
  const mixedPct = total > 0 ? Math.round((agentPath.transition_provenance_mixed / total) * 100) : 0;

  const statusTotal = agentPath.transition_supported + agentPath.transition_hypothesis + agentPath.transition_disputed;
  const supportedPct = statusTotal > 0 ? Math.round((agentPath.transition_supported / statusTotal) * 100) : 0;
  const hypothesisPct = statusTotal > 0 ? Math.round((agentPath.transition_hypothesis / statusTotal) * 100) : 0;
  const disputedPct = statusTotal > 0 ? Math.round((agentPath.transition_disputed / statusTotal) * 100) : 0;

  const agents = [
    { label: "Spec Agent", calls: agentPath.spec_llm_calls, fallback: agentPath.spec_fallback, icon: <RobotOutlined /> },
    { label: "Trace Agent", calls: agentPath.trace_llm_calls, fallback: agentPath.trace_fallback, icon: <RobotOutlined /> },
    { label: "Probe Agent", calls: agentPath.probe_llm_calls, fallback: false, icon: <ApiOutlined /> },
  ];

  return (
    <div className="glass-card">
      <h3 style={{ color: "var(--text-secondary)", fontSize: 14, textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 16 }}>
        <RobotOutlined style={{ marginRight: 8, color: "#a78bfa" }} />
        Agent Path Signals
      </h3>

      {/* Per-agent LLM calls + fallback */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 20 }}>
        {agents.map((ag) => (
          <div
            key={ag.label}
            style={{
              padding: "10px 12px",
              background: "var(--bg-secondary)",
              borderRadius: "var(--radius-sm)",
              border: `1px solid ${ag.fallback ? "#f87171" : ag.calls > 0 ? "#34d399" : "var(--border-color)"}`,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <span style={{ fontSize: 12, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 5 }}>
                {ag.icon} {ag.label}
              </span>
              <Tooltip title={ag.fallback ? "Fell back to heuristic rules" : ag.calls > 0 ? "Used LLM tool calls" : "Not yet run"}>
                <Tag
                  color={ag.fallback ? "red" : ag.calls > 0 ? "green" : "default"}
                  style={{ fontSize: 10, padding: "0 5px", cursor: "help" }}
                >
                  {ag.fallback ? "fallback" : ag.calls > 0 ? "agent" : "idle"}
                </Tag>
              </Tooltip>
            </div>
            <div style={{ fontWeight: 700, fontSize: 22, color: ag.calls > 0 ? "#60a5fa" : "var(--text-muted)" }}>
              {ag.calls}
            </div>
            <div style={{ fontSize: 11, color: "var(--text-muted)" }}>LLM tool calls</div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Transition provenance bar */}
        <div>
          <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 10 }}>
            Transition Provenance ({total} transitions)
          </div>
          {total > 0 ? (
            <>
              <div style={{ display: "flex", height: 10, borderRadius: 5, overflow: "hidden", marginBottom: 8 }}>
                {agentPct > 0 && (
                  <div style={{ width: `${agentPct}%`, background: "#34d399", transition: "width 0.5s" }} />
                )}
                {mixedPct > 0 && (
                  <div style={{ width: `${mixedPct}%`, background: "#f59e0b", transition: "width 0.5s" }} />
                )}
                {fallbackPct > 0 && (
                  <div style={{ width: `${fallbackPct}%`, background: "#f87171", transition: "width 0.5s" }} />
                )}
              </div>
              <div style={{ display: "flex", gap: 12, fontSize: 12, flexWrap: "wrap" }}>
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: "#34d399", display: "inline-block" }} />
                  Agent {agentPct}% ({agentPath.transition_provenance_agent})
                </span>
                {mixedPct > 0 && (
                  <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <span style={{ width: 10, height: 10, borderRadius: 2, background: "#f59e0b", display: "inline-block" }} />
                    Mixed {mixedPct}% ({agentPath.transition_provenance_mixed})
                  </span>
                )}
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: "#f87171", display: "inline-block" }} />
                  Fallback {fallbackPct}% ({agentPath.transition_provenance_fallback})
                </span>
              </div>
            </>
          ) : (
            <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
              No transitions yet — run the full pipeline first.
            </div>
          )}
        </div>

        {/* Transition verification status */}
        <div>
          <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 10 }}>
            Verification Status ({statusTotal} transitions)
          </div>
          {statusTotal > 0 ? (
            <>
              <div style={{ display: "flex", height: 10, borderRadius: 5, overflow: "hidden", marginBottom: 8 }}>
                {supportedPct > 0 && (
                  <div style={{ width: `${supportedPct}%`, background: "#34d399", transition: "width 0.5s" }} />
                )}
                {hypothesisPct > 0 && (
                  <div style={{ width: `${hypothesisPct}%`, background: "#f59e0b", transition: "width 0.5s" }} />
                )}
                {disputedPct > 0 && (
                  <div style={{ width: `${disputedPct}%`, background: "#f87171", transition: "width 0.5s" }} />
                )}
              </div>
              <div style={{ display: "flex", gap: 12, fontSize: 12, flexWrap: "wrap" }}>
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: "#34d399", display: "inline-block" }} />
                  Supported {supportedPct}% ({agentPath.transition_supported})
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: "#f59e0b", display: "inline-block" }} />
                  Hypothesis {hypothesisPct}% ({agentPath.transition_hypothesis})
                </span>
                {disputedPct > 0 && (
                  <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <span style={{ width: 10, height: 10, borderRadius: 2, background: "#f87171", display: "inline-block" }} />
                    Disputed {disputedPct}% ({agentPath.transition_disputed})
                  </span>
                )}
              </div>
            </>
          ) : (
            <div style={{ color: "var(--text-muted)", fontSize: 13 }}>No transitions yet.</div>
          )}
          <div style={{ marginTop: 12, fontSize: 12, color: "var(--text-muted)", display: "flex", gap: 12 }}>
            <span>🤖 LLM evidence: <b style={{ color: "var(--text-primary)" }}>{agentPath.llm_evidence_count}</b></span>
            <span>🔍 Probe evidence: <b style={{ color: "var(--text-primary)" }}>{agentPath.probe_evidence_count}</b></span>
          </div>
        </div>
      </div>
    </div>
  );
}
