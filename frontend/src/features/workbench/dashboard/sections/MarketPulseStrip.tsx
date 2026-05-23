import { Link } from "react-router-dom";

import { tabularNumsStyle } from "../../../../theme/designSystem";
import type { DashboardMarketPulseVM } from "../dashboardCockpitHomeModel";
import { resolveKpiDeltaClass } from "../dashboardCockpitHomeModel";

type MarketPulseStripProps = {
  items: readonly DashboardMarketPulseVM[];
  maxItems?: number;
};

export function MarketPulseStrip({ items, maxItems = 6 }: MarketPulseStripProps) {
  const visible = items.slice(0, maxItems);

  return (
    <section
      data-testid="dashboard-cockpit-market-ticker"
      className="dashboard-cockpit-market-strip"
      aria-label="宏观上下文"
    >
      <div className="dashboard-cockpit-market-strip__items">
        {visible.map((item) => (
          <span
            key={item.id}
            data-testid={`dashboard-market-pulse-${item.id}`}
            className="dashboard-cockpit-market-strip__item"
          >
            <em>
          {item.label}
          {item.isEstimated ? (
            <span className="dashboard-cockpit-market-strip__estimate" aria-label="估算值">
              估算
            </span>
          ) : null}
        </em>
            <strong style={tabularNumsStyle}>{item.value}</strong>
            <span className={resolveKpiDeltaClass(item.deltaTone)} style={tabularNumsStyle}>
              {item.delta}
            </span>
          </span>
        ))}
      </div>
      <Link to="/market-data" className="dashboard-cockpit-market-strip__more">
        市场数据 →
      </Link>
    </section>
  );
}
