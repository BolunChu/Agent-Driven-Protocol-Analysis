import { useEffect, useState } from "react";
import { Spin, Drawer, Tag, Empty } from "antd";
import { api } from "../api/client";
import type { StateItem, TransitionItem, EvidenceItem } from "../api/client";

/* ------------------------------------------------------------------ */
/* SVG-based interactive state-machine graph                          */
/* ------------------------------------------------------------------ */

interface NodePos {
  x: number;
  y: number;
  state: StateItem;
}

const NODE_W = 150;
const NODE_H = 54;
const COLORS: Record<string, string> = {
  INIT: "#60a5fa",
  AUTH_PENDING: "#fb923c",
  AUTHENTICATED: "#34d399",
  DATA_TRANSFER: "#a78bfa",
  CLOSED: "#f87171",
};

function getColor(name: string) {
  return COLORS[name] || "#60a5fa";
}

function layoutNodes(states: StateItem[]): NodePos[] {
  // Arrange nodes in a structured layout
  const positions: Record<string, [number, number]> = {
    INIT: [400, 60],
    AUTH_PENDING: [400, 190],
    AUTHENTICATED: [400, 320],
    DATA_TRANSFER: [650, 320],
    CLOSED: [400, 460],
  };

  const result: NodePos[] = [];
  let extraX = 150;
  let extraY = 100;

  for (const s of states) {
    const pos = positions[s.name];
    if (pos) {
      result.push({ x: pos[0], y: pos[1], state: s });
    } else {
      result.push({ x: extraX, y: extraY, state: s });
      extraX += 180;
      if (extraX > 700) {
        extraX = 150;
        extraY += 120;
      }
    }
  }
  return result;
}

function getEdgePath(
  from: NodePos,
  to: NodePos,
  index: number,
  total: number
): { path: string; labelX: number; labelY: number } {
  const fx = from.x + NODE_W / 2;
  const fy = from.y + NODE_H / 2;
  const tx = to.x + NODE_W / 2;
  const ty = to.y + NODE_H / 2;

  if (from.state.name === to.state.name) {
    // Self-loop
    const r = 30;
    return {
      path: `M ${fx + NODE_W / 2 - 10} ${fy - 5}
             C ${fx + NODE_W / 2 + r} ${fy - r - 30},
               ${fx + NODE_W / 2 + r + 20} ${fy + r - 10},
               ${fx + NODE_W / 2 - 10} ${fy + 15}`,
      labelX: fx + NODE_W / 2 + 45,
      labelY: fy - 10,
    };
  }

  // Curved edge with offset for multiple edges
  const offset = (index - (total - 1) / 2) * 30;
  const midX = (fx + tx) / 2 + offset;
  const midY = (fy + ty) / 2 + offset * 0.3;

  return {
    path: `M ${fx} ${fy} Q ${midX} ${midY} ${tx} ${ty}`,
    labelX: midX,
    labelY: midY - 10,
  };
}

export default function StateMachine() {
  const [states, setStates] = useState<StateItem[]>([]);
  const [transitions, setTransitions] = useState<TransitionItem[]>([]);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<TransitionItem | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const projectId = 1;

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.getStates(projectId),
      api.getTransitions(projectId),
      api.getEvidence(projectId),
    ])
      .then(([s, t, e]) => {
        setStates(s);
        setTransitions(t);
        setEvidence(e);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const nodes = layoutNodes(states);
  const nodeMap = new Map(nodes.map((n) => [n.state.name, n]));

  // Group transitions by from->to for offset calculation
  const edgeGroups = new Map<string, TransitionItem[]>();
  transitions.forEach((t) => {
    const key = [t.from_state, t.to_state].sort().join("|");
    if (!edgeGroups.has(key)) edgeGroups.set(key, []);
    edgeGroups.get(key)!.push(t);
  });

  const handleEdgeClick = (t: TransitionItem) => {
    setSelected(t);
    setDrawerOpen(true);
  };

  const selectedEvidence = selected
    ? evidence.filter((e) => e.claim_type === "transition" && e.claim_id === selected.id)
    : [];

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (states.length === 0) {
    return (
      <div className="fade-in">
        <div className="page-header">
          <h1>State Machine</h1>
          <p>Run the analysis pipeline first to generate the state machine</p>
        </div>
        <div className="glass-card" style={{ textAlign: "center", padding: 80 }}>
          <Empty description="No states found. Run the analysis pipeline from Dashboard." />
        </div>
      </div>
    );
  }

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1>Protocol State Machine</h1>
        <p>
          Interactive state transition graph — click edges to view evidence
        </p>
      </div>

      <div className="graph-container" style={{ padding: 0 }}>
        <svg width="100%" height="560" viewBox="0 0 900 540">
          <defs>
            <marker id="arrow" viewBox="0 0 10 8" refX="9" refY="4"
              markerWidth="8" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 4 L 0 8 z" fill="#60a5fa" opacity="0.7" />
            </marker>
            <marker id="arrow-green" viewBox="0 0 10 8" refX="9" refY="4"
              markerWidth="8" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 4 L 0 8 z" fill="#34d399" opacity="0.9" />
            </marker>
            <marker id="arrow-red" viewBox="0 0 10 8" refX="9" refY="4"
              markerWidth="8" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 4 L 0 8 z" fill="#f87171" opacity="0.9" />
            </marker>
            <filter id="glow">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Edges */}
          {transitions.map((t) => {
            const fromNode = nodeMap.get(t.from_state);
            const toNode = nodeMap.get(t.to_state);
            if (!fromNode || !toNode) return null;

            const key = [t.from_state, t.to_state].sort().join("|");
            const group = edgeGroups.get(key) || [t];
            const groupIdx = group.indexOf(t);

            const { path, labelX, labelY } = getEdgePath(
              fromNode, toNode, groupIdx, group.length
            );

            const edgeColor =
              t.status === "supported" ? "#34d399" :
              t.status === "disputed" ? "#f87171" : "#60a5fa";

            const markerEnd =
              t.status === "supported" ? "url(#arrow-green)" :
              t.status === "disputed" ? "url(#arrow-red)" : "url(#arrow)";

            return (
              <g key={t.id} onClick={() => handleEdgeClick(t)} style={{ cursor: "pointer" }}>
                <path
                  d={path}
                  stroke={edgeColor}
                  strokeWidth={selected?.id === t.id ? 3 : 1.5}
                  fill="none"
                  opacity={selected?.id === t.id ? 1 : 0.6}
                  markerEnd={markerEnd}
                  className="edge-line"
                />
                {/* Invisible wider path for easier clicking */}
                <path d={path} stroke="transparent" strokeWidth={15} fill="none" />
                <text x={labelX} y={labelY} textAnchor="middle" className="edge-label"
                  style={{ fontSize: 11, fill: edgeColor }}>
                  {t.message_type}
                </text>
                <text x={labelX} y={labelY + 14} textAnchor="middle"
                  style={{ fontSize: 9, fill: "var(--text-muted)" }}>
                  {(t.confidence * 100).toFixed(0)}%
                </text>
              </g>
            );
          })}

          {/* Nodes */}
          {nodes.map((n) => {
            const color = getColor(n.state.name);
            return (
              <g key={n.state.name} className="state-node">
                <rect
                  className="node-bg"
                  x={n.x} y={n.y}
                  width={NODE_W} height={NODE_H}
                  rx={12} ry={12}
                  fill="var(--bg-card)"
                  stroke={color}
                  strokeWidth={1.5}
                  filter="url(#glow)"
                />
                {/* Top accent line */}
                <rect
                  x={n.x + 1} y={n.y + 1}
                  width={NODE_W - 2} height={3}
                  rx={12} ry={2}
                  fill={color}
                  opacity={0.8}
                />
                <text
                  x={n.x + NODE_W / 2}
                  y={n.y + NODE_H / 2 + 2}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  style={{ fill: color, fontSize: 13, fontWeight: 600, fontFamily: "var(--font-mono)" }}
                >
                  {n.state.name}
                </text>
                <text
                  x={n.x + NODE_W / 2}
                  y={n.y + NODE_H / 2 + 17}
                  textAnchor="middle"
                  style={{ fill: "var(--text-muted)", fontSize: 9 }}
                >
                  conf: {(n.state.confidence * 100).toFixed(0)}%
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Legend */}
      <div style={{ display: "flex", gap: 24, marginTop: 16, justifyContent: "center" }}>
        <LegendItem color="#60a5fa" label="Hypothesis" />
        <LegendItem color="#34d399" label="Supported" />
        <LegendItem color="#f87171" label="Disputed" />
      </div>

      {/* Edge Detail Drawer */}
      <Drawer
        title={
          selected
            ? `${selected.from_state} → ${selected.to_state}`
            : "Transition Detail"
        }
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={480}
        styles={{
          header: { background: "var(--bg-secondary)", borderBottom: "1px solid var(--border-color)", color: "var(--text-primary)" },
          body: { background: "var(--bg-secondary)", color: "var(--text-primary)" },
        }}
      >
        {selected && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <div>
              <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 4 }}>
                MESSAGE TYPE
              </div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 16, color: "var(--accent-blue)" }}>
                {selected.message_type}
              </div>
            </div>

            <div style={{ display: "flex", gap: 16 }}>
              <div>
                <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 4 }}>STATUS</div>
                <span className={`status-badge status-${selected.status}`}>
                  {selected.status}
                </span>
              </div>
              <div>
                <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 4 }}>CONFIDENCE</div>
                <div style={{ fontWeight: 600 }}>{(selected.confidence * 100).toFixed(1)}%</div>
                <div className="confidence-bar" style={{ width: 120, marginTop: 4 }}>
                  <div
                    className="confidence-bar-fill"
                    style={{
                      width: `${selected.confidence * 100}%`,
                      background:
                        selected.confidence > 0.7
                          ? "var(--gradient-success)"
                          : selected.confidence > 0.4
                          ? "var(--accent-orange)"
                          : "var(--accent-red)",
                    }}
                  />
                </div>
              </div>
            </div>

            <div>
              <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 8 }}>
                EVIDENCE ({selectedEvidence.length})
              </div>
              {selectedEvidence.length === 0 ? (
                <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
                  No evidence bound to this transition.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {selectedEvidence.map((e) => (
                    <div
                      key={e.id}
                      style={{
                        background: "#f8fafc",
                        border: "1px solid var(--border-color)",
                        borderRadius: "var(--radius-sm)",
                        padding: 12,
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                        <Tag color={e.source_type === "doc" ? "blue" : e.source_type === "trace" ? "green" : e.source_type === "probe" ? "orange" : "purple"}>
                          {e.source_type}
                        </Tag>
                        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                          score: {e.score.toFixed(2)}
                        </span>
                      </div>
                      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4 }}>
                        {e.source_ref}
                      </div>
                      <div className="snippet-block" style={{ fontSize: 12, marginTop: 6 }}>
                        {e.snippet}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div
        style={{
          width: 24,
          height: 3,
          background: color,
          borderRadius: 2,
        }}
      />
      <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{label}</span>
    </div>
  );
}
