import { shellTokens as t } from "../../../theme/tokens";

type GitNexusResultCard = {
  title: string;
  value?: string;
  type: string;
  data?: Record<string, unknown>[] | Record<string, unknown>;
};

const GITNEXUS_PROCESS_CARD_TITLE = "GitNexus Processes Table";
const GITNEXUS_GROUP_COLORS: Record<string, string> = {
  api: "#2563eb",
  services: "#0f766e",
  repositories: "#9333ea",
  governance: "#b45309",
  core: "#be123c",
  tasks: "#166534",
  schemas: "#4f46e5",
  unknown: "#64748b",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function formatMetaValue(value: unknown) {
  if (value === null || value === undefined) {
    return "鈥?";
  }
  if (typeof value === "string") {
    return value.trim().length > 0 ? value : "鈥?";
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
    <div
      style={{
        display: "grid",
        gap: 16,
      }}
    >
      {summaryCards.length > 0 ? (
        <div
          style={{
            padding: 18,
            borderRadius: 18,
            border: `1px solid ${t.colorBorderSoft}`,
            background: t.colorBgCanvas,
            display: "grid",
            gap: 12,
          }}
        >
          <div
            style={{
              fontSize: 16,
              fontWeight: 600,
              color: t.colorTextPrimary,
            }}
          >
            Index Summary
          </div>
          {summaryMetricCards.length > 0 ? (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                gap: 10,
              }}
            >
              {summaryMetricCards.map((card) => (
                <div
                  key={`summary-${card.title}`}
                  style={{
                    padding: 12,
                    borderRadius: 14,
                    background: t.colorBgSurface,
                    display: "grid",
                    gap: 6,
                  }}
                >
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: t.colorTextMuted,
                      textTransform: "uppercase",
                    }}
                  >
                    {card.title}
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: t.colorTextPrimary }}>
                    {formatMetaValue(card.value)}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
          {summaryReferenceCards.length > 0 ? (
            <div
              style={{
                display: "grid",
                gap: 8,
              }}
            >
              {summaryReferenceCards.map((card) => (
                <div
                  key={`summary-ref-${card.title}`}
                  style={{
                    display: "flex",
                    gap: 8,
                    flexWrap: "wrap",
                    fontSize: 12,
                    color: t.colorTextSecondary,
                  }}
                >
                  <span style={{ color: t.colorTextMuted }}>{card.title}:</span>
                  <span>{formatMetaValue(card.value)}</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.2fr) minmax(0, 1fr)",
          gap: 16,
        }}
      >
        <div
          style={{
            padding: 18,
            borderRadius: 18,
            border: `1px solid ${t.colorBorderSoft}`,
            background: t.colorBgCanvas,
            display: "grid",
            gap: 12,
          }}
        >
          <div
            style={{
              fontSize: 16,
              fontWeight: 600,
              color: t.colorTextPrimary,
            }}
          >
            Context Overview
          </div>
          {contextCard?.value ? (
            <div
              style={{
                fontSize: 13,
                color: t.colorTextSecondary,
                wordBreak: "break-all",
              }}
            >
              {contextCard.value}
            </div>
          ) : null}
          {Array.isArray(contextCard?.data) ? (
            <div
              style={{
                display: "grid",
                gap: 6,
              }}
            >
              {contextCard.data.filter(isRecord).map((item, index) => (
                <div
                  key={`context-${index}`}
                  style={{
                    display: "flex",
                    gap: 8,
                    flexWrap: "wrap",
                    fontSize: 13,
                    color: t.colorTextSecondary,
                  }}
                >
                  <span style={{ color: t.colorTextMuted }}>
                    {String(item.label ?? "label")}:
                  </span>
                  <span>{formatMetaValue(item.value)}</span>
                </div>
              ))}
            </div>
          ) : null}
          {toolRows.length > 0 ? (
            <div
              style={{
                display: "grid",
                gap: 8,
              }}
            >
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: t.colorTextMuted,
                  textTransform: "uppercase",
                }}
              >
                Tools
              </div>
              {toolRows.map((row, index) => (
                <div
                  key={`tool-${index}`}
                  style={{
                    padding: 10,
                    borderRadius: 12,
                    background: t.colorBgSurface,
                    display: "grid",
                    gap: 4,
                  }}
                >
                  <div style={{ fontSize: 13, fontWeight: 600, color: t.colorTextPrimary }}>
                    {formatMetaValue(row.tool)}
                  </div>
                  <div style={{ fontSize: 12, color: t.colorTextSecondary }}>
                    {formatMetaValue(row.description)}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>

        <div
          style={{
            padding: 18,
            borderRadius: 18,
            border: `1px solid ${t.colorBorderSoft}`,
            background: t.colorBgCanvas,
            display: "grid",
            gap: 12,
          }}
        >
          <div
            style={{
              fontSize: 16,
              fontWeight: 600,
              color: t.colorTextPrimary,
            }}
          >
            Execution Flows
          </div>
          {processes.length > 0 ? (
            <div
              style={{
                display: "grid",
                gap: 8,
              }}
            >
              {processes.map((row, index) => (
                <div
                  key={`process-${index}`}
                  style={{
                    padding: 12,
                    borderRadius: 12,
                    background: t.colorBgSurface,
                    display: "grid",
                    gap: 4,
                  }}
                >
                  <div style={{ fontSize: 13, fontWeight: 600, color: t.colorTextPrimary }}>
                    {formatMetaValue(row.name)}
                  </div>
                  <div style={{ fontSize: 12, color: t.colorTextSecondary }}>
                    {formatMetaValue(row.type)} 路 steps {formatMetaValue(row.steps)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ fontSize: 13, color: t.colorTextSecondary }}>
              鏈繑鍥炴祦绋嬪垪琛ㄣ€?
            </div>
          )}
          {resourceRows.length > 0 ? (
            <div
              style={{
                display: "grid",
                gap: 6,
              }}
            >
              {resourceRows.map((row, index) => (
                <div
                  key={`resource-${index}`}
                  style={{
                    display: "flex",
                    gap: 8,
                    flexWrap: "wrap",
                    fontSize: 12,
                    color: t.colorTextSecondary,
                  }}
                >
                  <span style={{ color: t.colorTextMuted }}>{formatMetaValue(row.description)}:</span>
                  <span>{formatMetaValue(row.uri)}</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      {traceRows.length > 0 ? (
        <div
          style={{
            padding: 18,
            borderRadius: 18,
            border: `1px solid ${t.colorBorderSoft}`,
            background: t.colorBgCanvas,
            display: "grid",
            gap: 12,
          }}
        >
          <div
            style={{
              fontSize: 16,
              fontWeight: 600,
              color: t.colorTextPrimary,
            }}
          >
            Process Graph
          </div>
          <div
            style={{
              display: "flex",
              gap: 12,
              alignItems: "stretch",
              overflowX: "auto",
              paddingBottom: 4,
            }}
          >
            {traceRows.map((row, index) => {
              const moduleGroup = moduleGroupForTrace(row);
              const edgeLabel = edgeLabelForTrace(row);

              return (
                <div
                  key={`trace-${index}`}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    minWidth: 0,
                  }}
                >
                  <div
                    style={{
                      minWidth: 220,
                      padding: 14,
                      borderRadius: 16,
                      background: t.colorBgSurface,
                      border: `1px solid ${t.colorBorderSoft}`,
                      boxShadow: `inset 4px 0 0 ${moduleGroup.color}`,
                      display: "grid",
                      gap: 8,
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        gap: 12,
                        alignItems: "center",
                      }}
                    >
                      <span
                        style={{
                          fontSize: 12,
                          fontWeight: 700,
                          letterSpacing: "0.04em",
                          textTransform: "uppercase",
                          color: t.colorTextMuted,
                        }}
                      >
                        Step {formatMetaValue(row.step)}
                      </span>
                      <span
                        style={{
                          width: 30,
                          height: 30,
                          borderRadius: 999,
                          background: t.colorAccent,
                          color: t.colorBgCanvas,
                          display: "grid",
                          placeItems: "center",
                          fontSize: 12,
                          fontWeight: 700,
                        }}
                      >
                        {formatMetaValue(row.step)}
                      </span>
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: t.colorTextPrimary }}>
                      {formatMetaValue(row.symbol)}
                    </div>
                    <div
                      style={{
                        width: "fit-content",
                        padding: "4px 8px",
                        borderRadius: 999,
                        background: `${moduleGroup.color}14`,
                        color: moduleGroup.color,
                        fontSize: 11,
                        fontWeight: 700,
                        textTransform: "uppercase",
                        letterSpacing: "0.03em",
                      }}
                    >
                      {moduleGroup.label}
                    </div>
                    <div style={{ fontSize: 12, color: t.colorTextSecondary }}>
                      {formatMetaValue(row.file)}
                    </div>
                  </div>
                  {index < traceRows.length - 1 ? (
                    <div
                      aria-hidden="true"
                      style={{
                        display: "grid",
                        gap: 4,
                        justifyItems: "center",
                        color: t.colorTextMuted,
                        minWidth: 52,
                      }}
                    >
                      <div
                        style={{
                          padding: "4px 8px",
                          borderRadius: 999,
                          background: t.colorBgSurface,
                          border: `1px solid ${t.colorBorderSoft}`,
                          fontSize: 11,
                          fontWeight: 700,
                        }}
                      >
                        {edgeLabel}
                      </div>
                      <div
                        style={{
                          width: 36,
                          height: 2,
                          background: t.colorBorderSoft,
                        }}
                      />
                      <div style={{ fontSize: 12, fontWeight: 600 }}>鈫?</div>
                      <div
                        style={{
                          width: 36,
                          height: 2,
                          background: t.colorBorderSoft,
                        }}
                      />
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
