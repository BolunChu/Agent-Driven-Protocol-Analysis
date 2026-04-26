import { useEffect, useState } from "react";
import { Spin, Drawer, Tag, Empty } from "antd";
import { api } from "../api/client";
import type { StateItem, TransitionItem, EvidenceItem } from "../api/client";
import { useProjectContext } from "../context/ProjectContext";

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
const HORIZONTAL_SPACING = 280;
const VERTICAL_SPACING = 140;

// Core states shared/common across protocols
const COLORS: Record<string, string> = {
  // Common
  INIT:             "#60a5fa",
  CLOSED:           "#f87171",
  ERROR:            "#f87171",

  // FTP
  AUTH_PENDING:         "#fb923c",
  AUTHENTICATED:        "#34d399",
  DATA_CHANNEL_READY:   "#22d3ee",
  DATA_TRANSFER:        "#a78bfa",
  RESETTING:            "#f59e0b",

  // SMTP
  CONNECTED:            "#60a5fa",
  GREETED:              "#818cf8",
  MAIL_TRANSACTION:     "#34d399",
  RCPT_COLLECTING:      "#22d3ee",
  DATA_RECEIVING:       "#a78bfa",
  MAIL_SENT:            "#f59e0b",
  AUTH_REQUIRED:        "#fb923c",

  // RTSP
  OPTIONS_SENT:         "#38bdf8",
  DESCRIBED:            "#818cf8",
  SETUP:                "#34d399",
  PLAYING:              "#4ade80",
  PAUSED:               "#f59e0b",
  TEARDOWN:             "#f87171",

  // HTTP
  REQUEST_RECEIVED:     "#38bdf8",
  PROCESSING:           "#818cf8",
  RESPONDED:            "#34d399",
  REDIRECT:             "#f59e0b",
  AUTH_CHALLENGED:      "#fb923c",
};

const PALETTE = [
  "#60a5fa", "#a78bfa", "#34d399", "#22d3ee", "#fb923c",
  "#f59e0b", "#818cf8", "#38bdf8", "#4ade80", "#e879f9",
];

function hashColor(name: string): string {
  let h = 5381;
  for (let i = 0; i < name.length; i++) h = ((h << 5) + h) ^ name.charCodeAt(i);
  return PALETTE[Math.abs(h) % PALETTE.length];
}

function getColor(name: string) {
  return COLORS[name] || hashColor(name);
}

function layoutNodes(states: StateItem[]): NodePos[] {
  const basePositions: Record<string, [number, number]> = {
    INIT: [1.5, 0.5], AUTH_PENDING: [1.5, 1.5], AUTHENTICATED: [1.5, 2.5],
    DATA_CHANNEL_READY: [2.5, 1.8], DATA_TRANSFER: [2.5, 2.8],
    RESETTING: [0.5, 2.5], CLOSED: [1.5, 3.8],
    CONNECTED: [1.5, 0.5], GREETED: [1.5, 1.3], MAIL_TRANSACTION: [1.5, 2.5],
    RCPT_COLLECTING: [2.5, 1.8], DATA_RECEIVING: [2.5, 3.0], MAIL_SENT: [1.5, 3.8],
    AUTH_REQUIRED: [0.5, 1.3],
    OPTIONS_SENT: [1.5, 0.6], DESCRIBED: [1.5, 1.6], SETUP: [1.5, 2.6],
    PLAYING: [2.5, 2.0], PAUSED: [2.5, 3.2], TEARDOWN: [1.5, 3.8],
    REQUEST_RECEIVED: [1.5, 0.6], PROCESSING: [1.5, 1.7], RESPONDED: [1.5, 2.8],
    REDIRECT: [2.5, 1.8], AUTH_CHALLENGED: [0.5, 1.8], ERROR: [0.5, 3.0],
  };
  const placed: NodePos[] = [];
  const extras: StateItem[] = [];
  for (const s of states) {
    const coords = basePositions[s.name];
    if (coords) {
      placed.push({ x: coords[0] * HORIZONTAL_SPACING, y: coords[1] * VERTICAL_SPACING, state: s });
    } else {
      extras.push(s);
    }
  }
  let col = 0;
  const startX = 100;
  const startY = 600;
  for (const s of extras) {
    placed.push({ x: startX + (col % 4) * 220, y: startY + Math.floor(col / 4) * 120, state: s });
    col++;
  }
  return placed;
}

interface EdgeControl {
  x: number;
  y: number;
}

function getEdgePath(
  from: NodePos,
  to: NodePos,
  index: number,
  total: number,
  customControl?: EdgeControl
): { path: string; labelX: number; labelY: number; controlX: number; controlY: number } {
  const fx = from.x + NODE_W / 2;
  const fy = from.y + NODE_H / 2;
  const tx = to.x + NODE_W / 2;
  const ty = to.y + NODE_H / 2;

  if (from.state.name === to.state.name) {
    const r = 35 + index * 15;
    const sweep = 1;
    const largeArc = 1;
    const x1 = fx + NODE_W / 2 - 10;
    const y1 = fy - 5;
    const x2 = fx + NODE_W / 2 - 10;
    const y2 = fy + 15;
    return {
      path: `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} ${sweep} ${x2} ${y2}`,
      labelX: fx + NODE_W / 2 + r + 5,
      labelY: fy + 5,
      controlX: fx + NODE_W / 2 + r,
      controlY: fy + 5,
    };
  }

  let midX, midY;
  const dx = tx - fx;
  const dy = ty - fy;
  const len = Math.sqrt(dx * dx + dy * dy) || 1;
  const nx = -dy / len; 
  const ny = dx / len;  

  if (customControl) {
    midX = customControl.x;
    midY = customControl.y;
  } else {
    const spread = 30;
    const dist = (index - (total - 1) / 2) * spread;
    midX = (fx + tx) / 2 + nx * dist;
    midY = (fy + ty) / 2 + ny * dist;
  }

  const t = 0.5; // Fixed midpoint for 3-point arc visual
  const invT = 1 - t;
  const lx = invT * invT * fx + 2 * invT * t * midX + t * t * tx;
  const ly = invT * invT * fy + 2 * invT * t * midY + t * t * ty;

  return {
    path: `M ${fx} ${fy} Q ${midX} ${midY} ${tx} ${ty}`,
    labelX: lx + nx * 5,
    labelY: ly + ny * 5,
    controlX: midX,
    controlY: midY,
  };
}

export default function StateMachine() {
  const [states, setStates] = useState<StateItem[]>([]);
  const [transitions, setTransitions] = useState<TransitionItem[]>([]);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<TransitionItem | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { projectId } = useProjectContext();

  // Draggable state
  const [nodes, setNodes] = useState<NodePos[]>([]);
  const [edgeControls, setEdgeControls] = useState<Record<number, EdgeControl>>({});
  const [draggingNode, setDraggingNode] = useState<string | null>(null);
  const [draggingEdge, setDraggingEdge] = useState<number | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  useEffect(() => {
    if (!projectId) {
      setStates([]);
      setTransitions([]);
      setEvidence([]);
      setNodes([]);
      setEdgeControls({});
      setLoading(false);
      return;
    }
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
        setNodes(layoutNodes(s));
        setEdgeControls({}); 
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [projectId]);

  const nodeMap = new Map(nodes.map((n) => [n.state.name, n]));

  const edgeGroups = new Map<string, TransitionItem[]>();
  transitions.forEach((t) => {
    const key = [t.from_state, t.to_state].sort().join("|");
    if (!edgeGroups.has(key)) edgeGroups.set(key, []);
    edgeGroups.get(key)!.push(t);
  });

  const handleMouseDownNode = (e: React.MouseEvent, nodeName: string, x: number, y: number) => {
    setDraggingNode(nodeName);
    const svg = (e.currentTarget as Element).closest("svg") as SVGSVGElement;
    if (!svg) return;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const transformed = pt.matrixTransform(svg.getScreenCTM()?.inverse());
    setDragOffset({ x: transformed.x - x, y: transformed.y - y });
    e.stopPropagation();
  };

  const handleMouseDownEdge = (e: React.MouseEvent, transitionId: number, x: number, y: number) => {
    setDraggingEdge(transitionId);
    const svg = (e.currentTarget as Element).closest("svg") as SVGSVGElement;
    if (!svg) return;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const transformed = pt.matrixTransform(svg.getScreenCTM()?.inverse());
    setDragOffset({ x: transformed.x - x, y: transformed.y - y });
    e.stopPropagation();
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const svg = e.currentTarget as SVGSVGElement;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const transformed = pt.matrixTransform(svg.getScreenCTM()?.inverse());

    if (draggingNode) {
      setNodes(prev => prev.map(n => 
        n.state.name === draggingNode 
          ? { ...n, x: transformed.x - dragOffset.x, y: transformed.y - dragOffset.y }
          : n
      ));
    } else if (draggingEdge !== null) {
      setEdgeControls(prev => ({
        ...prev,
        [draggingEdge]: { x: transformed.x - dragOffset.x, y: transformed.y - dragOffset.y }
      }));
    }
  };

  const handleMouseUp = () => {
    setDraggingNode(null);
    setDraggingEdge(null);
  };

  const handleEdgeClick = (t: TransitionItem) => {
    setSelected(t);
    setDrawerOpen(true);
  };

  const selectedEvidence = selected
    ? evidence.filter((e) => e.claim_type === "transition" && e.claim_id === selected.id)
    : [];

  if (loading) {
    return <div style={{ textAlign: "center", padding: 100 }}><Spin size="large" /></div>;
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
    <div className="fade-in" style={{ userSelect: (draggingNode || draggingEdge !== null) ? "none" : "auto" }}>
      <div className="page-header">
        <h1>Protocol State Machine</h1>
        <p>Interactive graph — <b>Drag nodes</b> or <b>drag edge handles</b> to reorganize layout</p>
      </div>

      <div className="graph-container" style={{ padding: 0, overflow: "hidden", background: "var(--bg-secondary)" }}>
        <svg 
          width="100%" height="750" viewBox="0 0 1000 850"
          onMouseMove={handleMouseMove} onMouseUp={handleMouseUp} onMouseLeave={handleMouseUp}
          style={{ cursor: (draggingNode || draggingEdge !== null) ? "grabbing" : "default" }}
        >
          <defs>
            <marker id="arrow" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="8" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 4 L 0 8 z" fill="#60a5fa" opacity="0.7" />
            </marker>
            <marker id="arrow-green" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="8" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 4 L 0 8 z" fill="#34d399" opacity="0.9" />
            </marker>
            <marker id="arrow-red" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="8" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 4 L 0 8 z" fill="#f87171" opacity="0.9" />
            </marker>
            <filter id="glow"><feGaussianBlur stdDeviation="3" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
          </defs>

          {/* Edges */}
          {transitions.map((t) => {
            const fromNode = nodeMap.get(t.from_state);
            const toNode = nodeMap.get(t.to_state);
            if (!fromNode || !toNode) return null;

            const key = [t.from_state, t.to_state].sort().join("|");
            const group = edgeGroups.get(key) || [t];
            const groupIdx = group.indexOf(t);
            
            const { path, labelX, labelY, controlX, controlY } = getEdgePath(
              fromNode, toNode, groupIdx, group.length, edgeControls[t.id]
            );

            const edgeColor = t.status === "supported" ? "#34d399" : t.status === "disputed" ? "#f87171" : "#60a5fa";
            const markerEnd = t.status === "supported" ? "url(#arrow-green)" : t.status === "disputed" ? "url(#arrow-red)" : "url(#arrow)";

            return (
              <g key={t.id}>
                <path
                  d={path} stroke={edgeColor} strokeWidth={selected?.id === t.id ? 3 : 1.5}
                  fill="none" opacity={selected?.id === t.id ? 1 : 0.6} markerEnd={markerEnd}
                  onClick={() => handleEdgeClick(t)} style={{ cursor: "pointer" }}
                />
                
                {/* Control point handle */}
                <circle 
                  cx={controlX} cy={controlY} r={draggingEdge === t.id ? 6 : 4}
                  fill="white" stroke={edgeColor} strokeWidth={2}
                  onMouseDown={(e) => handleMouseDownEdge(e, t.id, controlX, controlY)}
                  style={{ cursor: "grab", opacity: (draggingEdge === t.id || !draggingNode) ? 1 : 0.3 }}
                />

                <rect x={labelX - 35} y={labelY - 12} width={70} height={26} rx={4} fill="white" fillOpacity={0.8} style={{ pointerEvents: "none" }} />
                <text x={labelX} y={labelY} textAnchor="middle" style={{ fontSize: 11, fontWeight: 600, fill: edgeColor, pointerEvents: "none" }}>{t.message_type}</text>
                <text x={labelX} y={labelY + 12} textAnchor="middle" style={{ fontSize: 9, fill: "var(--text-muted)", fontWeight: 500, pointerEvents: "none" }}>{(t.confidence * 100).toFixed(0)}%</text>
              </g>
            );
          })}

          {/* Nodes */}
          {nodes.map((n) => {
            const color = getColor(n.state.name);
            const isDragging = draggingNode === n.state.name;
            return (
              <g key={n.state.name} onMouseDown={(e) => handleMouseDownNode(e, n.state.name, n.x, n.y)} style={{ cursor: isDragging ? "grabbing" : "grab" }}>
                <rect x={n.x} y={n.y} width={NODE_W} height={NODE_H} rx={12} ry={12} fill={isDragging ? "var(--bg-secondary)" : "var(--bg-card)"} stroke={color} strokeWidth={isDragging ? 2.5 : 1.5} filter="url(#glow)" />
                <rect x={n.x + 1} y={n.y + 1} width={NODE_W - 2} height={3} rx={12} ry={2} fill={color} opacity={0.8} />
                <text x={n.x + NODE_W / 2} y={n.y + NODE_H / 2 + 2} textAnchor="middle" dominantBaseline="middle" style={{ fill: color, fontSize: 13, fontWeight: 700, fontFamily: "var(--font-mono)", pointerEvents: "none" }}>{n.state.name}</text>
                <text x={n.x + NODE_W / 2} y={n.y + NODE_H / 2 + 17} textAnchor="middle" style={{ fill: "var(--text-muted)", fontSize: 9, pointerEvents: "none" }}>conf: {(n.state.confidence * 100).toFixed(0)}%</text>
              </g>
            );
          })}
        </svg>
      </div>
<div style={{ display: "flex", gap: 24, marginTop: 16, justifyContent: "center" }}>
        <LegendItem color="#60a5fa" label="Hypothesis" />
        <LegendItem color="#34d399" label="Supported" />
        <LegendItem color="#f87171" label="Disputed" />
      </div>

      <Drawer
        title={selected ? `${selected.from_state} → ${selected.to_state}` : "Transition Detail"}
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
              <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 4 }}>MESSAGE TYPE</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 16, color: "var(--accent-blue)" }}>{selected.message_type}</div>
            </div>
            <div style={{ display: "flex", gap: 16 }}>
              <div>
                <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 4 }}>STATUS</div>
                <span className={`status-badge status-${selected.status}`}>{selected.status}</span>
              </div>
              <div>
                <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 4 }}>CONFIDENCE</div>
                <div style={{ fontWeight: 600 }}>{(selected.confidence * 100).toFixed(1)}%</div>
              </div>
            </div>
            <div>
              <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 8 }}>EVIDENCE ({selectedEvidence.length})</div>
              {selectedEvidence.length === 0 ? (
                <div style={{ color: "var(--text-muted)", fontSize: 13 }}>No evidence bound to this transition.</div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {selectedEvidence.map((e) => (
                    <div key={e.id} style={{ background: "#f8fafc", border: "1px solid var(--border-color)", borderRadius: "var(--radius-sm)", padding: 12 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                        <Tag color={e.source_type === "doc" ? "blue" : e.source_type === "trace" ? "green" : e.source_type === "probe" ? "orange" : "purple"}>{e.source_type}</Tag>
                        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>score: {e.score.toFixed(2)}</span>
                      </div>
                      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4 }}>{e.source_ref}</div>
                      <div className="snippet-block" style={{ fontSize: 12, marginTop: 6 }}>{e.snippet}</div>
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
