import dhStyles from "../dashboard-home/dashboardHome.module.css";
import type { ModuleHomeDetailPanel, ModuleHomeTone } from "./moduleHomeModel";
import { PortfolioStructureChart } from "./PortfolioStructureChart";
import marketStyles from "./marketHome.module.css";

function toneClass(tone: ModuleHomeTone) {
  if (tone === "watch") return dhStyles.dhMuted;
  if (tone === "error") return dhStyles.dhUpRed;
  return "";
}

type MarketDepthPanelProps = {
  panel: ModuleHomeDetailPanel;
  testId: string;
  compact?: boolean;
};

export function MarketDepthPanel({ panel, testId, compact = false }: MarketDepthPanelProps) {
  const hasChart = Boolean(panel.chart && panel.chart.categories.length > 0);

  return (
    <article className={`${dhStyles.dhCard} ${marketStyles.depthPanel}`} data-testid={testId}>
      <div className={dhStyles.dhSectionTitle}>
        <span>{panel.title}</span>
        <span className={marketStyles.statusChip}>{panel.stateLabel}</span>
      </div>
      <p className={marketStyles.panelMeta}>{panel.meta}</p>
      {panel.rows.length > 0 ? (
        <div className={`${marketStyles.terminalTable} ${marketStyles.panelScroll}`}>
          {!compact ? (
            <div className={marketStyles.terminalTableHead} aria-hidden="true">
              <span>序列</span>
              <span>最新</span>
            </div>
          ) : null}
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
      )}
      {hasChart && panel.chart ? (
        <div className={`${dhStyles.dhInsetSurface} ${marketStyles.terminalChart}`}>
          <PortfolioStructureChart chart={panel.chart} />
        </div>
      ) : null}
    </article>
  );
}
