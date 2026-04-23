import { useEffect, useState } from "react";
import { Button, Spin, message, Select } from "antd";
import {
  ThunderboltOutlined,
  PlayCircleOutlined,
  ExportOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";
import type { DashboardStats, Project } from "../api/client";

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    api.listProjects().then((p) => {
      setProjects(p);
      if (p.length > 0) setProjectId(p[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (projectId) {
      setLoading(true);
      api.getDashboard(projectId).then(setStats).finally(() => setLoading(false));
    }
  }, [projectId]);

  const handleRunPipeline = async () => {
    if (!projectId) return;
    setRunning(true);
    try {
      await api.runPipeline(projectId);
      message.success("Pipeline completed successfully!");
      const s = await api.getDashboard(projectId);
      setStats(s);
    } catch (err: any) {
      message.error(err.message || "Pipeline failed");
    }
    setRunning(false);
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

  return (
    <div className="fade-in">
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1>Dashboard</h1>
          <p>Protocol analysis overview and control panel</p>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <Select
            value={projectId}
            onChange={setProjectId}
            style={{ width: 260 }}
            placeholder="Select Project"
            options={projects.map((p) => ({ label: `${p.name} (${p.protocol_name})`, value: p.id }))}
          />
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
                  <AgentButton key={i} {...agent} projectId={projectId} onDone={() => api.getDashboard(projectId!).then(setStats)} />
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
  label: string; desc: string; fn: () => Promise<any>; projectId: number | null; onDone: () => void;
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
