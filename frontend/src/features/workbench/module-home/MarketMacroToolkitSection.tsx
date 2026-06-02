import { Link } from "react-router-dom";

import dhStyles from "../dashboard-home/dashboardHome.module.css";
import type { ModuleHomeDetailPanel, ModuleHomeTone } from "./moduleHomeModel";
import { MarketDepthPanel } from "./MarketDepthPanel";
import marketStyles from "./marketHome.module.css";

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
};

function toneClass(tone: ModuleHomeTone) {
  if (tone === "watch") return dhStyles.dhMuted;
  if (tone === "error") return dhStyles.dhUpRed;
  return "";
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
}: MarketMacroToolkitSectionProps) {
  const stanceRow = overviewPanel?.rows.find((row) => row.key === "macro-stance");
  const actionRow = overviewPanel?.rows.find((row) => row.key === "macro-action");
  const hitRateRow = overviewPanel?.rows.find((row) => row.key === "macro-hit-rate");
  const summaryRow = overviewPanel?.rows.find((row) => row.key === "macro-summary");
  const scriptsRow = overviewPanel?.rows.find((row) => row.key === "macro-scripts");

  return (
    <section className={marketStyles.macroSection} data-testid="module-home-macro-toolkit">
      <div className={dhStyles.dhSectionTitle}>
        <span>宏观工具</span>
        <Link to="/macro-toolkit" className={dhStyles.dhLink}>
          完整工具页 →
        </Link>
      </div>

      <article className={marketStyles.macroLead}>
        {stanceRow ? (
          <>
            <span className={marketStyles.macroLeadTitle}>工具结论 · 观察口径</span>
            <strong className={`${marketStyles.macroLeadValue} ${toneClass(stanceRow.tone)}`}>
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

      {signalPanel && signalPanel.rows.length > 0 ? (
        <div className={marketStyles.macroSignalGrid} data-testid="module-home-macro-signals">
          {signalPanel.rows.map((row) => (
            <article className={marketStyles.macroSignalCard} key={row.key}>
              <span className={marketStyles.macroSignalTitle}>{row.label}</span>
              <strong className={`${marketStyles.macroSignalValue} ${toneClass(row.tone)}`}>{row.value}</strong>
              <span className={marketStyles.macroSignalEvidence}>{row.source}</span>
            </article>
          ))}
        </div>
      ) : null}

      <div className={marketStyles.macroFeaturedGrid}>
        {aShareRiskPanel && aShareRiskPanel.rows.length > 0 ? (
          <MarketDepthPanel panel={aShareRiskPanel} testId="module-home-macro-a-share-risk" />
        ) : null}
        {hasonPanel && hasonPanel.rows.length > 0 ? (
          <MarketDepthPanel panel={hasonPanel} testId="module-home-macro-hason" compact />
        ) : null}
      </div>

      <div className={marketStyles.macroDetailGrid}>
        {capabilityPanel && capabilityPanel.rows.length > 0 ? (
          <MarketDepthPanel panel={capabilityPanel} testId="module-home-macro-capabilities" compact />
        ) : null}
        {indicatorPanel && indicatorPanel.rows.length > 0 ? (
          <MarketDepthPanel panel={indicatorPanel} testId="module-home-macro-indicators" />
        ) : null}
        {strategyPanel && strategyPanel.rows.length > 0 ? (
          <MarketDepthPanel panel={strategyPanel} testId="module-home-macro-strategies" compact />
        ) : null}
      </div>

      <div className={marketStyles.macroSecondaryGrid}>
        {shadowPanel && shadowPanel.rows.length > 0 ? (
          <MarketDepthPanel panel={shadowPanel} testId="module-home-macro-shadow" />
        ) : null}
        {runtimePanel && runtimePanel.rows.length > 0 ? (
          <MarketDepthPanel panel={runtimePanel} testId="module-home-macro-runtime" compact />
        ) : null}
      </div>
    </section>
  );
}
