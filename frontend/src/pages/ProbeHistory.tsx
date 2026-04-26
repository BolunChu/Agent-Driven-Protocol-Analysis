import { useEffect, useState } from "react";
import { Spin, Tag, Empty } from "antd";
import { api } from "../api/client";
import type { ProbeItem } from "../api/client";
import { useProjectContext } from "../context/ProjectContext";

export default function ProbeHistory() {
  const [probes, setProbes] = useState<ProbeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const { projectId } = useProjectContext();

  useEffect(() => {
    if (!projectId) {
      setProbes([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    api.getProbes(projectId).then(setProbes).catch(() => {}).finally(() => setLoading(false));
  }, [projectId]);

  if (loading) return <div style={{ textAlign: "center", padding: 100 }}><Spin size="large" /></div>;

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1>Probe History</h1>
        <p>Online probe executions — request/response records and model changes</p>
      </div>
      {probes.length === 0 ? (
        <div className="glass-card" style={{ textAlign: "center", padding: 80 }}>
          <Empty description="No probes executed yet. Run the Probe Agent from Dashboard." />
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {probes.map((probe) => {
            let reqPayload: string[] = [];
            let respPayload: { command: string; response: string }[] = [];
            try { reqPayload = JSON.parse(probe.request_payload); } catch {}
            try { respPayload = JSON.parse(probe.response_payload); } catch {}

            return (
              <div key={probe.id} className="glass-card" style={{ padding: 20 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>{probe.goal}</div>
                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                      Target: {probe.target_host}:{probe.target_port} · {new Date(probe.created_at).toLocaleString()}
                    </div>
                  </div>
                  <Tag color="orange">Probe #{probe.id}</Tag>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                  {/* Request */}
                  <div>
                    <div style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 8 }}>
                      Request Commands
                    </div>
                    <div className="snippet-block">
                      {reqPayload.map((cmd, i) => (
                        <div key={i} style={{ color: "var(--accent-blue)" }}>
                          {">"} {cmd}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Response */}
                  <div>
                    <div style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 8 }}>
                      Exchange Log
                    </div>
                    <div className="snippet-block">
                      {respPayload.map((ex, i) => (
                        <div key={i} style={{ marginBottom: 4 }}>
                          <span style={{ color: "var(--accent-blue)" }}>{ex.command}</span>
                          {ex.response && (
                            <div style={{ color: "var(--text-secondary)", paddingLeft: 12 }}>← {ex.response}</div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div style={{ marginTop: 12, padding: "8px 12px", background: "#f8fafc", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-color)" }}>
                  <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Result: </span>
                  <span style={{ fontSize: 13 }}>{probe.result_summary}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
