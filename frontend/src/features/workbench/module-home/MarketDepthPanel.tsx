import type { ComponentType } from "react";

import dhStyles from "../dashboard-home/dashboardHome.module.css";
import { EM_DASH } from "../../../utils/format";
import type { MarketVisualAccent } from "./marketEvidenceVisual";
import { marketChangePresentation } from "./marketHomeChangeTone";
import type { MarketIconProps } from "./marketHomeIcons";
import { MarketMacroPanelShell } from "./MarketMacroPanelShell";
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

type PanelShellConfig = {
  kicker: string;
  icon: ComponentType<MarketIconProps>;
  accent?: MarketVisualAccent;
};

type MarketDepthPanelProps = {
  panel: ModuleHomeDetailPanel;
  testId: string;
  compact?: boolean;
  /** Chart-first home ladder: label-only row, date muted below, series_id in tooltip only */
  compactLadder?: boolean;
  /** Hide per-row trade dates in compactLadder mode (home depth zone). */
  hideLadderDates?: boolean;
  /** Strip date segments from shell meta line. */
  hideMetaDate?: boolean;
  chartHeight?: number;
  className?: string;
  layout?: "split" | "chart-first";
  shell?: PanelShellConfig;
  hideChartTitle?: boolean;
};

function depthTable(panel: ModuleHomeDetailPanel, compact: boolean, compactLadder: boolean, hideLadderDates: boolean) {
  const tableClassName = [
    marketStyles.terminalTable,
    marketStyles.panelScroll,
    marketStyles.terminalTableLadder,
    compactLadder ? marketStyles.terminalTableLadderCompact : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={tableClassName}>
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
        const sourceMeta = compactLadder
          ? hideLadderDates
            ? null
            : row.tradeDate !== EM_DASH
              ? row.tradeDate
              : null
          : [row.tradeDate !== EM_DASH ? row.tradeDate : null, row.source !== EM_DASH ? row.source : null]
              .filter(Boolean)
              .join(" · ");
        const labelTitle =
          compactLadder && row.source !== EM_DASH
            ? `${row.label} · ${row.source}`
            : row.label;
        return (
          <div className={marketStyles.terminalTableRow} data-testid={`module-home-depth-${row.key}`} key={row.key}>
            <div className={marketStyles.terminalTableMain}>
              <span className={marketStyles.terminalTableLabel} title={labelTitle}>
                {row.label}
              </span>
              {sourceMeta ? (
                <span
                  className={marketStyles.terminalTableSource}
                  title={compactLadder && row.source !== EM_DASH ? row.source : undefined}
                >
                  {sourceMeta}
                </span>
              ) : null}
            </div>
            <span className={`${marketStyles.terminalTableValue} ${dhStyles.dhNum} ${toneClass(row.tone)}`}>
              {rowDisplayValue(row)}
            </span>
            <span
              className={`${marketStyles.terminalTableChange} ${dhStyles.dhNum} ${change.className}`}
              data-change={change.direction ?? "flat"}
            >
              {changeText ?? EM_DASH}
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
  compactLadder = false,
  hideLadderDates = false,
  hideMetaDate = false,
  chartHeight = compact ? 160 : 180,
  className,
  layout = "split",
  shell,
  hideChartTitle = false,
}: MarketDepthPanelProps) {
  const hasChart = Boolean(panel.chart && panel.chart.categories.length > 0);
  const isEmpty = panel.rows.length === 0 && !hasChart;
  const chartBlock =
    hasChart && panel.chart ? (
      <div className={`${dhStyles.dhInsetSurface} ${marketStyles.terminalChart} ${shell ? marketStyles.terminalChartHero : ""}`}>
        <PortfolioStructureChart chart={panel.chart} height={chartHeight} hideTitle={hideChartTitle || Boolean(shell)} />
      </div>
    ) : null;
  const tableBlock =
    panel.rows.length > 0 ? (
      depthTable(panel, compact, compactLadder, hideLadderDates)
    ) : (
      <p className={marketStyles.panelEmpty}>{panel.stateDetail}</p>
    );
  const bodyClass =
    layout === "chart-first" && hasChart
      ? marketStyles.depthPanelBodyChartFirst
      : hasChart
        ? marketStyles.depthPanelBodySplit
        : marketStyles.depthPanelBody;

  const body = (
    <>
      {!shell ? <p className={marketStyles.panelMeta}>{panel.meta}</p> : null}
      {!shell ? <MarketPanelSummary panel={panel} /> : null}
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
    </>
  );

  if (shell) {
    return (
      <MarketMacroPanelShell
        accent={shell.accent ?? "navy"}
        className={`${isEmpty ? marketStyles.marketCompactEmptyPanel : ""} ${className ?? ""} ${marketStyles.depthPanelShell}`}
        hideMetaDate={hideMetaDate}
        icon={shell.icon}
        kicker={shell.kicker}
        meta={panel.meta}
        statusLabel={panel.stateLabel}
        testId={testId}
        title={panel.title}
      >
        {body}
      </MarketMacroPanelShell>
    );
  }

  return (
    <article
      className={`${dhStyles.dhCard} ${marketStyles.marketDeskPanel} ${marketStyles.depthPanel} ${isEmpty ? marketStyles.marketCompactEmptyPanel : ""} ${className ?? ""}`}
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
