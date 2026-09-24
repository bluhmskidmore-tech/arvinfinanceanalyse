import { Link } from "react-router-dom";
import { useMemo } from "react";

import dhStyles from "../dashboard-home/dashboardHome.module.css";
import { MarketHomeKpiSparkline } from "./MarketHomeKpiSparkline";
import {
  crossAssetRowVisual,
  filterCrossAssetSecondaryRows,
  type CrossAssetTraderBucket,
} from "./marketEvidenceVisual";
import { marketChangePresentation } from "./marketHomeChangeTone";
import type { MarketChangeDirection } from "./marketHomeChangeTone";
import { ModuleHomeSectionHead } from "./ModuleHomeSectionHead";
import type {
  MarketCrisisExplainView,
  MarketDeskIntelView,
  ModuleHomeDetailRow,
  ModuleHomeTone,
} from "./moduleHomeModel";
import marketStyles from "./marketHome.module.css";

import { EM_DASH } from "../../../utils/format";
const MARKET_CHANGE_CLASSES = {
  up: dhStyles.dhUpGreen,
  down: dhStyles.dhDownRed,
  neutral: dhStyles.dhMuted,
} as const;

type MarketCrossAssetGapBlockProps = {
  allRows: readonly ModuleHomeDetailRow[];
  primaryKeys: ReadonlySet<string>;
  presentBuckets: ReadonlySet<CrossAssetTraderBucket>;
  crisisExplain?: MarketCrisisExplainView | null;
  liquidityRow?: ModuleHomeDetailRow | null;
  deskIntel?: MarketDeskIntelView | null;
};

function toneClass(tone: ModuleHomeTone) {
  if (tone === "watch") return dhStyles.dhMuted;
  // error 是警示语义（非方向），保持红色链。
  if (tone === "error") return dhStyles.dhDownRed;
  return "";
}

function trendChangeDirection(values: readonly number[]): MarketChangeDirection | undefined {
  if (values.length < 2) {
    return undefined;
  }
  const first = values[0];
  const last = values[values.length - 1];
  if (first === undefined || last === undefined) {
    return undefined;
  }
  if (last > first) {
    return "up";
  }
  if (last < first) {
    return "down";
  }
  return "flat";
}

function CrisisMiniTrend({ explain }: { explain: MarketCrisisExplainView }) {
  const scoreValues = explain.scoreHistory
    .map((point) => point.crisisScore)
    .filter((value): value is number => value !== null && Number.isFinite(value));
  const percentileHistory = explain.scoreHistory.filter((point) => point.percentile !== null);
  const percentileValues = percentileHistory
    .map((point) => point.percentile)
    .filter((value): value is number => value !== null && Number.isFinite(value));

  const scoreLabel =
    explain.crisisScore !== null
      ? explain.crisisScore.toFixed(2)
      : (scoreValues[scoreValues.length - 1]?.toFixed(2) ?? EM_DASH);
  const regimeLabel = explain.regime ?? EM_DASH;

  return (
    <section className={marketStyles.crossAssetGapSection} data-testid="module-home-cross-asset-crisis-mini">
      <ModuleHomeSectionHead
        label="CRISIS 趋势"
        title=""
        className={marketStyles.crossAssetGapSectionHead}
        trailing={
          <Link to="/macro-toolkit" className={marketStyles.marketIbLink}>
            宏观工具 →
          </Link>
        }
      />
      <div className={marketStyles.crossAssetCrisisMini}>
        <div className={marketStyles.crossAssetCrisisMiniStats}>
          <strong className={`${dhStyles.dhNum} ${marketStyles.crossAssetCrisisMiniScore}`}>{scoreLabel}</strong>
          <em className={marketStyles.crossAssetCrisisMiniRegime}>{regimeLabel}</em>
        </div>
        {scoreValues.length >= 2 || percentileValues.length >= 2 ? (
          <div className={marketStyles.crossAssetCrisisMiniSparkGrid}>
            {scoreValues.length >= 2 ? (
              <MarketHomeKpiSparkline
                changeDirection={trendChangeDirection(scoreValues)}
                className={marketStyles.crossAssetCrisisMiniSparkline}
                tone={explain.tone}
                values={scoreValues}
                variant="ticker"
              />
            ) : null}
            {percentileValues.length >= 2 ? (
              <MarketHomeKpiSparkline
                changeDirection={trendChangeDirection(percentileValues)}
                className={marketStyles.crossAssetCrisisMiniSparkline}
                tone={explain.tone}
                values={percentileValues}
                variant="ticker"
              />
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}

function DeskContextStrip({
  presentBuckets,
  liquidityRow,
  curveShapeLabel,
}: {
  presentBuckets: ReadonlySet<CrossAssetTraderBucket>;
  liquidityRow?: ModuleHomeDetailRow | null;
  curveShapeLabel?: string | null;
}) {
  const missingRates = !presentBuckets.has("rates");
  const missingFx = !presentBuckets.has("fx");
  const hasCurve = Boolean(curveShapeLabel?.trim());

  if (!missingRates && !missingFx && !hasCurve) {
    return null;
  }

  return (
    <section className={marketStyles.crossAssetDeskContext} data-testid="module-home-cross-asset-desk-context">
      <ModuleHomeSectionHead
        label="Desk 上下文"
        title=""
        className={marketStyles.crossAssetGapSectionHead}
      />
      <div className={marketStyles.crossAssetDeskContextGrid}>
        {missingRates ? (
          <div className={marketStyles.crossAssetDeskContextCell} data-testid="module-home-cross-asset-missing-rates">
            <span className={marketStyles.crossAssetDeskContextLabel}>RATES</span>
            <strong className={`${dhStyles.dhNum} ${marketStyles.crossAssetDeskContextValue}`}>
              {liquidityRow ? `${liquidityRow.value}` : "待观察"}
            </strong>
            {liquidityRow ? (
              <em className={marketStyles.crossAssetDeskContextDetail}>{liquidityRow.label}</em>
            ) : (
              <em className={marketStyles.crossAssetDeskContextDetail}>待接入</em>
            )}
          </div>
        ) : null}
        {missingFx ? (
          <div className={marketStyles.crossAssetDeskContextCell} data-testid="module-home-cross-asset-missing-fx">
            <span className={marketStyles.crossAssetDeskContextLabel}>FX</span>
            <strong className={marketStyles.crossAssetDeskContextValue}>待观察</strong>
            <em className={marketStyles.crossAssetDeskContextDetail}>待接入</em>
          </div>
        ) : null}
        {hasCurve ? (
          <div className={marketStyles.crossAssetDeskContextCell} data-testid="module-home-cross-asset-desk-hint">
            <span className={marketStyles.crossAssetDeskContextLabel}>曲线</span>
            <strong className={marketStyles.crossAssetDeskContextValue}>{curveShapeLabel}</strong>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function SecondaryRow({ row }: { row: ModuleHomeDetailRow }) {
  const change = marketChangePresentation(row.detail, row.sparkline, MARKET_CHANGE_CLASSES);
  const visual = crossAssetRowVisual(row);
  const Icon = visual.icon;

  return (
    <div
      className={`${marketStyles.crossAssetBarRow} ${marketStyles.crossAssetBarRowCompact} ${marketStyles.crossAssetSecondaryRow}`}
      data-testid={`module-home-cross-asset-secondary-${row.key}`}
    >
      <span className={marketStyles.crossAssetBarIconBox}>
        <Icon className={marketStyles.crossAssetBarIconGlyph} size={12} />
      </span>
      <span className={marketStyles.crossAssetBarLabel} title={row.label}>
        {row.label}
      </span>
      <div className={marketStyles.crossAssetBarValueCol}>
        <strong className={`${dhStyles.dhNum} ${marketStyles.crossAssetBarValue} ${toneClass(row.tone)}`}>
          {row.value}
        </strong>
        {row.detail ? (
          <em className={`${dhStyles.dhNum} ${marketStyles.crossAssetBarChange} ${change.className}`}>
            {row.detail}
          </em>
        ) : null}
      </div>
    </div>
  );
}

export function MarketCrossAssetGapBlock({
  allRows,
  primaryKeys,
  presentBuckets,
  crisisExplain,
  liquidityRow,
  deskIntel,
}: MarketCrossAssetGapBlockProps) {
  const secondaryRows = useMemo(
    () => filterCrossAssetSecondaryRows(allRows, primaryKeys, { maxRows: 4 }),
    [allRows, primaryKeys],
  );

  const showCrisisMini = (crisisExplain?.scoreHistory.length ?? 0) > 1;
  const showDeskContext =
    !presentBuckets.has("rates") ||
    !presentBuckets.has("fx") ||
    Boolean(deskIntel?.curveShapeLabel?.trim());
  const showSecondary = secondaryRows.length > 0;
  const curveShapeLabel = deskIntel?.curveShapeLabel ?? null;

  if (!showCrisisMini && !showDeskContext && !showSecondary) {
    return null;
  }

  return (
    <div className={marketStyles.crossAssetGapBlock} data-testid="module-home-cross-asset-gap-block">
      {showDeskContext ? (
        <DeskContextStrip
          curveShapeLabel={curveShapeLabel}
          liquidityRow={liquidityRow}
          presentBuckets={presentBuckets}
        />
      ) : null}
      {showSecondary ? (
        <section className={marketStyles.crossAssetGapSection} data-testid="module-home-cross-asset-secondary-list">
          <ModuleHomeSectionHead
            label="更多观察"
            title=""
            className={marketStyles.crossAssetGapSectionHead}
            trailing={<em className={marketStyles.crossAssetGapSectionMeta}>{secondaryRows.length} 条</em>}
          />
          <div className={marketStyles.crossAssetSecondaryList}>
            {secondaryRows.map((row) => (
              <SecondaryRow key={row.key} row={row} />
            ))}
          </div>
        </section>
      ) : null}
      {showCrisisMini && crisisExplain ? <CrisisMiniTrend explain={crisisExplain} /> : null}
    </div>
  );
}
