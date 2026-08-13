import { Link } from "react-router-dom";

import dhStyles from "../dashboard-home/dashboardHome.module.css";
import { EM_DASH } from "../../../utils/format";
import { MARKET_KPI_ACCENT } from "./marketEvidenceVisual";
import { marketChangePresentation, resolveMarketChangeDirection } from "./marketHomeChangeTone";
import { MarketHomeKpiSparkline } from "./MarketHomeKpiSparkline";
import type { ModuleHomeDetailRow, ModuleHomeTone } from "./moduleHomeModel";
import marketStyles from "./marketHome.module.css";
import { marketDataPageHref } from "../../market-data/components/marketDataDeskBridgeLinks";

const MARKET_CHANGE_CLASSES = {
  up: dhStyles.dhUpRed,
  down: dhStyles.dhDownGreen,
  neutral: dhStyles.dhMuted,
} as const;

type MarketCurveSpreadBandProps = {
  termSpreadRows: ModuleHomeDetailRow[];
  creditSpreadRow?: ModuleHomeDetailRow;
  curveShapeLabel?: string | null;
  activeKeys?: readonly string[];
  onSpreadHover?: (key: string | null) => void;
};

function toneClass(tone: ModuleHomeTone) {
  if (tone === "watch") return dhStyles.dhMuted;
  if (tone === "error") return dhStyles.dhUpRed;
  return "";
}

function resolveWatchDate(rows: ModuleHomeDetailRow[]): string | undefined {
  const dated = rows.find((row) => row.tradeDate && row.tradeDate !== EM_DASH);
  return dated?.tradeDate;
}

function SpreadMiniCard({
  row,
  linked,
  onHover,
  href,
}: {
  row: ModuleHomeDetailRow;
  linked: boolean;
  onHover?: (key: string | null) => void;
  href?: string;
}) {
  const accent = MARKET_KPI_ACCENT[row.key];
  const changeDirection = resolveMarketChangeDirection(row.detail, row.sparkline);
  const change = marketChangePresentation(row.detail, row.sparkline, MARKET_CHANGE_CLASSES);

  const card = (
    <article
      className={`${dhStyles.dhCard} ${marketStyles.marketCurveSpreadCard} ${marketStyles.marketDeskPanel} ${accent ? marketStyles[`marketAccent_${accent}`] : marketStyles.marketAccent_slate} ${linked ? marketStyles.marketCurveSpreadCardLinked : ""}`}
      data-testid={`module-home-market-curve-spread-${row.key}`}
      data-tone={row.tone}
      data-linked-active={linked ? "true" : "false"}
      data-spread-key={row.key}
      onMouseEnter={() => onHover?.(row.key)}
      onMouseLeave={() => onHover?.(null)}
    >
      <span className={marketStyles.marketCurveSpreadLabel}>{row.label}</span>
      <div className={marketStyles.marketCurveSpreadValueRow}>
        <strong className={`${dhStyles.dhNum} ${marketStyles.marketMetricNum} ${toneClass(row.tone)}`}>{row.value}</strong>
        {row.sparkline && row.sparkline.length >= 2 ? (
          <MarketHomeKpiSparkline values={row.sparkline} tone={row.tone} changeDirection={changeDirection} />
        ) : null}
      </div>
      {row.detail ? (
        <em
          className={`${marketStyles.marketCurveSpreadDetail} ${change.className}`}
          data-change={change.direction ?? "flat"}
        >
          {row.detail}
        </em>
      ) : null}
    </article>
  );

  if (!href) {
    return card;
  }

  return (
    <Link to={href} className={marketStyles.marketCurveSpreadCardLink}>
      {card}
    </Link>
  );
}

export function MarketCurveSpreadBand({
  termSpreadRows,
  creditSpreadRow,
  curveShapeLabel,
  activeKeys = [],
  onSpreadHover,
}: MarketCurveSpreadBandProps) {
  const rows = creditSpreadRow ? [...termSpreadRows, creditSpreadRow] : termSpreadRows;
  if (rows.length === 0) {
    return null;
  }

  const activeKeySet = new Set(activeKeys);
  const watchDate = resolveWatchDate(rows);
  const marketDataBase = marketDataPageHref("/market-data", watchDate);

  return (
    <section
      className={`${dhStyles.dhCard} ${marketStyles.marketCurveSpreadBand} ${marketStyles.marketDeskPanel}`}
      data-testid="module-home-market-curve-spread-band"
    >
      <header className={marketStyles.marketCurveSpreadBandHead}>
        <div>
          <span className={marketStyles.marketSummaryKicker}>CURVE</span>
          <h3 className={marketStyles.marketCurveSpreadBandTitle}>曲线形态 · 期限与信用利差</h3>
          {curveShapeLabel ? (
            <p className={marketStyles.marketCrisisExplainMeta} data-testid="module-home-market-curve-shape-label">
              后端形态：{curveShapeLabel}
            </p>
          ) : null}
        </div>
        <Link to={`${marketDataBase}#market-data-term-structure`} className={marketStyles.marketIbLink}>
          终端曲线 →
        </Link>
      </header>
      <div className={marketStyles.marketCurveSpreadGrid}>
        {rows.map((row) => {
          const isCredit = row.key === creditSpreadRow?.key;
          const href = isCredit
            ? `${marketDataBase}#market-data-linkage-correlation`
            : `${marketDataBase}#market-data-term-structure`;
          return (
            <SpreadMiniCard
              key={row.key}
              href={href}
              linked={activeKeySet.has(row.key)}
              onHover={onSpreadHover}
              row={row}
            />
          );
        })}
      </div>
    </section>
  );
}
