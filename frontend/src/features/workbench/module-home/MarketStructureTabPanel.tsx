import type { ModuleHomeDetailPanel, ModuleHomeTone } from "./moduleHomeModel";
import { PortfolioStructureChart } from "./PortfolioStructureChart";
import dhStyles from "../dashboard-home/dashboardHome.module.css";
import { MarketPanelSummary } from "./MarketPanelSummary";
import marketStyles from "./marketHome.module.css";

const DEFAULT_TERMINAL_CHART_HEIGHT = 220;

function toneClass(tone: ModuleHomeTone) {
  if (tone === "watch") return dhStyles.dhMuted;
  if (tone === "error") return dhStyles.dhUpRed;
  return "";
}

type MarketStructureTabPanelProps = {
  panel: ModuleHomeDetailPanel;
  chartHeight?: number;
};

export function MarketStructureTabPanel({
  panel,
  chartHeight = DEFAULT_TERMINAL_CHART_HEIGHT,
}: MarketStructureTabPanelProps) {
  const hasChart = Boolean(panel.chart && panel.chart.categories.length > 0);
  const chartBlock =
    hasChart && panel.chart ? (
      <div className={`${dhStyles.dhInsetSurface} ${marketStyles.terminalChart}`}>
        <PortfolioStructureChart chart={panel.chart} height={chartHeight} />
      </div>
    ) : null;
  const tableBlock =
    panel.rows.length > 0 ? (
      <div className={`${marketStyles.terminalTable} ${marketStyles.terminalTableScroll}`}>
        <div className={marketStyles.terminalTableHead} aria-hidden="true">
          <span>序列</span>
          <span>最新</span>
        </div>
        {panel.rows.map((row) => (
          <div className={marketStyles.terminalTableRow} key={row.key}>
            <div className={marketStyles.terminalTableMain}>
              <span className={marketStyles.terminalTableLabel}>{row.label}</span>
              <span className={marketStyles.terminalTableSource}>
                {[row.tradeDate !== "-" ? row.tradeDate : null, row.source !== "-" ? row.source : null]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            </div>
            <span className={`${marketStyles.terminalTableValue} ${dhStyles.dhNum} ${toneClass(row.tone)}`}>
              {row.value}
            </span>
          </div>
        ))}
      </div>
    ) : (
      <p className={marketStyles.panelEmpty}>{panel.stateDetail}</p>
    );

  return (
    <div
      className={`${marketStyles.terminalPanel} ${hasChart ? marketStyles.terminalPanelChartFirst : ""}`}
    >
      <div className={marketStyles.terminalPanelMeta}>
        <p className={marketStyles.panelMeta}>{panel.meta}</p>
        <span className={marketStyles.statusChip}>{panel.stateLabel}</span>
      </div>
      <MarketPanelSummary panel={panel} />
      <div className={hasChart ? marketStyles.terminalPanelBodyChartFirst : marketStyles.terminalPanelBody}>
        {hasChart ? (
          <>
            {chartBlock}
            {tableBlock}
          </>
        ) : (
          tableBlock
        )}
      </div>
    </div>
  );
}
