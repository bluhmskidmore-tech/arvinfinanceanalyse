import { shellTokens as t } from "../../../theme/tokens";
import { PlaceholderCard } from "../../workbench/components/PlaceholderCard";

type AgentGenericCard = {
  title: string;
  value?: string;
  type: string;
  data?: Record<string, unknown>[] | Record<string, unknown>;
  spec?: Record<string, unknown>;
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

function renderStructuredCard(card: AgentGenericCard, formatValue: (value: unknown) => string) {
  const columns = columnsForCard(card);
  const rows = Array.isArray(card.data)
    ? card.data
    : isRecord(card.data)
      ? Object.entries(card.data).map(([key, value]) => ({ key, value }))
      : [];

  return (
    <div
      key={`${card.title}-${card.type}`}
      style={{
        padding: 16,
        borderRadius: 16,
        border: `1px solid ${t.colorBorderSoft}`,
        background: t.colorBgCanvas,
      }}
    >
      <div
        style={{
          color: t.colorTextPrimary,
          fontSize: 15,
          fontWeight: 600,
          marginBottom: 6,
        }}
      >
        {card.title}
      </div>
      {card.value ? (
        <div
          style={{
            color: t.colorTextSecondary,
            fontSize: 13,
            marginBottom: rows.length > 0 ? 10 : 0,
            wordBreak: "break-all",
          }}
        >
          {card.value}
        </div>
      ) : null}
      {rows.length > 0 ? (
        <div
          style={{
            display: "grid",
            gap: 8,
          }}
        >
          {columns.length > 0 ? (
            <div
              style={{
                display: "grid",
                gap: 6,
              }}
            >
              {rows.map((row, index) => (
                <div
                  key={`${card.title}-row-${index}`}
                  style={{
                    borderRadius: 12,
                    background: t.colorBgSurface,
                    padding: 10,
                    display: "grid",
                    gap: 4,
                  }}
                >
                  {columns.map((column) => (
                    <div
                      key={`${card.title}-${index}-${column}`}
                      style={{
                        display: "flex",
                        gap: 6,
                        flexWrap: "wrap",
                        fontSize: 13,
                        color: t.colorTextSecondary,
                      }}
                    >
                      <span style={{ color: t.colorTextMuted }}>{column}:</span>
                      <span>{formatValue((row as Record<string, unknown>)[column])}</span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
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
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
        gap: 14,
      }}
    >
      {cards.map((card) => {
        if (card.type === "table" || card.type === "resource" || card.data !== undefined) {
          return renderStructuredCard(card, formatValue);
        }
        return (
          <PlaceholderCard
            key={`${card.title}-${card.type}`}
            title={card.title}
            value={String(card.value ?? "--")}
            detail={card.type}
          />
        );
      })}
    </div>
  );
}
