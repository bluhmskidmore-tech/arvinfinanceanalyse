import { Link } from "react-router-dom";

import { tabularNumsStyle } from "../../../theme/designSystem";
import type { MarketOverviewMetric } from "../pages/MarketDataHeroSection";
import { MARKET_DATA_WORKBENCH_LINKS, marketDataPageHref } from "./marketDataDeskBridgeLinks";

type MarketDataDeskBridgeBandProps = {
  bridgeMetrics: readonly MarketOverviewMetric[];
  basisChipLabel: string;
  emptyReason?: string;
  watchDate: string;
};

const MARKET_DATA_PAGE_CHART_LINKS = [
  { testId: "market-data-bridge-chart-curve", label: "曲线", hash: "market-data-term-structure" },
  { testId: "market-data-bridge-chart-ncd", label: "存单", hash: "market-data-liquidity-deck" },
  {
    testId: "market-data-bridge-chart-linkage",
    label: "联动",
    hash: "market-data-linkage-correlation",
  },
] as const;

export function MarketDataDeskBridgeBand({
  bridgeMetrics,
  basisChipLabel,
  emptyReason,
  watchDate,
}: MarketDataDeskBridgeBandProps) {
  return (
    <section className="market-data-desk-bridge-band" data-testid="market-data-desk-bridge-band">
      <div className="market-data-desk-bridge-links" data-testid="market-data-desk-bridge-links">
        {MARKET_DATA_WORKBENCH_LINKS.map((item) => (
          <Link
            key={item.testId}
            className="market-data-desk-bridge-link"
            data-testid={item.testId}
            to={item.to}
          >
            {item.label}
          </Link>
        ))}
        <Link
          className="market-data-desk-bridge-link market-data-desk-bridge-link--muted"
          data-testid="market-data-bridge-link-self"
          to={marketDataPageHref("/market-data", watchDate)}
        >
          本页终端
        </Link>
      </div>

      <div className="market-data-desk-bridge-body">
        {bridgeMetrics.length > 0 ? (
          <div className="market-data-desk-bridge-metrics" data-testid="market-data-desk-bridge-metrics">
            {bridgeMetrics.map((metric) => (
              <article
                key={metric.testId}
                className={`market-data-desk-bridge-metric market-data-desk-bridge-metric--${metric.tone ?? "default"}`}
                data-testid={metric.testId}
              >
                <span className="market-data-desk-bridge-metric-label">{metric.title}</span>
                <strong className="market-data-desk-bridge-metric-value" style={tabularNumsStyle}>
                  {metric.value}
                </strong>
                <em className="market-data-desk-bridge-metric-detail">{metric.detail.split(" · ")[0]}</em>
              </article>
            ))}
          </div>
        ) : (
          <p className="market-data-desk-bridge-empty" data-testid="market-data-desk-bridge-empty">
            {emptyReason ?? "共享读数暂无，请在下方的利率主表核对。"}
          </p>
        )}

        <div className="market-data-desk-bridge-chip-row">
          <span className="market-data-desk-bridge-chip" data-testid="market-data-desk-bridge-basis-chip">
            {basisChipLabel}
          </span>
        </div>

        <div className="market-data-desk-bridge-chart-links" data-testid="market-data-desk-bridge-chart-links">
          <span className="market-data-desk-bridge-chart-links-label">本页图表</span>
          {MARKET_DATA_PAGE_CHART_LINKS.map((item) => (
            <Link
              key={item.testId}
              className="market-data-desk-bridge-chart-link"
              data-testid={item.testId}
              to={`${marketDataPageHref("/market-data", watchDate)}#${item.hash}`}
            >
              {item.label}
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
