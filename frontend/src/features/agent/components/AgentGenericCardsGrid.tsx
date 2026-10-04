import "./AgentGenericCardsGrid.css";

import { EM_DASH } from "../../../utils/format";

type AgentGenericCard = {
  title: string;
  value?: string | null;
  type: string;
  data?: Record<string, unknown>[] | Record<string, unknown> | null;
  spec?: Record<string, unknown> | null;
};

const WORKFLOW_TITLES: Record<string, string> = {
  portfolio_review: "组合复核",
  pnl_review: "损益复核",
  risk_memo: "风险纪要",
  market_brief: "市场简报",
  research_radar_brief: "研究雷达简报",
};

const WORKFLOW_DESCRIPTIONS: Record<string, string> = {
  "Reference workflow plan for reviewing portfolio scale, duration risk, and credit exposure.":
    "复核组合规模、久期风险与信用暴露的参考工作流。",
  "Reference workflow plan for reviewing PnL summary, bridge, and product-level PnL.":
    "复核损益汇总、损益桥接与产品损益的参考工作流。",
  "Reference workflow plan for preparing a governed risk memo outline.":
    "生成受治理风险纪要提纲的参考工作流。",
  "Reference workflow plan for combining governed market data and news evidence.":
    "汇总受治理市场数据与新闻证据的参考工作流。",
  "Local analytical brief over governed Choice news events.":
    "基于受治理 Choice 新闻事件生成本地分析简报。",
};

const INTENT_TITLES: Record<string, string> = {
  portfolio_overview: "组合概览复核",
  duration_risk: "久期风险复核",
  credit_exposure: "信用暴露复核",
  pnl_summary: "损益汇总复核",
  pnl_bridge: "损益桥接复核",
  product_pnl: "产品损益复核",
  risk_tensor: "风险张量复核",
  market_data: "市场数据检查",
  news: "事件与新闻检查",
  research_radar_brief: "研究雷达简报",
};

const PNL_CARD_TITLE_LABELS: Record<string, string> = {
  "total pnl": "总损益",
  "interest 514": "利息收入（514）",
  "fair value 516": "公允价值变动（516）",
  "capital gain 517": "资本利得（517）",
};

const GOVERNANCE_NOTES: Record<string, string> = {
  "Uses Anthropic financial-services reference patterns only as a workflow blueprint.":
    "仅借鉴 Anthropic financial-services 的工作流组织方式。",
  "Routes through existing MOSS governed intents before any formal financial result can be produced.":
    "正式金融结果只能由现有 MOSS 受治理意图产出。",
  "Does not connect to Claude API, Managed Agents, or external market-data providers.":
    "不连接 Claude API、Managed Agents 或外部市场数据商。",
  "Keeps formal PnL calculations inside existing MOSS intent handlers.":
    "正式损益计算仍由 MOSS 现有意图处理器完成。",
  "Does not write adjustments or trigger downstream posting workflows.":
    "不写入调整项，也不触发下游入账流程。",
  "Plan card is the default; multi-intent execution requires explicit context.workflow_mode=execute.":
    "默认只生成计划；多意图执行必须显式指定 context.workflow_mode=execute。",
  "Uses MOSS duration, credit exposure, and risk tensor evidence paths when executed later.":
    "后续执行时仅使用 MOSS 久期、信用暴露与风险张量证据链。",
  "Plan responses are non-formal with no evidence rows; execute mode aggregates evidence from the mapped MOSS intents.":
    "计划响应不是正式结果且不含证据行；执行模式只汇总映射意图的 MOSS 证据。",
  "External agents cannot bypass MOSS result_meta, lineage, or audit contracts.":
    "外部 Agent 不能绕过 MOSS result_meta、血缘或审计契约。",
  "Uses existing MOSS market-data and news intents rather than new external feeds.":
    "使用现有 MOSS 市场数据与新闻意图，不新增外部数据流。",
  "Any future provider integration must enter through governed MCP/data contracts.":
    "未来数据商接入必须通过受治理的 MCP 或数据契约。",
  "Current phase does not fetch or license external financial data.":
    "当前阶段不抓取或授权使用外部金融数据。",
  "Analytical only: not a formal metric, stress result, or trading instruction.":
    "仅供分析，不构成正式指标、压力测试结果或交易指令。",
  "Raw Choice/news evidence must appear before interpretation.":
    "解读前必须先展示 Choice 或新闻原始证据。",
  "Human confirmation is required before any later scenario analysis.":
    "后续情景分析前必须由人工确认。",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function textValue(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function displayCardTitle(title: string) {
  const normalized = title.trim().toLowerCase();
  return PNL_CARD_TITLE_LABELS[normalized] ?? title;
}

function workflowTitle(data: Record<string, unknown>) {
  const workflowId = textValue(data.workflow_id);
  const title = textValue(data.title);
  return (WORKFLOW_TITLES[workflowId] ?? WORKFLOW_TITLES[title] ?? title) || EM_DASH;
}

function workflowDescription(value: unknown) {
  const description = textValue(value);
  return WORKFLOW_DESCRIPTIONS[description] ?? description;
}

function workflowCategory(value: unknown) {
  const category = textValue(value);
  const labels: Record<string, string> = {
    portfolio: "组合",
    pnl: "损益",
    risk: "风险",
    market: "市场",
    research: "研究",
  };
  return labels[category] ?? category;
}

function workflowOutputKind(value: unknown) {
  const outputKind = textValue(value);
  const labels: Record<string, string> = {
    workflow_plan: "工作流计划",
    "agent.research_radar_brief": "研究简报",
  };
  return labels[outputKind] ?? outputKind;
}

function workflowPhase(value: unknown) {
  const phase = textValue(value);
  return phase === "plan_only" ? "仅规划" : phase;
}

function workflowSource(value: unknown) {
  const source = textValue(value);
  const labels: Record<string, string> = {
    anthropic_financial_services_reference: "Anthropic 金融服务参考架构",
    moss_research_workflow_catalog: "MOSS 研究工作流目录",
  };
  return labels[source] ?? source;
}

function columnsForCard(card: AgentGenericCard) {
  const explicitColumns = Array.isArray(card.spec?.columns)
    ? card.spec.columns.filter((value): value is string => typeof value === "string")
    : [];
  if (explicitColumns.length > 0) {
    return explicitColumns;
  }
  if (Array.isArray(card.data) && card.data.length > 0) {
    return Object.keys(card.data[0]);
  }
  if (isRecord(card.data)) {
    return Object.keys(card.data);
  }
  return [];
}

function formatCardType(type: string) {
  const typeLabels: Record<string, string> = {
    duration: "久期",
    risk: "风险",
    metric: "指标",
    table: "表格",
    resource: "资源",
  };
  return typeLabels[type] ?? type;
}

function safeInternalHref(value: unknown) {
  if (typeof value !== "string") {
    return "#";
  }
  const href = value.trim();
  return href.startsWith("/") ? href : "#";
}

function renderStructuredCard(card: AgentGenericCard, formatValue: (value: unknown) => string) {
  const columns = columnsForCard(card);
  const rows = Array.isArray(card.data)
    ? card.data
    : isRecord(card.data)
      ? [card.data]
      : [];

  return (
    <div key={`${card.title}-${card.type}`} className="agent-generic-cards__card">
      <div className="agent-generic-cards__title">{displayCardTitle(card.title)}</div>
      {card.value ? <div className="agent-generic-cards__value">{card.value}</div> : null}
      {rows.length > 0 && columns.length > 0 ? (
        <div className="agent-generic-cards__rows">
          {rows.map((row, index) => (
            <div key={`${card.title}-row-${index}`} className="agent-generic-cards__row">
              {columns.map((column) => (
                <div key={`${card.title}-${index}-${column}`} className="agent-generic-cards__field">
                  <span className="agent-generic-cards__field-label">{column}:</span>
                  <span>{formatValue((row as Record<string, unknown>)[column])}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function renderWorkflowPlanCard(card: AgentGenericCard) {
  const data = isRecord(card.data) ? card.data : {};
  const workflowId = textValue(data.workflow_id) || EM_DASH;
  const description = workflowDescription(data.description);
  const meta = [
    { label: "业务域", value: workflowCategory(data.category) || EM_DASH },
    { label: "输出类型", value: workflowOutputKind(data.output_kind) || EM_DASH },
    { label: "阶段", value: workflowPhase(data.phase) || EM_DASH },
    { label: "参考来源", value: workflowSource(data.source) || EM_DASH },
  ];

  return (
    <section
      key={`${card.title}-${card.type}`}
      className="agent-generic-cards__card agent-generic-cards__card--workflow"
      data-testid="agent-workflow-plan-card"
    >
      <div className="agent-generic-cards__workflow-header">
        <div>
          <h3 className="agent-generic-cards__title">工作流计划</h3>
          <div className="agent-generic-cards__workflow-name">{workflowTitle(data)}</div>
        </div>
        <span className="agent-generic-cards__workflow-state">只读计划</span>
      </div>
      {description ? (
        <p className="agent-generic-cards__workflow-description">{description}</p>
      ) : null}
      <div className="agent-generic-cards__workflow-id">
        <span>工作流标识</span>
        <code>{workflowId}</code>
      </div>
      <dl className="agent-generic-cards__workflow-meta">
        {meta.map((item) => (
          <div key={item.label} className="agent-generic-cards__workflow-meta-item">
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function renderWorkflowIntentsCard(card: AgentGenericCard) {
  const rows = Array.isArray(card.data) ? card.data : [];

  return (
    <section
      key={`${card.title}-${card.type}`}
      className="agent-generic-cards__card agent-generic-cards__card--workflow"
      data-testid="agent-workflow-intents-card"
    >
      <div className="agent-generic-cards__workflow-header">
        <h3 className="agent-generic-cards__title">子任务编排</h3>
        <span className="agent-generic-cards__workflow-count">{rows.length} 个子任务</span>
      </div>
      <ol className="agent-generic-cards__intent-list">
        {rows.map((row, index) => {
          const intentId = textValue(row.intent) || EM_DASH;
          const order = typeof row.order === "number" ? row.order : index + 1;
          return (
            <li key={`${intentId}-${order}`} className="agent-generic-cards__intent-item">
              <span className="agent-generic-cards__intent-order">
                {String(order).padStart(2, "0")}
              </span>
              <div className="agent-generic-cards__intent-main">
                <strong>{INTENT_TITLES[intentId] ?? intentId}</strong>
                <code aria-label={`意图标识 ${intentId}`}>{intentId}</code>
              </div>
              <span className="agent-generic-cards__intent-state">待人工执行</span>
            </li>
          );
        })}
      </ol>
      <p className="agent-generic-cards__workflow-boundary">只读计划，不会自动执行。</p>
    </section>
  );
}

function renderGovernanceNotesCard(card: AgentGenericCard) {
  const rows = Array.isArray(card.data) ? card.data : [];

  return (
    <section
      key={`${card.title}-${card.type}`}
      className="agent-generic-cards__card agent-generic-cards__card--workflow"
      data-testid="agent-governance-notes-card"
    >
      <div className="agent-generic-cards__workflow-header">
        <h3 className="agent-generic-cards__title">治理边界</h3>
        <span className="agent-generic-cards__governance-state">人工决策</span>
      </div>
      <ul className="agent-generic-cards__governance-list">
        {rows.map((row, index) => {
          const note = textValue(row.note);
          return (
            <li key={`${note}-${index}`} title={note || undefined}>
              {(GOVERNANCE_NOTES[note] ?? note) || EM_DASH}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function renderLinkListCard(card: AgentGenericCard) {
  const rows = Array.isArray(card.data) ? card.data : [];

  return (
    <div key={`${card.title}-${card.type}`} className="agent-generic-cards__card">
      <div className="agent-generic-cards__title agent-generic-cards__title--spaced">{card.title}</div>
      <div className="agent-generic-cards__rows agent-generic-cards__rows--links">
        {rows.map((row, index) => {
          const label = typeof row.label === "string" ? row.label : `Link ${index + 1}`;
          const href = safeInternalHref(row.href);
          const description = typeof row.description === "string" ? row.description : "";
          return (
            <div key={`${card.title}-link-${index}`} className="agent-generic-cards__row">
              <a href={href} className="agent-generic-cards__link">
                {label}
              </a>
              {description ? (
                <div className="agent-generic-cards__description">{description}</div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function renderMarkdownCard(card: AgentGenericCard) {
  const text = String(card.value ?? "").trim();
  return (
    <div
      key={`${card.title}-${card.type}`}
      className="agent-generic-cards__card agent-generic-cards__card--memo"
    >
      <div className="agent-generic-cards__title">{displayCardTitle(card.title)}</div>
      <div className="agent-generic-cards__memo" data-testid="agent-memo-card-body">
        {text || EM_DASH}
      </div>
    </div>
  );
}

function renderScalarCard(card: AgentGenericCard) {
  return (
    <div key={`${card.title}-${card.type}`} className="agent-generic-cards__card">
      <div className="agent-generic-cards__title">{displayCardTitle(card.title)}</div>
      <div className="agent-generic-cards__scalar">{String(card.value ?? EM_DASH)}</div>
      <div className="agent-generic-cards__type">{formatCardType(card.type)}</div>
    </div>
  );
}

export function AgentGenericCardsGrid({
  cards,
  formatValue,
}: {
  cards: AgentGenericCard[];
  formatValue: (value: unknown) => string;
}) {
  if (!cards.length) {
    return null;
  }

  return (
    <div className="agent-generic-cards">
      {cards.map((card) => {
        if (card.type === "workflow_plan") {
          return renderWorkflowPlanCard(card);
        }
        if (card.type === "workflow_intents") {
          return renderWorkflowIntentsCard(card);
        }
        if (card.type === "governance_notes") {
          return renderGovernanceNotesCard(card);
        }
        if (card.type === "link_list") {
          return renderLinkListCard(card);
        }
        if (card.type === "markdown") {
          return renderMarkdownCard(card);
        }
        if (card.type === "table" || card.type === "resource" || card.data !== undefined) {
          return renderStructuredCard(card, formatValue);
        }
        return renderScalarCard(card);
      })}
    </div>
  );
}
