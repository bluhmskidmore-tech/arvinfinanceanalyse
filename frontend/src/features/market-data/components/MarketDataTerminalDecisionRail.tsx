import { Link } from "react-router-dom";

import { MarketTerminalSparkline } from "./MarketTerminalSparkline";
import type { MarketOverviewMetric } from "../pages/MarketDataHeroSection";
import { MARKET_DATA_WORKBENCH_LINKS } from "./marketDataDeskBridgeLinks";
import "../pages/MarketDataPage.css";

type SourceGateField = {
  label: string;
  value: string;
};

type MarketDataTerminalDecisionRailProps = {
  readinessVerdict: string;
  secondaryLabel: string;
  sourceGateFields: SourceGateField[];
  highlightMetric: MarketOverviewMetric | null;
};

export function MarketDataTerminalDecisionRail({
  readinessVerdict,
  secondaryLabel,
  sourceGateFields,
  highlightMetric,
}: MarketDataTerminalDecisionRailProps) {
  return (
    <aside className="market-data-terminal-decision-rail" data-testid="market-data-terminal-decision-rail">
      <div className="market-data-terminal-rail-head">
        <span>Market Data Terminal</span>
        <strong>{readinessVerdict}</strong>
        <small>{secondaryLabel}</small>
      </div>

      <nav className="market-data-terminal-workbench-nav" aria-label="工作台联动导航" data-testid="market-data-terminal-workbench-nav">
        <span className="market-data-terminal-rail-kicker">Workbench</span>
        <div className="market-data-terminal-workbench-links">
          {MARKET_DATA_WORKBENCH_LINKS.map((item) => (
            <Link key={item.testId} className="market-data-terminal-workbench-link" data-testid={`${item.testId}-rail`} to={item.to}>
              {item.label}
            </Link>
          ))}
        </div>
      </nav>

      <div className="market-data-terminal-source-gate">
        <span className="market-data-terminal-rail-kicker">Source Gate</span>
        {sourceGateFields.map((field) => (
          <div
            key={field.label}
            className={`market-data-terminal-source-row ${
              field.label === "Source" ? "market-data-terminal-source-row--source" : ""
            }`}
          >
            <span>{field.label}</span>
            <strong title={field.value}>{field.value}</strong>
          </div>
        ))}
      </div>

      {highlightMetric ? (
        <div className="market-data-terminal-rail-metrics">
          <div
            className={`market-data-terminal-rail-metric market-data-terminal-rail-metric--${highlightMetric.tone ?? "default"}`}
            data-testid="market-data-terminal-rail-highlight-metric"
          >
            <div className="market-data-terminal-rail-metric-head">
              <span>{highlightMetric.title}</span>
              {highlightMetric.sparklineValues && highlightMetric.sparklineValues.length >= 2 ? (
                <MarketTerminalSparkline
                  values={highlightMetric.sparklineValues}
                  tone={highlightMetric.sparklineTone}
                  variant="ticker"
                />
              ) : null}
            </div>
            <strong>{highlightMetric.value}</strong>
            <small>{highlightMetric.detail}</small>
          </div>
        </div>
      ) : null}

      <nav className="market-data-terminal-anchor-nav" aria-label="市场数据终端导航">
        <a href="#market-data-core-workbench">利率曲线</a>
        <a href="#market-data-liquidity-deck" aria-label="资金与 NCD">
          资金/NCD
        </a>
        <a href="#market-data-evidence-gate">证据口径</a>
      </nav>
    </aside>
  );
}
