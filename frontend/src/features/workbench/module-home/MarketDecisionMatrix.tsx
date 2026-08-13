import dhStyles from "../dashboard-home/dashboardHome.module.css";
import { EM_DASH } from "../../../utils/format";
import { marketChangePresentation } from "./marketHomeChangeTone";
import type { ModuleHomeDetailPanel, ModuleHomeDetailRow, ModuleHomeTone, ModuleHomeView } from "./moduleHomeModel";
import marketStyles from "./marketHome.module.css";

const MARKET_CHANGE_CLASSES = {
  up: dhStyles.dhUpRed,
  down: dhStyles.dhDownGreen,
  neutral: dhStyles.dhMuted,
} as const;

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
  summaryDetail?: string;
  summarySparkline?: readonly number[];
  meta: string[];
  evidence: string[];
  tone: ModuleHomeTone;
  auditOnly?: boolean;
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
  return new Set(panel?.rows.map((row) => row.source).filter((source) => source && source !== EM_DASH) ?? []).size;
}

function panelWithRows(primary?: ModuleHomeDetailPanel, fallback?: ModuleHomeDetailPanel) {
  return primary && primary.rows.length > 0 ? primary : fallback;
}

function compactParts(parts: Array<string | undefined | null>) {
  return parts.map((part) => part?.trim()).filter((part): part is string => Boolean(part && part !== EM_DASH));
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

function rowMeta(row?: ModuleHomeDetailRow) {
  if (!row) return [];
  return compactParts([validDate(row.tradeDate) ? row.tradeDate : null, row.detail, row.source]);
}

function rowSummary(row?: ModuleHomeDetailRow) {
  if (!row) return [];
  return compactParts([row.detail, validDate(row.tradeDate) ? row.tradeDate : null]);
}

function matrixChangeText(item: MatrixItem) {
  if (item.summaryDetail?.trim()) {
    return item.summaryDetail;
  }
  return item.summary[0] ?? "—";
}

function matrixImplication(item: MatrixItem, direction: string | undefined) {
  if (item.key === "rates") {
    if (item.headline === "待曲线核验") return "先补曲线，再定久期";
    if (direction === "up") return "长端上行，复核久期压力";
    if (direction === "down") return "长端下行，观察久期弹性";
    return "长端平稳，维持曲线监控";
  }
  if (item.key === "liquidity") {
    if (direction === "up") return "资金收紧，控制融资敏感仓位";
    if (direction === "down") return "资金缓和，观察杠杆承接";
    return "资金平稳，维持杠杆监控";
  }
  if (item.key === "cross-asset") {
    if (direction === "up") return "风险偏好抬升，观察债市承压";
    if (direction === "down") return "风险偏好走弱，复核股债传导";
    return "跨资产平稳，等待下钻确认";
  }
  if (item.key === "macro") {
    if (item.tone === "error") return "宏观缺口，先核验读链路";
    if (item.tone === "watch") return "宏观中性，策略保持复核";
    return "宏观信号可读，跟踪策略摘要";
  }
  return "作为读链路状态复核";
}

function findRow(panel: ModuleHomeDetailPanel | undefined, patterns: string[]) {
  return panel?.rows.find((row) => patterns.some((pattern) => `${row.key} ${row.label} ${row.source}`.includes(pattern)));
}

function panelCoverage(panel: ModuleHomeDetailPanel | undefined, fallbackDate?: string) {
  const date = latestPanelDate(panel) ?? fallbackDate ?? EM_DASH;
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
    macroOverviewPanel?.rows.find((row) => row.key === "macro-stance") ??
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
      summaryDetail: rateRow?.detail,
      summarySparkline: rateRow?.sparkline,
      meta: panelCoverage(ratePanel, formalTradeDate),
      evidence: rateRow ? rowMeta(rateRow) : compactParts([yieldCurvePanel?.stateDetail ?? keyRatePanel?.stateDetail]),
      tone: yieldCurvePanel?.tone ?? keyRatePanel?.tone ?? "muted",
    },
    {
      key: "liquidity",
      label: "流动性",
      headline: rowHeadline(liquidity),
      summary: rowSummary(liquidity),
      summaryDetail: liquidity?.detail,
      summarySparkline: liquidity?.sparkline,
      meta: liquidity ? rowMeta(liquidity) : panelCoverage(keyRatePanel, latestTradeDate),
      evidence: compactParts([keyRatePanel?.stateDetail]),
      tone: liquidity?.tone ?? keyRatePanel?.tone ?? "muted",
    },
    {
      key: "cross-asset",
      label: "跨资产",
      headline: rowHeadline(crossAsset),
      summary: rowSummary(crossAsset),
      summaryDetail: crossAsset?.detail,
      summarySparkline: crossAsset?.sparkline,
      meta: panelCoverage(macroPanel, latestTradeDate),
      evidence: compactParts([macroPanel?.meta]),
      tone: macroPanel?.tone ?? "muted",
    },
    {
      key: "macro",
      label: "宏观归因",
      headline: rowHeadline(macroStance),
      summary: rowSummary(macroStance),
      summaryDetail: macroStance?.detail,
      summarySparkline: macroStance?.sparkline,
      meta: panelCoverage(macroOverviewPanel, latestTradeDate),
      evidence: compactParts([macroOverviewPanel?.stateDetail]),
      tone: macroStance?.tone ?? macroOverviewPanel?.tone ?? "muted",
    },
    {
      key: "data",
      label: "数据闸门",
      headline: view.stateLabel,
      summary: [],
      meta: compactParts([formalPanel?.stateLabel, `最新 ${latestTradeDate || EM_DASH}`, `正式 ${formalTradeDate || EM_DASH}`]),
      evidence: catalogPanel ? panelCoverage(catalogPanel, formalTradeDate) : compactParts([view.sourceScope]),
      tone: errorCount > 0 ? "error" : watchCount > 0 ? "watch" : "ok",
      auditOnly: true,
    },
  ];

  return (
    <section
      className={`${dhStyles.dhCard} ${marketStyles.decisionMatrix} ${marketStyles.marketDeskPanel}`}
      data-testid="module-home-market-matrix"
    >
      <div className={marketStyles.decisionMatrixHeader}>
        <span>市场决策要点</span>
        <em>读数 / 变动 / 组合观察</em>
        <i className={marketStyles.marketAuditOnly} data-testid="module-home-market-matrix-audit-label" hidden>
          Market Decision Tape
        </i>
      </div>
      <div className={marketStyles.decisionMatrixTape}>
        <div aria-hidden="true" className={marketStyles.decisionMatrixTableHead}>
          <span>维度</span>
          <span>读数</span>
          <span>变动</span>
          <span>组合观察</span>
        </div>
        {items.map((item) => {
          const summaryChange = marketChangePresentation(
            item.summaryDetail,
            item.summarySparkline,
            MARKET_CHANGE_CLASSES,
          );
          const changeText = matrixChangeText(item);
          const implication = matrixImplication(item, summaryChange.direction);

          if (item.auditOnly) {
            return (
              <div
                className={marketStyles.decisionMatrixTableRow}
                data-testid={`module-home-market-matrix-cell-${item.key}`}
                data-tone={item.tone}
                hidden
                key={item.key}
              >
                <span className={marketStyles.decisionMatrixTableLabel}>{item.label}</span>
                <strong data-testid={`module-home-market-matrix-cell-${item.key}-headline`}>{item.headline}</strong>
                <span data-testid={`module-home-market-matrix-cell-${item.key}-summary`}>—</span>
                <span data-testid={`module-home-market-matrix-cell-${item.key}-implication`}>{implication}</span>
                <em
                  aria-label={item.meta.length > 0 ? item.meta.join(" / ") : undefined}
                  className={marketStyles.decisionMatrixMeta}
                  data-testid={`module-home-market-matrix-cell-${item.key}-meta`}
                >
                  {item.meta.length > 0 ? renderFieldSegments(item.meta) : <span>待返回</span>}
                </em>
                <p
                  className={marketStyles.decisionMatrixEvidence}
                  aria-label={item.evidence.length > 0 ? item.evidence.join(" / ") : undefined}
                  data-testid={`module-home-market-matrix-cell-${item.key}-evidence`}
                >
                  {item.evidence.length > 0 ? renderFieldSegments(item.evidence) : <span>待返回</span>}
                </p>
              </div>
            );
          }

          return (
            <div
              className={marketStyles.decisionMatrixTableRow}
              data-testid={`module-home-market-matrix-cell-${item.key}`}
              data-tone={item.tone}
              key={item.key}
            >
              <span className={marketStyles.decisionMatrixTableLabel}>{item.label}</span>
              <strong
                className={`${marketStyles.decisionMatrixTableValue} ${dhStyles.dhNum} ${marketStyles.marketMetricNum} ${toneClass(item.tone)}`}
                data-testid={`module-home-market-matrix-cell-${item.key}-headline`}
              >
                {item.headline}
              </strong>
              <span
                className={`${marketStyles.decisionMatrixTableChange} ${dhStyles.dhNum} ${marketStyles.marketMetricNum} ${summaryChange.className}`}
                data-change={summaryChange.direction ?? "flat"}
                data-testid={`module-home-market-matrix-cell-${item.key}-summary`}
              >
                {changeText}
              </span>
              <span
                className={marketStyles.decisionMatrixTableImplication}
                data-testid={`module-home-market-matrix-cell-${item.key}-implication`}
              >
                {implication}
              </span>
              <em
                aria-label={item.meta.length > 0 ? item.meta.join(" / ") : undefined}
                className={marketStyles.decisionMatrixMeta}
                data-testid={`module-home-market-matrix-cell-${item.key}-meta`}
                hidden
              >
                {item.meta.length > 0 ? renderFieldSegments(item.meta) : <span>待返回</span>}
              </em>
              <p
                className={marketStyles.decisionMatrixEvidence}
                aria-label={item.evidence.length > 0 ? item.evidence.join(" / ") : undefined}
                data-testid={`module-home-market-matrix-cell-${item.key}-evidence`}
                hidden
              >
                {item.evidence.length > 0 ? renderFieldSegments(item.evidence) : <span>待返回</span>}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
