import type { CSSProperties } from "react";

import { designTokens, ibTokens } from "../../../theme/designSystem";

import "./GitNexusResultView.css";

type GitNexusResultCard = {
  title: string;
  value?: string | null;
  type: string;
  data?: Record<string, unknown>[] | Record<string, unknown> | null;
};

const GITNEXUS_PROCESS_CARD_TITLE = "GitNexus Processes Table";
const GITNEXUS_GROUP_COLORS: Record<string, string> = {
  api: ibTokens.color.accent,
  services: ibTokens.color.up,
  repositories: designTokens.color.warm.slateBlue,
  governance: ibTokens.color.gold,
  core: ibTokens.color.down,
  tasks: ibTokens.color.up,
  schemas: designTokens.color.primary[700],
  unknown: ibTokens.color.inkMuted,
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function formatMetaValue(value: unknown) {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "string") {
    return value.trim().length > 0 ? value : "—";
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function moduleGroupForTrace(row: Record<string, unknown>) {
  const moduleGroup =
    typeof row.module_group === "string" && row.module_group.trim().length > 0
      ? row.module_group.trim()
      : "unknown";
  return {
    label: moduleGroup,
    color: GITNEXUS_GROUP_COLORS[moduleGroup] ?? GITNEXUS_GROUP_COLORS.unknown,
  };
}

function edgeLabelForTrace(row: Record<string, unknown>) {
  return typeof row.edge_label === "string" ? row.edge_label.trim() : "";
}

export function GitNexusResultView({ cards }: { cards: GitNexusResultCard[] }) {
  const contextCard = cards.find((card) => card.title === "GitNexus Context");
  const toolsCard = cards.find((card) => card.title === "GitNexus Tools");
  const resourcesCard = cards.find((card) => card.title === "GitNexus Resources");
  const processesCard = cards.find((card) => card.title === GITNEXUS_PROCESS_CARD_TITLE);
  const processTraceCard = cards.find((card) => card.title === "GitNexus Process Trace");
  const summaryCards = cards.filter(
    (card) =>
      ![
        "GitNexus Context",
        "GitNexus Tools",
        "GitNexus Resources",
        GITNEXUS_PROCESS_CARD_TITLE,
        "GitNexus Process Trace",
      ].includes(card.title),
  );
  const summaryMetricCards = summaryCards.filter((card) => card.type === "metric");
  const summaryReferenceCards = summaryCards.filter((card) => card.type !== "metric");

  const processes =
    Array.isArray(processesCard?.data) ? processesCard.data.filter(isRecord) : [];
  const traceRows =
    Array.isArray(processTraceCard?.data) ? processTraceCard.data.filter(isRecord) : [];
  const toolRows =
    Array.isArray(toolsCard?.data) ? toolsCard.data.filter(isRecord) : [];
  const resourceRows =
    Array.isArray(resourcesCard?.data) ? resourcesCard.data.filter(isRecord) : [];

  return (
    <div className="agent-gitnexus">
      {summaryCards.length > 0 ? (
        <div className="agent-gitnexus__panel">
          <div className="agent-gitnexus__panel-title">索引摘要</div>
          {summaryMetricCards.length > 0 ? (
            <div className="agent-gitnexus__metric-grid">
              {summaryMetricCards.map((card) => (
                <div key={`summary-${card.title}`} className="agent-gitnexus__metric">
                  <div className="agent-gitnexus__metric-label">{card.title}</div>
                  <div className="agent-gitnexus__metric-value">{formatMetaValue(card.value)}</div>
                </div>
              ))}
            </div>
          ) : null}
          {summaryReferenceCards.length > 0 ? (
            <div className="agent-gitnexus__kv-list">
              {summaryReferenceCards.map((card) => (
                <div key={`summary-ref-${card.title}`} className="agent-gitnexus__kv agent-gitnexus__kv--small">
                  <span className="agent-gitnexus__kv-label">{card.title}:</span>
                  <span>{formatMetaValue(card.value)}</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="agent-gitnexus__columns">
        <div className="agent-gitnexus__panel">
          <div className="agent-gitnexus__panel-title">上下文概览</div>
          {contextCard?.value ? (
            <div className="agent-gitnexus__context-value">{contextCard.value}</div>
          ) : null}
          {Array.isArray(contextCard?.data) ? (
            <div className="agent-gitnexus__kv-list agent-gitnexus__kv-list--tight">
              {contextCard.data.filter(isRecord).map((item, index) => (
                <div key={`context-${index}`} className="agent-gitnexus__kv">
                  <span className="agent-gitnexus__kv-label">{String(item.label ?? "label")}:</span>
                  <span>{formatMetaValue(item.value)}</span>
                </div>
              ))}
            </div>
          ) : null}
          {toolRows.length > 0 ? (
            <div className="agent-gitnexus__sublist">
              <div className="agent-gitnexus__sublist-title">工具</div>
              {toolRows.map((row, index) => (
                <div key={`tool-${index}`} className="agent-gitnexus__list-item">
                  <div className="agent-gitnexus__list-item-title">{formatMetaValue(row.tool)}</div>
                  <div className="agent-gitnexus__list-item-detail">{formatMetaValue(row.description)}</div>
                </div>
              ))}
            </div>
          ) : null}
        </div>

        <div className="agent-gitnexus__panel">
          <div className="agent-gitnexus__panel-title">执行流程</div>
          {processes.length > 0 ? (
            <div className="agent-gitnexus__sublist">
              {processes.map((row, index) => (
                <div key={`process-${index}`} className="agent-gitnexus__list-item agent-gitnexus__list-item--padded">
                  <div className="agent-gitnexus__list-item-title">{formatMetaValue(row.name)}</div>
                  <div className="agent-gitnexus__list-item-detail">
                    {formatMetaValue(row.type)} · 步骤 {formatMetaValue(row.steps)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="agent-gitnexus__empty">未返回流程列表。</div>
          )}
          {resourceRows.length > 0 ? (
            <div className="agent-gitnexus__kv-list agent-gitnexus__kv-list--tight">
              {resourceRows.map((row, index) => (
                <div key={`resource-${index}`} className="agent-gitnexus__kv agent-gitnexus__kv--small">
                  <span className="agent-gitnexus__kv-label">{formatMetaValue(row.description)}:</span>
                  <span>{formatMetaValue(row.uri)}</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      {traceRows.length > 0 ? (
        <div className="agent-gitnexus__panel">
          <div className="agent-gitnexus__panel-title">流程图</div>
          <div className="agent-gitnexus__trace">
            {traceRows.map((row, index) => {
              const moduleGroup = moduleGroupForTrace(row);
              const edgeLabel = edgeLabelForTrace(row);

              return (
                <div key={`trace-${index}`} className="agent-gitnexus__trace-step">
                  <div
                    className="agent-gitnexus__trace-node"
                    style={{ "--agent-gitnexus-group-color": moduleGroup.color } as CSSProperties}
                  >
                    <div className="agent-gitnexus__trace-head">
                      <span className="agent-gitnexus__trace-kicker">
                        步骤 {formatMetaValue(row.step)}
                      </span>
                      <span className="agent-gitnexus__trace-index">{formatMetaValue(row.step)}</span>
                    </div>
                    <div className="agent-gitnexus__trace-symbol">{formatMetaValue(row.symbol)}</div>
                    <div className="agent-gitnexus__trace-group">{moduleGroup.label}</div>
                    <div className="agent-gitnexus__trace-file">{formatMetaValue(row.file)}</div>
                  </div>
                  {index < traceRows.length - 1 ? (
                    <div aria-hidden="true" className="agent-gitnexus__trace-edge">
                      <div className="agent-gitnexus__trace-edge-label">{edgeLabel}</div>
                      <div className="agent-gitnexus__trace-edge-line" />
                      <div className="agent-gitnexus__trace-edge-arrow">→</div>
                      <div className="agent-gitnexus__trace-edge-line" />
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}
