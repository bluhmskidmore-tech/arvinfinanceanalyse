import dhStyles from "../dashboard-home/dashboardHome.module.css";
import { EM_DASH } from "../../../utils/format";
import type { ModuleHomeDetailPanel } from "./moduleHomeModel";
import marketStyles from "./marketHome.module.css";

type MarketPanelSummaryProps = {
  panel: ModuleHomeDetailPanel;
};

function latestTradeDate(panel: ModuleHomeDetailPanel) {
  return panel.rows
    .map((row) => row.tradeDate)
    .filter((date) => date && /^\d{4}-\d{2}-\d{2}$/.test(date))
    .sort()
    .at(-1);
}

function sourceCount(panel: ModuleHomeDetailPanel) {
  return new Set(panel.rows.map((row) => row.source).filter((source) => source && source !== EM_DASH)).size;
}

export function MarketPanelSummary({ panel }: MarketPanelSummaryProps) {
  const chartCount = panel.chart?.categories.length ?? 0;

  if (panel.rows.length === 0 && chartCount === 0) {
    return null;
  }

  const items = [
    { label: "样本", value: `${panel.rows.length} 条` },
    { label: "最新", value: latestTradeDate(panel) ?? EM_DASH },
    { label: "来源", value: `${sourceCount(panel)} 源` },
    ...(chartCount > 0 ? [{ label: "图表", value: `${chartCount} 项` }] : []),
  ];

  return (
    <div className={marketStyles.panelSummaryStrip} data-testid="module-home-panel-summary">
      {items.map((item) => (
        <span key={item.label}>
          <b>{item.label}</b>
          <strong className={dhStyles.dhNum}>{item.value}</strong>
        </span>
      ))}
    </div>
  );
}
