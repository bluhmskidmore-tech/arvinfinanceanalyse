import { Link } from "react-router-dom";

import dhStyles from "../dashboard-home/dashboardHome.module.css";
import { marketChangePresentation } from "./marketHomeChangeTone";
import type { ModuleHomeDetailPanel, ModuleHomeTone } from "./moduleHomeModel";

const MARKET_CHANGE_CLASSES = {
  up: dhStyles.dhUpRed,
  down: dhStyles.dhDownGreen,
  neutral: dhStyles.dhMuted,
} as const;
import { MarketPanelSummary } from "./MarketPanelSummary";
import marketStyles from "./marketHome.module.css";

function toneClass(tone: ModuleHomeTone) {
  if (tone === "watch") return dhStyles.dhMuted;
  if (tone === "error") return dhStyles.dhUpRed;
  return "";
}

type MarketRateLadderProps = {
  panel: ModuleHomeDetailPanel;
  viewAllPath?: string;
};

export function MarketRateLadder({ panel, viewAllPath = "/market-data" }: MarketRateLadderProps) {
  const rows = panel.rows;
  const isEmpty = rows.length === 0;

  return (
    <section
      data-testid="module-home-rate-snapshot"
      className={`${dhStyles.dhCard} ${marketStyles.ratePanel} ${isEmpty ? marketStyles.marketCompactEmptyPanel : ""}`}
    >
      <div className={dhStyles.dhSectionTitle}>
        <span>关键利率快照</span>
        {viewAllPath ? (
          <Link to={viewAllPath} className={dhStyles.dhLink}>
            市场数据 →
          </Link>
        ) : null}
      </div>
      <p className={marketStyles.panelMeta}>{panel.meta}</p>
      <MarketPanelSummary panel={panel} />
      {rows.length > 0 ? (
        <div className={`${marketStyles.rateTable} ${marketStyles.rateTableScroll}`}>
          <div className={marketStyles.rateTableHead} aria-hidden="true">
            <span>品种</span>
            <span>最新</span>
            <span>变动</span>
            <span>日期</span>
          </div>
          {rows.map((row) => {
            const change = marketChangePresentation(row.detail, row.sparkline, MARKET_CHANGE_CLASSES);
            return (
            <div className={marketStyles.rateTableRow} data-testid={`module-home-rate-${row.key}`} key={row.key}>
              <span className={marketStyles.rateTableLabel}>{row.label}</span>
              <span className={`${marketStyles.rateTableValue} ${dhStyles.dhNum} ${toneClass(row.tone)}`}>
                {row.value}
              </span>
              <span
                className={`${marketStyles.rateTableChange} ${dhStyles.dhNum} ${change.className}`}
                data-change={change.direction ?? "flat"}
              >
                {row.detail ?? "—"}
              </span>
              <span className={`${marketStyles.rateTableDate} ${dhStyles.dhNum}`}>{row.tradeDate}</span>
            </div>
            );
          })}
        </div>
      ) : (
        <p className={marketStyles.panelEmpty}>{panel.stateDetail || "未匹配到关键利率点。"}</p>
      )}
    </section>
  );
}
