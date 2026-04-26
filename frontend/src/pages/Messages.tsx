import { useEffect, useState } from "react";
import { Table, Tag, Spin, Empty } from "antd";
import { api } from "../api/client";
import type { MessageTypeItem, InvariantItem } from "../api/client";
import { useProjectContext } from "../context/ProjectContext";

export default function Messages() {
  const [messageTypes, setMessageTypes] = useState<MessageTypeItem[]>([]);
  const [invariants, setInvariants] = useState<InvariantItem[]>([]);
  const [loading, setLoading] = useState(true);
  const { projectId } = useProjectContext();

  useEffect(() => {
    if (!projectId) {
      setMessageTypes([]);
      setInvariants([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    Promise.all([api.getMessageTypes(projectId), api.getInvariants(projectId)])
      .then(([mt, inv]) => { setMessageTypes(mt); setInvariants(inv); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [projectId]);

  const columns = [
    {
      title: "Name", dataIndex: "name", key: "name",
      render: (name: string) => (
        <span style={{ fontFamily: "var(--font-mono)", color: "var(--accent-cyan)", fontWeight: 600 }}>{name}</span>
      ),
    },
    {
      title: "Template", dataIndex: "template", key: "template",
      render: (t: string) => (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--text-secondary)" }}>{t || "—"}</span>
      ),
    },
    {
      title: "Fields", dataIndex: "fields_json", key: "fields_json",
      render: (json: string) => {
        try {
          const fields = JSON.parse(json);
          const keys = Object.keys(fields);
          if (keys.length === 0) return <span style={{ color: "var(--text-muted)" }}>—</span>;
          return (
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {keys.map((k) => (<Tag key={k} color="blue" style={{ fontSize: 11 }}>{k}: {fields[k]}</Tag>))}
            </div>
          );
        } catch { return <span style={{ color: "var(--text-muted)" }}>—</span>; }
      },
    },
    {
      title: "Confidence", dataIndex: "confidence", key: "confidence", width: 160,
      render: (conf: number) => (
        <div>
          <span style={{ fontSize: 13, fontWeight: 600 }}>{(conf * 100).toFixed(0)}%</span>
          <div className="confidence-bar" style={{ marginTop: 4 }}>
            <div className="confidence-bar-fill"
              style={{ width: `${conf * 100}%`, background: conf > 0.7 ? "var(--gradient-success)" : conf > 0.4 ? "var(--accent-orange)" : "var(--accent-red)" }} />
          </div>
        </div>
      ),
    },
  ];

  if (loading) return <div style={{ textAlign: "center", padding: 100 }}><Spin size="large" /></div>;

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1>Messages &amp; Fields</h1>
        <p>Protocol message types, field structures, constraints, and invariants</p>
      </div>
      {messageTypes.length === 0 ? (
        <div className="glass-card" style={{ textAlign: "center", padding: 80 }}>
          <Empty description="No message types found. Run the Spec Agent first." />
        </div>
      ) : (
        <>
          <div className="glass-card" style={{ marginBottom: 24 }}>
            <h3 style={{ color: "var(--text-secondary)", fontSize: 14, textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 16 }}>
              Message Types ({messageTypes.length})
            </h3>
            <Table dataSource={messageTypes} columns={columns} rowKey="id" pagination={false} size="middle" />
          </div>
          <div className="glass-card">
            <h3 style={{ color: "var(--text-secondary)", fontSize: 14, textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 16 }}>
              Protocol Invariants ({invariants.length})
            </h3>
            {invariants.length === 0 ? (
              <div style={{ color: "var(--text-muted)", padding: 20, textAlign: "center" }}>No invariants discovered yet.</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {invariants.map((inv) => (
                  <div key={inv.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <Tag color="purple" style={{ fontSize: 11 }}>{inv.rule_type}</Tag>
                      <span style={{ fontSize: 14 }}>{inv.rule_text}</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <span className={`status-badge status-${inv.status}`}>{inv.status}</span>
                      <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{(inv.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
