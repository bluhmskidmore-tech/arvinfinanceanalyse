import "./AgentGenericCardsGrid.css";

import { EM_DASH } from "../../../utils/format";
type AgentGenericCard = {
  title: string;
  value?: string | null;
  type: string;
  data?: Record<string, unknown>[] | Record<string, unknown> | null;
  spec?: Record<string, unknown> | null;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
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
      ? Object.entries(card.data).map(([key, value]) => ({ key, value }))
      : [];

  return (
    <div key={`${card.title}-${card.type}`} className="agent-generic-cards__card">
      <div className="agent-generic-cards__title">{card.title}</div>
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
      <div className="agent-generic-cards__title">{card.title}</div>
      <div className="agent-generic-cards__memo" data-testid="agent-memo-card-body">
        {text || EM_DASH}
      </div>
    </div>
  );
}

function renderScalarCard(card: AgentGenericCard) {
  return (
    <div key={`${card.title}-${card.type}`} className="agent-generic-cards__card">
      <div className="agent-generic-cards__title">{card.title}</div>
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
