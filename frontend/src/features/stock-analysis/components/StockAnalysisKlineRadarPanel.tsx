import { useMemo } from "react";
import {
  FireOutlined,
  LineChartOutlined,
  SafetyCertificateOutlined,
  StockOutlined,
} from "@ant-design/icons";

import type { LivermoreStrategyPayload } from "../../../api/contracts";
import {
  SA_CARD_TITLE,
  SA_FIRST_CARD,
  SA_PILL,
  SA_SECTION_EYEBROW,
  SA_SECTION_HEAD,
} from "../lib/stockAnalysisPageChrome";
import { buildStockAnalysisKlineRadar } from "../lib/stockAnalysisKlineRadarModel";
import type {
  StockAnalysisKlineRadarItem,
  StockAnalysisKlineRadarQueueKey,
  StockAnalysisKlineRadarSummary,
  StockAnalysisKlineRadarTone,
  StockAnalysisKlineRadarTopologyNode,
} from "../lib/stockAnalysisKlineRadarModel";
import { CompactStatusTile } from "./StockAnalysisStatusPrimitives";

type StockAnalysisKlineRadarPanelProps = {
  strategyPayload: LivermoreStrategyPayload | null;
  onOpenRadarItem: (item: StockAnalysisKlineRadarItem) => void;
};

const QUEUE_ICONS: Record<StockAnalysisKlineRadarQueueKey, JSX.Element> = {
  breakout: <LineChartOutlined aria-hidden="true" />,
  trend_continuation: <StockOutlined aria-hidden="true" />,
  mean_reversion: <FireOutlined aria-hidden="true" />,
  risk_exit: <SafetyCertificateOutlined aria-hidden="true" />,
};

type TopologyDisplayNode = {
  id: string;
  label: string;
  detail: string;
  tone: StockAnalysisKlineRadarTone;
  technicalLabel?: string;
};

const FOCUS_TABLE_LIMIT = 8;

function compactTopologyNodeId(id: string): string {
  return id.replace(/^(gate|module|queue|stock):/, "");
}

function topologyRelationLabel(kind: string): string {
  if (kind === "feeds") return "供给";
  if (kind === "routes") return "路由";
  if (kind === "gates") return "门控";
  return "关联";
}

function marketGateStateLabel(state: string | null): string {
  if (!state) return "待确认";
  const labels: Record<string, string> = {
    BLOCKED: "受限",
    HOT: "偏热",
    OFF: "关闭",
    ON: "开启",
    OPEN: "开放",
    OVERHEAT: "过热",
    WARM: "温和",
  };
  return labels[state.toUpperCase()] ?? "待确认";
}

function marketGateEdgeLabel(label: string): string {
  const normalized = label.trim().toLowerCase();
  if (normalized === "enabled") return "已启用";
  if (normalized === "disabled") return "未启用";
  if (normalized === "blocked") return "受限";
  return "门控关系";
}

function edgeTone(kind: string): StockAnalysisKlineRadarTone {
  if (kind === "gates") return "warning";
  if (kind === "feeds") return "positive";
  return "neutral";
}

function stockRouteCount(node: StockAnalysisKlineRadarTopologyNode, summary: StockAnalysisKlineRadarSummary): number {
  return summary.topology.edges
    .filter((edge) => edge.kind === "routes" && edge.to === node.id)
    .reduce((total, edge) => total + edge.weight, 0);
}

function gateTone(state: string | null): StockAnalysisKlineRadarTone {
  if (!state) return "warning";
  if (state === "WARM") return "warning";
  if (state === "ON" || state === "HOT" || state === "OPEN") return "positive";
  if (state === "OFF" || state === "BLOCKED") return "negative";
  return "neutral";
}

function testIdFragment(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]+/g, "-");
}

function evidenceSummary(item: StockAnalysisKlineRadarItem): string {
  if (item.evidence.length > 0) return item.evidence.slice(0, 2).join(" / ");
  return item.scoreLabel ?? item.sectorName ?? item.sourceLabel;
}

function queueLeadText(queueItems: StockAnalysisKlineRadarItem[], emptyDetail: string): string {
  const leadItem = queueItems[0];
  if (!leadItem) return emptyDetail;
  return `${leadItem.stockName} ${leadItem.signalLabel}，${evidenceSummary(leadItem)}`;
}

export function StockAnalysisKlineRadarPanel({
  strategyPayload,
  onOpenRadarItem,
}: StockAnalysisKlineRadarPanelProps) {
  const summary = useMemo(() => buildStockAnalysisKlineRadar(strategyPayload), [strategyPayload]);
  const focusItems = summary.focusItems.slice(0, FOCUS_TABLE_LIMIT);
  const riskUnavailable = summary.riskTriggerCount == null && summary.riskUnavailableReason != null;
  const topology = summary.topology;
  const topologyEdgesByKind = {
    feeds: topology.edges.filter((edge) => edge.kind === "feeds").length,
    routes: topology.edges.filter((edge) => edge.kind === "routes").length,
    gates: topology.edges.filter((edge) => edge.kind === "gates").length,
  };
  const topologyNodeLabelsById = new Map(
    topology.nodes.map((node) => [
      node.id,
      node.kind === "gate"
        ? `市场门控：${marketGateStateLabel(summary.marketGateState)}`
        : node.label,
    ] as const),
  );
  const gateNodes = topology.nodes.filter((node) => node.kind === "gate");
  const gateEdges = topology.edges.filter((edge) => edge.kind === "gates");
  const topologyEdgeRows = topology.edges.map((edge) => ({
    ...edge,
    fromLabel: topologyNodeLabelsById.get(edge.from) ?? compactTopologyNodeId(edge.from),
    toLabel: topologyNodeLabelsById.get(edge.to) ?? compactTopologyNodeId(edge.to),
    tone: edgeTone(edge.kind),
  }));
  const sourceModuleNodes: TopologyDisplayNode[] = topology.nodes
    .filter((node) => node.kind === "module")
    .map((node) => ({
      id: node.id,
      label: node.label,
      detail: `${topology.edges.filter((edge) => edge.from === node.id).length} 条关联`,
      tone: node.tone,
      technicalLabel: compactTopologyNodeId(node.id),
    }));
  const queueNodes: TopologyDisplayNode[] = summary.queues.map((queue) => {
    const queueNodeId = `queue:${queue.key}`;
    const incoming = topology.edges.filter((edge) => edge.to === queueNodeId).length;
    const outgoing = topology.edges.filter((edge) => edge.from === queueNodeId).length;
    return {
      id: queueNodeId,
      label: queue.label,
      detail:
        queue.key === "risk_exit" && riskUnavailable
          ? `不可用 / ${summary.riskUnavailableReason}`
          : `${queue.count} 条 / 入 ${incoming} / 出 ${outgoing}`,
      tone: queue.tone,
      technicalLabel: queue.key,
    };
  });
  const stockNodes = topology.nodes.filter((node) => node.kind === "stock");
  const stockDisplayNodes: TopologyDisplayNode[] = stockNodes.map((node) => {
    const routes = stockRouteCount(node, summary);
    return {
      id: node.id,
      label: node.label,
      detail: `${node.stockCode ?? "代码待补"}${routes > 1 ? ` / ${routes} 信号` : ""}`,
      tone: node.tone,
    };
  });
  const topologyStages = [
    {
      key: "source_module",
      label: "来源模块",
      technicalLabel: "source_module",
      nodes: sourceModuleNodes,
      emptyLabel: "等待模块输出",
    },
    {
      key: "radar_queue",
      label: "雷达队列",
      technicalLabel: "radar_queue",
      nodes: queueNodes,
      emptyLabel: "等待队列",
    },
    {
      key: "stock_node",
      label: "股票节点",
      technicalLabel: "stock_node",
      nodes: stockDisplayNodes,
      emptyLabel: "等待股票节点",
    },
  ];
  const marketGateState = marketGateStateLabel(summary.marketGateState);
  const marketGateTone = gateTone(summary.marketGateState);
  const snapshotLabel = summary.asOfDate ?? "日期待补";
  const riskDecisionLabel = riskUnavailable
    ? `风险退出不可用（${summary.riskUnavailableReason}）`
    : `风险触发 ${summary.riskTriggerCount}，观察 ${summary.riskWatchCount}`;
  const decisionHeadline =
    summary.totalCount > 0
      ? `市场门控 ${marketGateState}，可观察 ${topology.stockCount} 只，${riskDecisionLabel}`
      : summary.pendingEvidenceItems.length > 0
        ? `市场门控 ${marketGateState}，${summary.pendingEvidenceItems.length} 只待补证观察，不计入可复核观察数，${riskDecisionLabel}`
        : riskUnavailable
          ? `市场门控 ${marketGateState}，暂无可复核观察，${riskDecisionLabel}`
          : "等待策略快照，暂无可复核样本";
  const riskQueue = summary.queues.find((queue) => queue.key === "risk_exit");
  const opportunityQueues = summary.queues.filter((queue) => queue.key !== "risk_exit");

  return (
    <section
      className={`${SA_FIRST_CARD} stock-analysis-page__lower-data-band stock-analysis-page__kline-radar`}
      id="stock-analysis-kline-radar"
      data-testid="stock-analysis-kline-radar"
    >
      <div className={SA_SECTION_HEAD}>
        <div className="stock-analysis-page__min-w-0">
          <p className={SA_SECTION_EYEBROW}>深度研究</p>
          <h2 className={SA_CARD_TITLE}>K线观察队列</h2>
          <div className="stock-analysis-page__lower-signal-strip" aria-label="AI K线雷达状态">
            {summary.queues.map((queue) => (
              <div
                key={queue.key}
                className="stock-analysis-page__signal-pill"
                data-tone={queue.tone}
              >
                {QUEUE_ICONS[queue.key]} {queue.shortLabel}{" "}
                {queue.key === "risk_exit" && riskUnavailable ? "不可用" : queue.count}
              </div>
            ))}
          </div>
        </div>
        <span className={SA_PILL}>
          {summary.totalCount > 0
            ? `${summary.totalCount} 条 / ${summary.asOfDate ?? "日期待补"}`
            : summary.pendingEvidenceItems.length > 0
              ? `${summary.pendingEvidenceItems.length} 条待补证 / ${summary.asOfDate ?? "日期待补"}`
              : "等待快照"}
        </span>
      </div>

      <div
        className="stock-analysis-page__kline-radar-decision"
        data-testid="stock-analysis-kline-radar-decision"
        data-tone={marketGateTone}
        aria-label="AI K线雷达今日观察结论"
      >
        <div className="stock-analysis-page__kline-radar-decision-main">
          <span>今日观察结论</span>
          <strong>{decisionHeadline}</strong>
          <p>
            来自策略快照的 K 线观察入口，仅用于复核股票候选、风险退出和来源证据；不生成交易指令。
          </p>
        </div>
        <div className="stock-analysis-page__kline-radar-decision-metrics">
          <span data-tone="positive">
            <small>可复核观察</small>
            <strong>{summary.opportunityCount}</strong>
          </span>
          <span data-tone="negative">
            <small>风险预警</small>
            <strong>
              {riskUnavailable
                ? "不可用"
                : `触发 ${summary.riskTriggerCount} · 观察 ${summary.riskWatchCount}`}
            </strong>
          </span>
          <span data-tone="warning">
            <small>多信号股票</small>
            <strong>{topology.multiSignalStockCount}</strong>
          </span>
          <span data-tone={marketGateTone}>
            <small>数据日</small>
            <strong>{snapshotLabel}</strong>
          </span>
        </div>
      </div>

      <div
        className="stock-analysis-page__kline-radar-buckets"
        data-testid="stock-analysis-kline-radar-buckets"
        aria-label="AI K线雷达观察与风险池"
      >
        <div className="stock-analysis-page__kline-radar-bucket stock-analysis-page__kline-radar-bucket--wide" data-tone="positive">
          <div>
            <span>观察池</span>
            <strong>{summary.opportunityCount}</strong>
          </div>
          <p>
            {opportunityQueues
              .map((queue) => `${queue.shortLabel} ${queue.count}`)
              .join(" / ")}
          </p>
        </div>
        <div className="stock-analysis-page__kline-radar-bucket" data-tone="negative">
          <div>
            <span>风险池</span>
            <strong>{riskUnavailable ? "不可用" : (riskQueue?.count ?? 0)}</strong>
          </div>
          <p>
            {riskUnavailable
              ? `风险退出不可用：${summary.riskUnavailableReason}`
              : queueLeadText(riskQueue?.items ?? [], riskQueue?.emptyDetail ?? "当前未命中风险退出观察。")}
          </p>
        </div>
        {opportunityQueues.map((queue) => (
          <div key={queue.key} className="stock-analysis-page__kline-radar-bucket" data-tone={queue.tone}>
            <div>
              <span>
                {QUEUE_ICONS[queue.key]} {queue.label}
              </span>
              <strong>{queue.count}</strong>
            </div>
            <p>{queueLeadText(queue.items, queue.emptyDetail)}</p>
          </div>
        ))}
      </div>

      {summary.pendingEvidenceItems.length > 0 ? (
        <div
          className="stock-analysis-page__kline-radar-bucket stock-analysis-page__kline-radar-bucket--wide"
          data-testid="stock-analysis-kline-radar-pending-evidence"
          data-tone="warning"
        >
          <div>
            <span>待补证观察</span>
            <strong>{summary.pendingEvidenceItems.length}</strong>
          </div>
          <p>融合模块仅提供明细证据，不计入可复核观察数。</p>
          <ul className="stock-analysis-page__kline-radar-list">
            {summary.pendingEvidenceItems.map((item) => (
              <li key={item.key}>
                <button
                  type="button"
                  className="stock-analysis-page__kline-radar-row"
                  data-tone="warning"
                  data-testid={`stock-analysis-kline-radar-pending-${testIdFragment(item.key)}`}
                  onClick={() => onOpenRadarItem(item)}
                >
                  <span className="stock-analysis-page__kline-radar-row-main">
                    <strong>{item.stockName}</strong>
                    <small className="stock-analysis-page__tabular">{item.stockCode}</small>
                  </span>
                  <span className="stock-analysis-page__kline-radar-row-meta">
                    <span>待补证</span>
                    <span>{item.sourceLabel}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div
        className="stock-analysis-page__kline-radar-focus-table"
        data-testid="stock-analysis-kline-radar-focus-table"
        aria-label="AI K线雷达重点股票"
      >
        <div className="stock-analysis-page__kline-radar-focus-table-title">
          <span>重点股票</span>
          <strong>{focusItems.length > 0 ? `${focusItems.length} 条可点选复核` : "暂无可点选样本"}</strong>
        </div>
        {focusItems.length === 0 ? (
          <CompactStatusTile
            icon={<LineChartOutlined />}
            label="K线雷达"
            value="0 条"
            detail="现有策略快照未返回可派生的 K 线观察样本。"
            testId="stock-analysis-kline-radar-empty"
          />
        ) : (
          <div className="stock-analysis-page__kline-radar-focus-table-grid">
            <div className="stock-analysis-page__kline-radar-focus-table-head" aria-hidden="true">
              <span>股票</span>
              <span>信号</span>
              <span>来源模块</span>
              <span>关键证据</span>
              <span>动作</span>
            </div>
            {focusItems.map((item) => (
              <button
                key={item.key}
                type="button"
                className="stock-analysis-page__kline-radar-focus-table-row"
                data-tone={item.tone}
                data-testid={`stock-analysis-kline-radar-focus-row-${testIdFragment(item.key)}`}
                onClick={() => onOpenRadarItem(item)}
              >
                <span className="stock-analysis-page__kline-radar-focus-stock">
                  <strong>{item.stockName}</strong>
                  <small className="stock-analysis-page__tabular">{item.stockCode}</small>
                </span>
                <span>{item.signalLabel}</span>
                <span>{item.sourceLabel}</span>
                <span>{evidenceSummary(item)}</span>
                <em>打开详情</em>
              </button>
            ))}
          </div>
        )}
      </div>

      <details
        className="stock-analysis-page__kline-radar-details"
        data-testid="stock-analysis-kline-radar-details"
      >
        <summary className="stock-analysis-page__kline-radar-details-summary">
          <span>更多审计</span>
          <strong>完整队列、页面状态与来源拓扑</strong>
          <small>默认收起</small>
        </summary>
        <div className="stock-analysis-page__kline-radar-details-content">
          <div
            className="stock-analysis-page__kline-radar-state-strip"
            data-testid="stock-analysis-kline-radar-state-strip"
            aria-label="AI K线雷达页面完整性状态"
          >
            <span data-tone={marketGateTone}>
              <strong>页面完整性状态</strong>
              <small>空态、日期待补、加载失败和回退状态在页面内显式呈现。</small>
            </span>
            <span data-tone="neutral">
              <strong>使用边界</strong>
              <small>观察复核入口，正式指标口径仍以业务契约确认为准。</small>
            </span>
          </div>

          <div className="stock-analysis-page__kline-radar-grid" aria-label="AI K线雷达完整队列">
            {summary.queues.map((queue) => (
              <div
                key={queue.key}
                className="stock-analysis-page__kline-radar-card"
                data-tone={queue.tone}
                data-testid={`stock-analysis-kline-radar-queue-${queue.key}`}
              >
            <div className="stock-analysis-page__kline-radar-card-head">
              <span>
                {QUEUE_ICONS[queue.key]} {queue.label}
              </span>
              <strong>{queue.key === "risk_exit" && riskUnavailable ? "不可用" : queue.count}</strong>
            </div>

            {queue.items.length === 0 ? (
              <p className="stock-analysis-page__kline-radar-empty">
                {queue.key === "risk_exit" && riskUnavailable
                  ? `风险退出不可用：${summary.riskUnavailableReason}`
                  : queue.emptyDetail}
              </p>
            ) : (
              <ul className="stock-analysis-page__kline-radar-list">
                {queue.items.map((item) => (
                  <li key={item.key}>
                    <button
                      type="button"
                      className="stock-analysis-page__kline-radar-row"
                      data-tone={item.tone}
                      data-testid={`stock-analysis-kline-radar-row-${item.queueKey}-${item.stockCode}`}
                      onClick={() => onOpenRadarItem(item)}
                    >
                      <span className="stock-analysis-page__kline-radar-row-main">
                        <strong>
                          {item.rank ? `#${item.rank} ` : ""}
                          {item.stockName}
                        </strong>
                        <small className="stock-analysis-page__tabular">{item.stockCode}</small>
                      </span>
                      <span className="stock-analysis-page__kline-radar-row-meta">
                        <span>{item.signalLabel}</span>
                        <span>{item.sectorName ?? item.sourceLabel}</span>
                        <span>{item.sourceLabel}</span>
                        {item.scoreLabel ? <span>{item.scoreLabel}</span> : null}
                      </span>
                      {item.evidence.length > 0 ? (
                        <span className="stock-analysis-page__kline-radar-evidence">
                          {item.evidence.slice(0, 3).map((line) => (
                            <em key={line}>{line}</em>
                          ))}
                        </span>
                      ) : null}
                    </button>
                  </li>
                ))}
              </ul>
            )}
              </div>
            ))}
          </div>

          <div
            className="stock-analysis-page__kline-radar-explanation"
            data-testid="stock-analysis-kline-radar-explanation"
            aria-label="AI K线雷达解释层"
          >
        <div className="stock-analysis-page__kline-radar-explanation-head">
          <span>解释层：来源与拓扑</span>
          <strong>模块 → 队列 → 股票节点</strong>
          <p>用于审计信号来源、市场门控和边关系，放在观察复核表之后，不遮挡第一眼信息。</p>
        </div>
        <div className="stock-analysis-page__kline-radar-relation-grid">
          <span>
            <small title="feeds">供给关系</small>
            <strong>{topologyEdgesByKind.feeds}</strong>
          </span>
          <span>
            <small title="routes">路由关系</small>
            <strong>{topologyEdgesByKind.routes}</strong>
          </span>
          <span>
            <small title="gates">门控关系</small>
            <strong>{topologyEdgesByKind.gates}</strong>
          </span>
          <span>
            <small title="modules">策略模块</small>
            <strong>{topology.moduleCount}</strong>
          </span>
        </div>

        <div
          className="stock-analysis-page__kline-radar-topology"
          data-testid="stock-analysis-kline-radar-topology"
          aria-label="AI K线雷达拓扑摘要"
        >
          <div className="stock-analysis-page__kline-radar-topology-summary">
            <p>信号拓扑</p>
            <strong>模块 → 队列 → 股票节点</strong>
            <span>多信号股票和风险退出保留在关系账本中，便于复核来源。</span>
            <div className="stock-analysis-page__kline-radar-topology-metrics">
              <span data-tone="positive">
                <small>策略模块</small>
                <strong>{topology.moduleCount}</strong>
              </span>
              <span data-tone="positive">
                <small>雷达队列</small>
                <strong>{summary.queues.length}</strong>
              </span>
              <span data-tone="neutral">
                <small>股票节点</small>
                <strong>{topology.stockCount}</strong>
              </span>
              <span data-tone="warning">
                <small>关联边</small>
                <strong>{topology.edgeCount}</strong>
              </span>
              <span data-tone="negative">
                <small>多信号</small>
                <strong>{topology.multiSignalStockCount}</strong>
              </span>
            </div>
            <div className="stock-analysis-page__kline-radar-edge-strip" aria-label="AI K线雷达边类型">
              <span title="feeds">供给 {topologyEdgesByKind.feeds}</span>
              <span title="routes">路由 {topologyEdgesByKind.routes}</span>
              <span title="gates">门控 {topologyEdgesByKind.gates}</span>
            </div>
            {gateNodes.length > 0 || gateEdges.length > 0 ? (
              <div
                className="stock-analysis-page__kline-radar-gate-strip"
                data-testid="stock-analysis-kline-radar-gate-strip"
                aria-label="AI K线雷达市场门控"
              >
                {gateNodes.map((node) => (
                  <span key={node.id} data-tone={node.tone} title={node.label}>
                    <strong title="market_gate">市场门控</strong>
                    <small>{marketGateStateLabel(summary.marketGateState)}</small>
                  </span>
                ))}
                {gateEdges.map((edge) => (
                  <span key={edge.id} data-tone="warning" title={edge.label}>
                    <strong>{marketGateEdgeLabel(edge.label)}</strong>
                    <small>
                      {topologyNodeLabelsById.get(edge.from) ?? compactTopologyNodeId(edge.from)}
                      {" → "}
                      {topologyNodeLabelsById.get(edge.to) ?? compactTopologyNodeId(edge.to)}
                    </small>
                  </span>
                ))}
              </div>
            ) : null}
          </div>

          <div className="stock-analysis-page__kline-radar-topology-map">
            {topologyStages.map((stage) => (
              <div
                key={stage.key}
                className="stock-analysis-page__kline-radar-topology-stage"
                data-topology-stage={stage.key}
              >
                <span
                  className="stock-analysis-page__kline-radar-topology-stage-label"
                  title={stage.technicalLabel}
                >
                  {stage.label}
                </span>
                {(stage.nodes.length > 0
                  ? stage.nodes
                  : [
                      {
                        id: `${stage.key}:empty`,
                        label: stage.emptyLabel,
                        detail: "0 条",
                        tone: "neutral" as StockAnalysisKlineRadarTone,
                      },
                    ]
                ).map((node) => (
                  <span
                    key={node.id}
                    className="stock-analysis-page__kline-radar-topology-node"
                    data-tone={node.tone}
                    data-topology-node-id={node.id}
                    title={node.technicalLabel}
                  >
                    <strong>{node.label}</strong>
                    <small>{node.detail}</small>
                  </span>
                ))}
              </div>
            ))}
          </div>

          <div
            className="stock-analysis-page__kline-radar-edge-ledger"
            data-testid="stock-analysis-kline-radar-edge-ledger"
            aria-label="AI K线雷达完整边账本"
          >
            <span className="stock-analysis-page__kline-radar-edge-ledger-title" title="edge ledger">
              关系账本
            </span>
            <div className="stock-analysis-page__kline-radar-edge-ledger-list">
              {topologyEdgeRows.length > 0 ? (
                topologyEdgeRows.map((edge) => (
                  <span
                    key={edge.id}
                    data-tone={edge.tone}
                    title={`${edge.kind}: ${edge.fromLabel} -> ${edge.toLabel}; ${edge.label}; weight=${edge.weight}`}
                  >
                    <em>{topologyRelationLabel(edge.kind)}</em>
                    <strong>{edge.fromLabel}</strong>
                    <small>
                      {" → "}
                      {edge.toLabel} / {topologyRelationLabel(edge.kind)} / 权重 {edge.weight}
                    </small>
                  </span>
                ))
              ) : (
                <span data-tone="neutral">
                  <em>暂无</em>
                  <strong>等待边关系</strong>
                  <small>0 条</small>
                </span>
              )}
            </div>
          </div>
        </div>
          </div>
        </div>
      </details>
    </section>
  );
}
