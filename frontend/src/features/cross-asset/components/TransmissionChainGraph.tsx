import { useMemo, useState } from "react";

import type {
  TransmissionChainGraph as TransmissionChainGraphData,
  TransmissionDirection,
  TransmissionGraphEdge,
  TransmissionGraphNode,
} from "../lib/crossAssetTransmissionGraph";

import "./TransmissionChainGraph.css";

const UI = {
  eyebrow: "宏观传导链路",
  title: "宏观因子 → 市场资产 → 组合影响",
  loading: "正在加载宏观传导链路…",
  empty: "宏观传导轴暂不可用，链路图等待联动分析数据。",
  layerTitles: ["宏观因子", "市场资产", "组合影响"],
  legend: [
    { key: "supportive", label: "利好债券" },
    { key: "restrictive", label: "利空债券" },
    { key: "conflicted", label: "多空交织" },
    { key: "neutral", label: "中性" },
    { key: "pending", label: "信号待确认" },
  ] as const,
  legendWeight: "线宽=强度",
  drawerSource: "来源",
  drawerEvidence: "证据",
  drawerAffected: "受影响对象",
  drawerClose: "关闭",
  sourceLabels: {
    backend: "联动分析",
    fallback: "兜底判断",
    unavailable: "待接入",
  } as Record<string, string>,
} as const;

/* 布局常量（viewBox 1200×400，三层列） */
const VIEW_W = 1200;
const VIEW_H = 400;
const LAYER_X = [70, 500, 930] as const;
const NODE_W = 200;
const NODE_H = 52;
const TITLE_Y = 26;

type PositionedNode = TransmissionGraphNode & { x: number; y: number };

function layoutNodes(graph: TransmissionChainGraphData): PositionedNode[][] {
  return graph.layers.map((nodes, layerIndex) => {
    const total = nodes.length * NODE_H + (nodes.length - 1) * 16;
    const startY = TITLE_Y + 24 + Math.max(0, (VIEW_H - TITLE_Y - 40 - total) / 2);
    return nodes.map((node, index) => ({
      ...node,
      x: LAYER_X[layerIndex],
      y: startY + index * (NODE_H + 16),
    }));
  });
}

function edgePath(from: PositionedNode, to: PositionedNode): string {
  const x1 = from.x + NODE_W;
  const y1 = from.y + NODE_H / 2;
  const x2 = to.x;
  const y2 = to.y + NODE_H / 2;
  const mx = (x1 + x2) / 2;
  return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
}

function dirClass(dir: TransmissionDirection): string {
  return `tcg-edge--${dir}`;
}

function nodeStanceClass(stance: TransmissionDirection): string {
  return `tcg-node--${stance}`;
}

export function TransmissionChainGraph({
  graph,
  loading = false,
}: {
  graph: TransmissionChainGraphData;
  loading?: boolean;
}) {
  const [hoverKey, setHoverKey] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const positioned = useMemo(() => layoutNodes(graph), [graph]);
  const nodeByKey = useMemo(() => {
    const map = new Map<string, PositionedNode>();
    for (const layer of positioned) {
      for (const node of layer) map.set(node.key, node);
    }
    return map;
  }, [positioned]);

  const edges = useMemo(
    () =>
      graph.edges
        .map((edge) => {
          const from = nodeByKey.get(edge.from);
          const to = nodeByKey.get(edge.to);
          return from && to ? { edge, from, to, d: edgePath(from, to) } : null;
        })
        .filter((item): item is { edge: TransmissionGraphEdge; from: PositionedNode; to: PositionedNode; d: string } =>
          Boolean(item),
        ),
    [graph.edges, nodeByKey],
  );

  const adjacency = useMemo(() => {
    const set = new Set<string>();
    if (hoverKey) {
      set.add(hoverKey);
      for (const { edge } of edges) {
        if (edge.from === hoverKey || edge.to === hoverKey) {
          set.add(edge.from);
          set.add(edge.to);
        }
      }
    }
    return set;
  }, [edges, hoverKey]);

  const isDimmedNode = (key: string) => hoverKey !== null && !adjacency.has(key);
  const isDimmedEdge = (edge: TransmissionGraphEdge) =>
    hoverKey !== null && edge.from !== hoverKey && edge.to !== hoverKey;

  const selectedNode = selectedKey ? nodeByKey.get(selectedKey) ?? null : null;
  const selectedAffected = useMemo(() => {
    if (!selectedKey) return [];
    const keys = new Set<string>();
    for (const { edge } of edges) {
      if (edge.from === selectedKey) keys.add(edge.to);
      if (edge.to === selectedKey) keys.add(edge.from);
    }
    return [...keys]
      .map((key) => nodeByKey.get(key))
      .filter((node): node is PositionedNode => Boolean(node))
      .map((node) => node.label);
  }, [edges, nodeByKey, selectedKey]);

  const hasL1 = graph.layers[0].length > 0;

  // 入场动效序号：节点逐层 stagger 40ms，边在节点之后 draw-on
  let enterIndex = 0;
  const nodeDelay = new Map<string, number>();
  for (const layer of positioned) {
    for (const node of layer) {
      nodeDelay.set(node.key, enterIndex * 40);
      enterIndex += 1;
    }
  }
  const edgeBaseDelay = enterIndex * 40;

  return (
    <section
      className="tcg"
      data-testid="transmission-chain-graph"
      aria-label={UI.title}
    >
      <div className="tcg__header">
        <div>
          <div className="tcg__eyebrow">{UI.eyebrow}</div>
          <h2 className="tcg__title">{UI.title}</h2>
        </div>
        <div className="tcg__legend" aria-hidden="true">
          {UI.legend.map((item) => (
            <span key={item.key} className={`tcg__legend-item tcg__legend-item--${item.key}`}>
              <i className="tcg__legend-swatch" />
              {item.label}
            </span>
          ))}
          <span className="tcg__legend-item tcg__legend-item--weight">{UI.legendWeight}</span>
        </div>
      </div>

      {loading ? (
        <div className="tcg__state" data-testid="transmission-chain-graph-loading">
          {UI.loading}
        </div>
      ) : !hasL1 ? (
        <div className="tcg__state" data-testid="transmission-chain-graph-empty">
          {UI.empty}
        </div>
      ) : (
        <div className="tcg__body">
          <svg
            className="tcg__svg"
            viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
            role="img"
            aria-label={UI.title}
          >
            {UI.layerTitles.map((title, index) => (
              <text
                key={title}
                className="tcg__layer-title"
                x={LAYER_X[index] + NODE_W / 2}
                y={TITLE_Y}
                textAnchor="middle"
              >
                {title}
              </text>
            ))}

            {edges.map(({ edge, d }, index) => (
              <path
                key={`${edge.from}-${edge.to}`}
                className={`tcg-edge ${dirClass(edge.dir)}${edge.pending ? " tcg-edge--pending" : ""}${isDimmedEdge(edge) ? " tcg-edge--dim" : ""}`}
                d={d}
                strokeWidth={edge.weight}
                pathLength={1}
                style={{ ["--tcg-draw-delay" as string]: `${edgeBaseDelay + index * 40}ms` }}
              />
            ))}

            {positioned.map((layer) =>
              layer.map((node) => (
                <g
                  key={node.key}
                  className={`tcg-node ${nodeStanceClass(node.stance)}${isDimmedNode(node.key) ? " tcg-node--dim" : ""}${selectedKey === node.key ? " tcg-node--active" : ""}`}
                  transform={`translate(${node.x}, ${node.y})`}
                  style={{ ["--tcg-enter-delay" as string]: `${nodeDelay.get(node.key) ?? 0}ms` }}
                  onMouseEnter={() => setHoverKey(node.key)}
                  onMouseLeave={() => setHoverKey(null)}
                  onClick={() => setSelectedKey(node.key === selectedKey ? null : node.key)}
                  tabIndex={0}
                  role="button"
                  aria-label={`${node.label} ${node.sub}`}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelectedKey(node.key === selectedKey ? null : node.key);
                    }
                  }}
                >
                  <rect className="tcg-node__rect" width={NODE_W} height={NODE_H} rx={6} />
                  <circle className="tcg-node__dot" cx={12} cy={14} r={3} />
                  <text className="tcg-node__label" x={22} y={18}>
                    {node.label}
                  </text>
                  <text className="tcg-node__sub" x={12} y={38}>
                    {node.sub.length > 24 ? `${node.sub.slice(0, 24)}…` : node.sub}
                  </text>
                </g>
              )),
            )}
          </svg>

          <aside
            className={`tcg__drawer${selectedNode ? " tcg__drawer--open" : ""}`}
            data-testid="transmission-chain-graph-drawer"
            aria-hidden={!selectedNode}
          >
            {selectedNode ? (
              <>
                <div className="tcg__drawer-head">
                  <div>
                    <div className="tcg__drawer-kicker">{UI.layerTitles[selectedNode.layer - 1]}</div>
                    <h3 className="tcg__drawer-title">{selectedNode.label}</h3>
                    <div className={`tcg__drawer-stance tcg__drawer-stance--${selectedNode.stance}`}>
                      {selectedNode.sub}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="tcg__drawer-close"
                    onClick={() => setSelectedKey(null)}
                    aria-label={UI.drawerClose}
                  >
                    ×
                  </button>
                </div>
                <p className="tcg__drawer-summary">{selectedNode.summary}</p>
                {selectedNode.tradeDate ? (
                  <div className="tcg__drawer-meta">交易日 {selectedNode.tradeDate}</div>
                ) : null}
                {selectedNode.evidence.length > 0 ? (
                  <div className="tcg__drawer-block">
                    <div className="tcg__drawer-block-title">{UI.drawerEvidence}</div>
                    <ul className="tcg__drawer-list">
                      {selectedNode.evidence.map((item, index) => (
                        <li key={index}>{item}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {selectedAffected.length > 0 ? (
                  <div className="tcg__drawer-block">
                    <div className="tcg__drawer-block-title">{UI.drawerAffected}</div>
                    <div className="tcg__drawer-tags">
                      {selectedAffected.map((label) => (
                        <span key={label} className="tcg__drawer-tag">
                          {label}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
                <div className="tcg__drawer-meta">
                  {UI.drawerSource}：{UI.sourceLabels[selectedNode.source] ?? selectedNode.source}
                </div>
              </>
            ) : null}
          </aside>
        </div>
      )}
    </section>
  );
}
