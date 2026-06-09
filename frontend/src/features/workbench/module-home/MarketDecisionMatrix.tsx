import dhStyles from "../dashboard-home/dashboardHome.module.css";
import type { ModuleHomeDetailPanel, ModuleHomeDetailRow, ModuleHomeTone, ModuleHomeView } from "./moduleHomeModel";
import marketStyles from "./marketHome.module.css";

type MarketDecisionMatrixProps = {
  view: ModuleHomeView;
  latestTradeDate: string;
  formalTradeDate: string;
  keyRatePanel?: ModuleHomeDetailPanel;
  yieldCurvePanel?: ModuleHomeDetailPanel;
  macroPanel?: ModuleHomeDetailPanel;
  formalPanel?: ModuleHomeDetailPanel;
  catalogPanel?: ModuleHomeDetailPanel;
  macroOverviewPanel?: ModuleHomeDetailPanel;
};

type MatrixItem = {
  key: string;
  label: string;
  headline: string;
  summary: string[];
  meta: string[];
  evidence: string[];
  tone: ModuleHomeTone;
};

function toneClass(tone: ModuleHomeTone) {
  if (tone === "watch") return dhStyles.dhMuted;
  if (tone === "error") return dhStyles.dhUpRed;
  return "";
}

function validDate(date: string | undefined) {
  return date && /^\d{4}-\d{2}-\d{2}$/.test(date);
}

function latestPanelDate(panel?: ModuleHomeDetailPanel) {
  return panel?.rows
    .map((row) => row.tradeDate)
    .filter(validDate)
    .sort()
    .at(-1);
}

function panelSourceCount(panel?: ModuleHomeDetailPanel) {
  return new Set(panel?.rows.map((row) => row.source).filter((source) => source && source !== "-") ?? []).size;
}

function panelWithRows(primary?: ModuleHomeDetailPanel, fallback?: ModuleHomeDetailPanel) {
  return primary && primary.rows.length > 0 ? primary : fallback;
}

function compactParts(parts: Array<string | undefined | null>) {
  return parts.map((part) => part?.trim()).filter((part): part is string => Boolean(part && part !== "-"));
}

function renderFieldSegments(parts: string[]) {
  return parts.flatMap((part, index) =>
    index > 0
      ? [
          <span className={marketStyles.fieldSeparator} key={`${part}-${index}-separator`}>
            {" / "}
          </span>,
          <span key={`${part}-${index}`}>{part}</span>,
        ]
      : [<span key={`${part}-${index}`}>{part}</span>],
  );
}

function rowHeadline(row?: ModuleHomeDetailRow, fallback = "待返回") {
  return row ? `${row.label} ${row.value}` : fallback;
}

function renderBlockTextSeparator(key: string) {
  return (
    <span aria-hidden="true" className={marketStyles.blockTextSeparator} hidden key={key}>
      {" / "}
    </span>
  );
}

function rowMeta(row?: ModuleHomeDetailRow) {
  if (!row) return [];
  return compactParts([validDate(row.tradeDate) ? row.tradeDate : null, row.detail, row.source]);
}

function rowSummary(row?: ModuleHomeDetailRow) {
  if (!row) return [];
  return compactParts([row.detail, validDate(row.tradeDate) ? row.tradeDate : null]);
}

function findRow(panel: ModuleHomeDetailPanel | undefined, patterns: string[]) {
  return panel?.rows.find((row) => patterns.some((pattern) => `${row.key} ${row.label} ${row.source}`.includes(pattern)));
}

function panelCoverage(panel: ModuleHomeDetailPanel | undefined, fallbackDate?: string) {
  const date = latestPanelDate(panel) ?? fallbackDate ?? "-";
  const rowCount = panel?.rows.length ?? 0;
  const sourceCount = panelSourceCount(panel);
  return compactParts([`${rowCount} 条`, `${sourceCount} 源`, date]);
}

function statusCount(view: ModuleHomeView, tone: ModuleHomeTone) {
  return view.statuses.filter((status) => status.tone === tone).length;
}

export function MarketDecisionMatrix({
  view,
  latestTradeDate,
  formalTradeDate,
  keyRatePanel,
  yieldCurvePanel,
  macroPanel,
  formalPanel,
  catalogPanel,
  macroOverviewPanel,
}: MarketDecisionMatrixProps) {
  const tenYear = findRow(keyRatePanel, ["10Y", "10年", "十年"]);
  const liquidity = findRow(keyRatePanel, ["DR007", "SHIBOR", "shibor"]);
  const rateRow = tenYear ?? yieldCurvePanel?.rows[0];
  const ratePanel = panelWithRows(yieldCurvePanel, keyRatePanel);
  const crossAsset = macroPanel?.rows[0];
  const macroStance =
    macroOverviewPanel?.rows.find((row) => row.key.includes("stance") || row.label.includes("结论")) ??
    macroOverviewPanel?.rows[0];
  const watchCount = statusCount(view, "watch");
  const errorCount = statusCount(view, "error");

  const items: MatrixItem[] = [
    {
      key: "rates",
      label: "利率曲线",
      headline: rowHeadline(rateRow, "待曲线核验"),
      summary: rateRow ? rowSummary(rateRow) : compactParts([yieldCurvePanel?.stateDetail ?? keyRatePanel?.stateDetail]),
      meta: panelCoverage(ratePanel, formalTradeDate),
      evidence: rateRow ? rowMeta(rateRow) : compactParts([yieldCurvePanel?.stateDetail ?? keyRatePanel?.stateDetail]),
      tone: yieldCurvePanel?.tone ?? keyRatePanel?.tone ?? "muted",
    },
    {
      key: "liquidity",
      label: "流动性",
      headline: rowHeadline(liquidity),
      summary: rowSummary(liquidity),
      meta: liquidity ? rowMeta(liquidity) : panelCoverage(keyRatePanel, latestTradeDate),
      evidence: compactParts([keyRatePanel?.stateDetail]),
      tone: liquidity?.tone ?? keyRatePanel?.tone ?? "muted",
    },
    {
      key: "cross-asset",
      label: "跨资产",
      headline: rowHeadline(crossAsset),
      summary: rowSummary(crossAsset),
      meta: panelCoverage(macroPanel, latestTradeDate),
      evidence: compactParts([macroPanel?.meta]),
      tone: macroPanel?.tone ?? "muted",
    },
    {
      key: "macro",
      label: "宏观归因",
      headline: rowHeadline(macroStance),
      summary: rowSummary(macroStance),
      meta: panelCoverage(macroOverviewPanel, latestTradeDate),
      evidence: compactParts([macroOverviewPanel?.stateDetail]),
      tone: macroStance?.tone ?? macroOverviewPanel?.tone ?? "muted",
    },
    {
      key: "data",
      label: "数据闸门",
      headline: view.stateLabel,
      summary: [],
      meta: compactParts([formalPanel?.stateLabel, `最新 ${latestTradeDate || "-"}`, `正式 ${formalTradeDate || "-"}`]),
      evidence: catalogPanel ? panelCoverage(catalogPanel, formalTradeDate) : compactParts([view.sourceScope]),
      tone: errorCount > 0 ? "error" : watchCount > 0 ? "watch" : "ok",
    },
  ];
  return (
    <section className={marketStyles.decisionMatrix} data-testid="module-home-market-matrix">
      <div className={marketStyles.decisionMatrixHeader}>
        <span>交易建议与约束检查</span>
        <em>利率 / 流动性 / 跨资产 / 宏观</em>
        <i className={marketStyles.marketAuditOnly} hidden>
          Market Decision Tape
        </i>
      </div>
      <div className={marketStyles.decisionMatrixGrid}>
        {items.map((item) => (
          <article
            className={marketStyles.decisionMatrixCell}
            data-testid={`module-home-market-matrix-cell-${item.key}`}
            data-tone={item.tone}
            key={item.key}
          >
            <span>{item.label}</span>
            <strong
              className={`${dhStyles.dhNum} ${toneClass(item.tone)}`}
              data-testid={`module-home-market-matrix-cell-${item.key}-headline`}
            >
              {item.headline}
            </strong>
            {item.summary.length > 0 ? (
              <small className={marketStyles.decisionMatrixSummary}>{renderFieldSegments(item.summary)}</small>
            ) : null}
            {renderBlockTextSeparator(`${item.key}-headline-meta`)}
            <em
              aria-label={item.meta.length > 0 ? item.meta.join(" / ") : undefined}
              className={marketStyles.decisionMatrixMeta}
              data-testid={`module-home-market-matrix-cell-${item.key}-meta`}
            >
              {item.meta.length > 0 ? renderFieldSegments(item.meta) : <span>待返回</span>}
            </em>
            {renderBlockTextSeparator(`${item.key}-meta-evidence`)}
            <p
              className={marketStyles.decisionMatrixEvidence}
              aria-label={item.evidence.length > 0 ? item.evidence.join(" / ") : undefined}
              data-testid={`module-home-market-matrix-cell-${item.key}-evidence`}
            >
              {item.evidence.length > 0 ? renderFieldSegments(item.evidence) : <span>待返回</span>}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
