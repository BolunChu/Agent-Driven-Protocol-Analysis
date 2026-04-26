import { useEffect, useState } from "react";
import { Spin, Tag, Empty } from "antd";
import { api } from "../api/client";
import type { EvidenceItem, TransitionItem, InvariantItem } from "../api/client";
import { useProjectContext } from "../context/ProjectContext";

export default function EvidenceChain() {
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [transitions, setTransitions] = useState<TransitionItem[]>([]);
  const [invariants, setInvariants] = useState<InvariantItem[]>([]);
  const [loading, setLoading] = useState(true);
  const { projectId } = useProjectContext();

  useEffect(() => {
    if (!projectId) {
      setEvidence([]);
      setTransitions([]);
      setInvariants([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    Promise.all([api.getEvidence(projectId), api.getTransitions(projectId), api.getInvariants(projectId)])
      .then(([e, t, i]) => { setEvidence(e); setTransitions(t); setInvariants(i); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [projectId]);

  // Group evidence by claim
  const groups = new Map<string, { label: string; status: string; items: EvidenceItem[] }>();
  evidence.forEach((e) => {
    const key = `${e.claim_type}:${e.claim_id}`;
    if (!groups.has(key)) {
      let label = `${e.claim_type} #${e.claim_id}`;
      let status = "hypothesis";
      if (e.claim_type === "transition") {
        const t = transitions.find((t) => t.id === e.claim_id);
        if (t) { label = `${t.from_state} → ${t.to_state} via ${t.message_type}`; status = t.status; }
      } else if (e.claim_type === "invariant") {
        const inv = invariants.find((i) => i.id === e.claim_id);
        if (inv) { label = inv.rule_text; status = inv.status; }
      }
      groups.set(key, { label, status, items: [] });
    }
    groups.get(key)!.items.push(e);
  });

  if (loading) return <div style={{ textAlign: "center", padding: 100 }}><Spin size="large" /></div>;

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1>Evidence Chain</h1>
        <p>Evidence records grouped by claim — trace the reasoning behind every conclusion</p>
      </div>
      {groups.size === 0 ? (
        <div className="glass-card" style={{ textAlign: "center", padding: 80 }}>
          <Empty description="No evidence found. Run the analysis pipeline first." />
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {Array.from(groups.entries()).map(([key, group]) => (
            <div key={key} className="glass-card" style={{ padding: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 15, fontWeight: 600 }}>{group.label}</span>
                </div>
                <span className={`status-badge status-${group.status}`}>{group.status}</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {group.items.map((e) => (
                  <div key={e.id} style={{ display: "flex", gap: 12, padding: "10px 14px", background: "#f8fafc", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-color)" }}>
                    <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 80 }}>
                      <Tag color={e.source_type === "doc" ? "blue" : e.source_type === "trace" ? "green" : e.source_type === "probe" ? "orange" : "purple"}>
                        {e.source_type}
                      </Tag>
                      <span style={{ fontSize: 11, color: "var(--text-muted)" }}>score: {e.score.toFixed(2)}</span>
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4 }}>{e.source_ref}</div>
                      <div className="snippet-block" style={{ fontSize: 12 }}>{e.snippet}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
