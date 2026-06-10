import dhStyles from "../dashboard-home/dashboardHome.module.css";
import { marketChangePresentation } from "./marketHomeChangeTone";
import type { ModuleHomeDetailPanel, ModuleHomeTone } from "./moduleHomeModel";
import { rowChangeText, rowDisplayValue } from "./marketHomeRowDisplay";
import { MarketPanelSummary } from "./MarketPanelSummary";
import { PortfolioStructureChart } from "./PortfolioStructureChart";
import marketStyles from "./marketHome.module.css";

const MARKET_CHANGE_CLASSES = {
  up: dhStyles.dhUpRed,
  down: dhStyles.dhDownGreen,
  neutral: dhStyles.dhMuted,
} as const;

function toneClass(tone: ModuleHomeTone) {
  if (tone === "watch") return dhStyles.dhMuted;
  if (tone === "error") return dhStyles.dhUpRed;
  return "";
}

type MarketDepthPanelProps = {
  panel: ModuleHomeDetailPanel;
  testId: string;
  compact?: boolean;
  chartHeight?: number;
  className?: string;
  layout?: "split" | "chart-first";
};

function depthTable(panel: ModuleHomeDetailPanel, compact: boolean) {
  return (
    <div className={`${marketStyles.terminalTable} ${marketStyles.panelScroll}`}>
      <div
        aria-hidden="true"
        className={`${marketStyles.terminalTableHead} ${compact ? marketStyles.terminalTableHeadCompact : ""}`}
      >
        <span>序列</span>
        <span>最新</span>
        <span>{compact ? "Δ" : "变动"}</span>
      </div>
      {panel.rows.map((row) => {
        const changeText = rowChangeText(row);
        const change = marketChangePresentation(changeText, row.sparkline, MARKET_CHANGE_CLASSES);
        return (
          <div className={marketStyles.terminalTableRow} data-testid={`module-home-depth-${row.key}`} key={row.key}>
            <div className={marketStyles.terminalTableMain}>
              <span className={marketStyles.terminalTableLabel}>{row.label}</span>
              <span className={marketStyles.terminalTableSource}>
                {[row.tradeDate !== "-" ? row.tradeDate : null, row.source !== "-" ? row.source : null]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            </div>
            <span className={`${marketStyles.terminalTableValue} ${dhStyles.dhNum} ${toneClass(row.tone)}`}>
              {rowDisplayValue(row)}
            </span>
            <span
              className={`${marketStyles.terminalTableChange} ${dhStyles.dhNum} ${change.className}`}
              data-change={change.direction ?? "flat"}
            >
              {changeText ?? "—"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function MarketDepthPanel({
  panel,
  testId,
  compact = false,
  chartHeight = compact ? 160 : 180,
  className,
  layout = "split",
}: MarketDepthPanelProps) {
  const hasChart = Boolean(panel.chart && panel.chart.categories.length > 0);
  const isEmpty = panel.rows.length === 0 && !hasChart;
  const chartBlock =
    hasChart && panel.chart ? (
      <div className={`${dhStyles.dhInsetSurface} ${marketStyles.terminalChart}`}>
        <PortfolioStructureChart chart={panel.chart} height={chartHeight} />
      </div>
    ) : null;
  const tableBlock =
    panel.rows.length > 0 ? depthTable(panel, compact) : <p className={marketStyles.panelEmpty}>{panel.stateDetail}</p>;
  const bodyClass =
    layout === "chart-first" && hasChart
      ? marketStyles.depthPanelBodyChartFirst
      : hasChart
        ? marketStyles.depthPanelBodySplit
        : marketStyles.depthPanelBody;

  return (
    <article
      className={`${marketStyles.marketDeskPanel} ${marketStyles.depthPanel} ${isEmpty ? marketStyles.marketCompactEmptyPanel : ""} ${className ?? ""}`}
      data-testid={testId}
    >
      <div className={dhStyles.dhSectionTitle}>
        <span>{panel.title}</span>
        <span className={marketStyles.statusChip}>{panel.stateLabel}</span>
      </div>
      <p className={marketStyles.panelMeta}>{panel.meta}</p>
      <MarketPanelSummary panel={panel} />
      <div className={bodyClass}>
        {layout === "chart-first" && hasChart ? (
          <>
            {chartBlock}
            {tableBlock}
          </>
        ) : (
          <>
            {tableBlock}
            {chartBlock}
          </>
        )}
      </div>
    </article>
  );
}
