import { Link } from "react-router-dom";
import { Collapse, Tabs, type TabsProps } from "antd";

import dhStyles from "../dashboard-home/dashboardHome.module.css";
import { formatMacroSignalEvidence, marketSignalVisual, parseMacroSignalValue } from "./marketEvidenceVisual";
import { marketChangePresentation } from "./marketHomeChangeTone";
import { MarketIconMacroToolkit } from "./marketHomeIcons";
import { MarketMacroPanelShell } from "./MarketMacroPanelShell";
import { formatPanelMetaForHome, type ModuleHomeDetailPanel, type ModuleHomeTone } from "./moduleHomeModel";
import { MarketDepthPanel } from "./MarketDepthPanel";
import marketStyles from "./marketHome.module.css";

const MARKET_CHANGE_CLASSES = {
  up: dhStyles.dhUpRed,
  down: dhStyles.dhDownGreen,
  neutral: dhStyles.dhMuted,
} as const;

type MarketMacroToolkitSectionProps = {
  overviewPanel?: ModuleHomeDetailPanel;
  signalPanel?: ModuleHomeDetailPanel;
  capabilityPanel?: ModuleHomeDetailPanel;
  indicatorPanel?: ModuleHomeDetailPanel;
  strategyPanel?: ModuleHomeDetailPanel;
  aShareRiskPanel?: ModuleHomeDetailPanel;
  hasonPanel?: ModuleHomeDetailPanel;
  shadowPanel?: ModuleHomeDetailPanel;
  runtimePanel?: ModuleHomeDetailPanel;
  compact?: boolean;
  depthCompact?: boolean;
};

function toneClass(tone: ModuleHomeTone) {
  if (tone === "watch") return dhStyles.dhMuted;
  if (tone === "error") return dhStyles.dhUpRed;
  return "";
}

function hasRows(panel?: ModuleHomeDetailPanel) {
  return Boolean(panel && panel.rows.length > 0);
}

type MacroDetailPanelConfig = {
  panel: ModuleHomeDetailPanel;
  testId: string;
  compact?: boolean;
};

function MacroDetailSummary({ panel }: { panel: ModuleHomeDetailPanel }) {
  const primaryRow = panel.rows[0];
  const latestDate = panel.rows.find((row) => row.tradeDate && row.tradeDate !== "-")?.tradeDate;

  return (
    <article className={marketStyles.macroDetailSummaryCard}>
      <div className={marketStyles.macroDetailSummaryMain}>
        <span className={marketStyles.macroDetailSummaryTitle}>{panel.title}</span>
        <strong className={`${marketStyles.macroDetailSummaryValue} ${toneClass(primaryRow?.tone ?? panel.tone)}`}>
          {primaryRow?.value ?? panel.stateLabel}
        </strong>
        <span className={marketStyles.macroDetailSummaryMeta}>
          {panel.rows.length} 条明细{latestDate ? ` · ${latestDate}` : ""}
        </span>
      </div>
      <span className={marketStyles.statusChip}>{panel.stateLabel}</span>
    </article>
  );
}

function MacroGroupedDetails({ panels }: { panels: MacroDetailPanelConfig[] }) {
  return (
    <div className={marketStyles.macroDetailGroup}>
      <div className={marketStyles.macroSummaryGrid}>
        {panels.map(({ panel }) => (
          <MacroDetailSummary panel={panel} key={panel.key} />
        ))}
      </div>
      <Collapse
        className={marketStyles.macroDetailCollapse}
        destroyOnHidden
        ghost
        items={[
          {
            key: "details",
            label: "展开明细",
            children: (
              <div className={marketStyles.macroGroupedGrid}>
                {panels.map(({ panel, testId, compact }) => (
                  <MarketDepthPanel panel={panel} testId={testId} compact={compact} key={panel.key} />
                ))}
              </div>
            ),
          },
        ]}
      />
    </div>
  );
}

function MacroToolkitLink() {
  return (
    <Link to="/macro-toolkit" className={marketStyles.marketIbLink}>
      完整工具页 →
    </Link>
  );
}

export default function MarketMacroToolkitSection({
  overviewPanel,
  signalPanel,
  capabilityPanel,
  indicatorPanel,
  strategyPanel,
  aShareRiskPanel,
  hasonPanel,
  shadowPanel,
  runtimePanel,
  compact = false,
  depthCompact = false,
}: MarketMacroToolkitSectionProps) {
  const stanceRow = overviewPanel?.rows.find((row) => row.key === "macro-stance");
  const actionRow = overviewPanel?.rows.find((row) => row.key === "macro-action");
  const hitRateRow = overviewPanel?.rows.find((row) => row.key === "macro-hit-rate");
  const summaryRow = overviewPanel?.rows.find((row) => row.key === "macro-summary");
  const scriptsRow = overviewPanel?.rows.find((row) => row.key === "macro-scripts");
  const compactToolkitMeta = compact
    ? formatPanelMetaForHome(
        [overviewPanel?.meta, hitRateRow?.value, scriptsRow?.value, signalPanel ? `${signalPanel.rows.length} 张信号卡` : null, indicatorPanel ? `${indicatorPanel.rows.length} 项指标` : null]
          .map((part) => part?.trim())
          .filter((part): part is string => Boolean(part && part !== "-"))
          .join(" · "),
      )
    : undefined;
  const groupItems: NonNullable<TabsProps["items"]> = [];

  if (hasRows(aShareRiskPanel) && aShareRiskPanel) {
    groupItems.push({
      key: "core",
      label: "核心归因",
      children: <MacroGroupedDetails panels={[{ panel: aShareRiskPanel, testId: "module-home-macro-a-share-risk" }]} />,
    });
  }

  if (hasRows(capabilityPanel) || hasRows(indicatorPanel) || hasRows(strategyPanel)) {
    groupItems.push({
      key: "tooling",
      label: "工具明细",
      children: (
        <MacroGroupedDetails
          panels={[
            ...(hasRows(capabilityPanel) && capabilityPanel
              ? [{ panel: capabilityPanel, testId: "module-home-macro-capabilities", compact: true }]
              : []),
            ...(hasRows(indicatorPanel) && indicatorPanel
              ? [{ panel: indicatorPanel, testId: "module-home-macro-indicators" }]
              : []),
            ...(hasRows(strategyPanel) && strategyPanel
              ? [{ panel: strategyPanel, testId: "module-home-macro-strategies", compact: true }]
              : []),
          ]}
        />
      ),
    });
  }

  if (hasRows(hasonPanel) || hasRows(shadowPanel) || hasRows(runtimePanel)) {
    groupItems.push({
      key: "runtime",
      label: "组合运行",
      children: (
        <MacroGroupedDetails
          panels={[
            ...(hasRows(hasonPanel) && hasonPanel
              ? [{ panel: hasonPanel, testId: "module-home-macro-hason", compact: true }]
              : []),
            ...(hasRows(shadowPanel) && shadowPanel ? [{ panel: shadowPanel, testId: "module-home-macro-shadow" }] : []),
            ...(hasRows(runtimePanel) && runtimePanel
              ? [{ panel: runtimePanel, testId: "module-home-macro-runtime", compact: true }]
              : []),
          ]}
        />
      ),
    });
  }

  const defaultMacroGroupKey = groupItems[0]?.key;

  const toolkitBody = (
    <>
      {!compact ? (
        <article className={marketStyles.macroLead}>
          {stanceRow ? (
            <>
              <span className={marketStyles.macroLeadTitle}>工具结论 · 观察口径</span>
              <strong className={`${marketStyles.macroLeadValue} ${marketStyles.macroLeadValueSerif} ${toneClass(stanceRow.tone)}`}>
                {stanceRow.value}
              </strong>
              {summaryRow ? <p className={marketStyles.macroLeadSummary}>{summaryRow.value}</p> : null}
              {actionRow ? <p className={marketStyles.macroLeadAction}>{actionRow.value}</p> : null}
            </>
          ) : (
            <p className={marketStyles.macroLeadAction}>宏观工具分析待读取。</p>
          )}
          <div className={marketStyles.macroLeadMetaRow}>
            {hitRateRow ? <span className={marketStyles.macroLeadMeta}>{hitRateRow.value}</span> : null}
            {scriptsRow ? <span className={marketStyles.macroLeadMeta}>{scriptsRow.value}</span> : null}
          </div>
        </article>
      ) : (
        <article className={`${marketStyles.macroLeadCompact} ${depthCompact ? marketStyles.macroLeadDepthCompact : ""}`}>
          {hitRateRow ? <span className={marketStyles.macroSignalHitKicker}>{hitRateRow.value}</span> : null}
          <span className={marketStyles.macroLeadTitle}>工具立场</span>
          <strong
            className={`${marketStyles.macroLeadValue} ${marketStyles.macroLeadValueSerif} ${toneClass(stanceRow?.tone ?? overviewPanel?.tone ?? "muted")}`}
          >
            {stanceRow?.value ?? overviewPanel?.stateLabel ?? "待返回"}
          </strong>
          {!depthCompact && summaryRow ? <p className={marketStyles.macroLeadSummary}>{summaryRow.value}</p> : null}
          {actionRow ? <p className={marketStyles.macroLeadAction}>{actionRow.value}</p> : null}
        </article>
      )}

      {signalPanel && signalPanel.rows.length > 0 ? (
        <div
          className={`${marketStyles.macroSignalScrollBlock} ${depthCompact ? marketStyles.macroSignalScrollBlockDepth : ""}`}
          data-testid="module-home-macro-signals-scroll"
        >
          <div
            aria-label="宏观信号卡片"
            className={`${marketStyles.macroSignalGrid} ${depthCompact ? marketStyles.macroSignalGridDepth : ""}`}
            data-testid="module-home-macro-signals"
            role="region"
            tabIndex={0}
          >
            {signalPanel.rows.map((row) => {
              const change = marketChangePresentation(row.detail, row.sparkline, MARKET_CHANGE_CLASSES);
              const visual = marketSignalVisual(row.key);
              const Icon = visual.icon;
              const parsed = parseMacroSignalValue(row.value);

              return (
                <article
                  className={`${marketStyles.macroSignalCard} ${depthCompact ? marketStyles.macroSignalCardDepth : ""} ${marketStyles[`marketAccent_${visual.accent}`]}`}
                  data-testid={`module-home-macro-signal-${row.key}`}
                  key={row.key}
                >
                  <header className={marketStyles.macroSignalCardHead}>
                    <span className={marketStyles.marketIconBoxCompact}>
                      <Icon className={marketStyles.marketIconGlyph} size={14} />
                    </span>
                    <div className={marketStyles.macroSignalCardCopy}>
                      <span className={marketStyles.macroSignalKicker}>{visual.kicker}</span>
                      <span className={marketStyles.macroSignalTitle}>{row.label}</span>
                    </div>
                  </header>
                  <strong className={`${marketStyles.macroSignalStance} ${toneClass(row.tone)}`}>{parsed.stance}</strong>
                  {parsed.score ? (
                    <span className={`${dhStyles.dhNum} ${marketStyles.macroSignalScore}`}>{parsed.score}</span>
                  ) : null}
                  {row.detail ? (
                    <em
                      className={`${marketStyles.macroSignalChange} ${depthCompact ? marketStyles.macroSignalChangeDepth : ""} ${dhStyles.dhNum} ${change.className}`}
                      data-change={change.direction ?? "flat"}
                    >
                      {row.detail}
                    </em>
                  ) : null}
                  {row.source && row.source !== "macro-toolkit" ? (
                    <span className={`${marketStyles.macroSignalEvidence} ${depthCompact ? marketStyles.macroSignalEvidenceDepth : ""}`}>
                      {formatMacroSignalEvidence(row.source)}
                    </span>
                  ) : null}
                </article>
              );
            })}
          </div>
        </div>
      ) : null}

      {!compact && defaultMacroGroupKey ? (
        <Tabs
          className={marketStyles.macroGroupTabs}
          data-testid="module-home-macro-groups"
          defaultActiveKey={defaultMacroGroupKey}
          items={groupItems}
        />
      ) : null}
    </>
  );

  if (compact) {
    return (
      <MarketMacroPanelShell
        accent="gold"
        className={`${marketStyles.macroSectionCompactShell} ${depthCompact ? marketStyles.macroSectionDepthCompact : ""}`}
        hideMetaDate
        icon={MarketIconMacroToolkit}
        kicker="MACRO"
        meta={compactToolkitMeta || overviewPanel?.meta || signalPanel?.meta}
        testId="module-home-macro-toolkit"
        title="宏观工具"
      >
        <div className={marketStyles.macroSectionCompactHead}>
          <MacroToolkitLink />
        </div>
        {toolkitBody}
      </MarketMacroPanelShell>
    );
  }

  return (
    <section className={marketStyles.macroSection} data-testid="module-home-macro-toolkit">
      <div className={marketStyles.macroSectionHead}>
        <span className={marketStyles.macroSectionHeadTitle}>宏观工具</span>
        <MacroToolkitLink />
      </div>
      {toolkitBody}
    </section>
  );
}
