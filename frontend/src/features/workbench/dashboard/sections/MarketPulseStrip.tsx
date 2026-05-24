import { Link } from "react-router-dom";

import type { DashboardMarketPulseVM } from "../dashboardCockpitHomeModel";
import { MarketPulseCard } from "./MarketPulseCard";

type MarketPulseStripProps = {
  items: readonly DashboardMarketPulseVM[];
  maxItems?: number;
};

export function MarketPulseStrip({ items, maxItems = 8 }: MarketPulseStripProps) {
  const visible = items.slice(0, maxItems);

  return (
    <section
      data-testid="dashboard-cockpit-market-ticker"
      id="dashboard-home-market-section"
      className="dashboard-cockpit-market-strip dashboard-terminal-market-tape-shell"
      aria-label="市场行情磁带"
    >
      <div
        data-testid="dashboard-market-tape"
        className="dashboard-cockpit-market-strip__items dashboard-terminal-market-tape"
      >
        {visible.map((item) => (
          <MarketPulseCard key={item.id} item={item} />
        ))}
        <Link to="/market-data" className="dashboard-cockpit-market-strip__more dashboard-terminal-market-tape__more">
          更多市场数据 →
        </Link>
      </div>
    </section>
  );
}
