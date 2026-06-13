import { Link } from "react-router-dom";
import { useMemo } from "react";

import dhStyles from "../dashboard-home/dashboardHome.module.css";
import {
  crossAssetBucket,
  crossAssetBucketLabel,
  crossAssetRowVisual,
  crossAssetTraderBucket,
  filterCrossAssetRowsForTrader,
  traderCrossAssetBucketOrder,
  type CrossAssetBucket,
  type CrossAssetTraderBucket,
} from "./marketEvidenceVisual";
import { MarketCrossAssetGapBlock } from "./MarketCrossAssetGapBlock";
import { marketChangePresentation } from "./marketHomeChangeTone";
import { MarketIconCrossAsset } from "./marketHomeIcons";
import { MarketMacroPanelShell } from "./MarketMacroPanelShell";
import type {
  MarketCrisisExplainView,
  MarketDeskIntelView,
  ModuleHomeDetailPanel,
  ModuleHomeDetailRow,
  ModuleHomeTone,
} from "./moduleHomeModel";
import marketStyles from "./marketHome.module.css";

const MARKET_CHANGE_CLASSES = {
  up: dhStyles.dhUpRed,
  down: dhStyles.dhDownGreen,
  neutral: dhStyles.dhMuted,
} as const;

const BUCKET_ORDER: CrossAssetBucket[] = ["equity", "fx", "commod", "other"];

function resolveBucketLabel(bucket: CrossAssetTraderBucket): string {
  if (bucket === "rates") {
    return "RATES";
  }
  return crossAssetBucketLabel(bucket);
}

function toneClass(tone: ModuleHomeTone) {
  if (tone === "watch") return dhStyles.dhMuted;
  if (tone === "error") return dhStyles.dhUpRed;
  return "";
}

function barWidth(sparkline: readonly number[] | undefined): number {
  if (!sparkline || sparkline.length === 0) {
    return 36;
  }
  const values = sparkline.filter((value) => Number.isFinite(value));
  if (values.length === 0) {
    return 36;
  }
  const max = Math.max(...values.map((value) => Math.abs(value)), 1);
  const last = Math.abs(values[values.length - 1] ?? 0);
  return Math.max(12, Math.round((last / max) * 100));
}

type MarketCrossAssetBarsProps = {
  panel: ModuleHomeDetailPanel;
  testId: string;
  traderMode?: boolean;
  depthCompact?: boolean;
  crisisExplain?: MarketCrisisExplainView | null;
  liquidityRow?: ModuleHomeDetailRow | null;
  deskIntel?: MarketDeskIntelView | null;
};

function CrossAssetBarRow({ row, depthCompact }: { row: ModuleHomeDetailRow; depthCompact?: boolean }) {
  const change = marketChangePresentation(row.detail, row.sparkline, MARKET_CHANGE_CLASSES);
  const visual = crossAssetRowVisual(row);
  const Icon = visual.icon;

  return (
    <div
      className={`${marketStyles.crossAssetBarRow} ${depthCompact ? marketStyles.crossAssetBarRowCompact : ""}`}
      data-testid={`module-home-depth-${row.key}`}
      data-tone={row.tone}
    >
      <span className={marketStyles.crossAssetBarIconBox}>
        <Icon className={marketStyles.crossAssetBarIconGlyph} size={14} />
      </span>
      <span className={marketStyles.crossAssetBarLabel} title={row.label}>
        {row.label}
      </span>
      {depthCompact ? null : (
        <div className={marketStyles.crossAssetBarTrack} aria-hidden="true">
          <span
            className={`${marketStyles.crossAssetBarFill} ${marketStyles[`crossAssetBarFill_${visual.accent}`]}`}
            style={{ width: `${barWidth(row.sparkline)}%` }}
          />
        </div>
      )}
      <div className={marketStyles.crossAssetBarValueCol}>
        <strong className={`${dhStyles.dhNum} ${marketStyles.crossAssetBarValue} ${toneClass(row.tone)}`}>
          {row.value}
        </strong>
        {row.detail ? (
          <em
            className={`${dhStyles.dhNum} ${marketStyles.crossAssetBarChange} ${change.className}`}
            data-change={change.direction ?? "flat"}
          >
            {row.detail}
          </em>
        ) : null}
      </div>
    </div>
  );
}

export function MarketCrossAssetBars({
  panel,
  testId,
  traderMode = true,
  depthCompact = false,
  crisisExplain,
  liquidityRow,
  deskIntel,
}: MarketCrossAssetBarsProps) {
  const isEmpty = panel.rows.length === 0;

  const groupedRows = useMemo(() => {
    const visibleRows = filterCrossAssetRowsForTrader(panel.rows, { traderMode });
    const bucketOrder = traderMode ? traderCrossAssetBucketOrder() : BUCKET_ORDER;
    const groups = new Map<CrossAssetTraderBucket, ModuleHomeDetailRow[]>();
    for (const row of visibleRows) {
      const bucket = traderMode ? crossAssetTraderBucket(row) : crossAssetBucket(row);
      const existing = groups.get(bucket) ?? [];
      existing.push(row);
      groups.set(bucket, existing);
    }
    return bucketOrder.filter((bucket) => groups.has(bucket)).map((bucket) => ({
      bucket,
      rows: groups.get(bucket) ?? [],
    }));
  }, [panel.rows, traderMode]);

  const visibleCount = groupedRows.reduce((total, group) => total + group.rows.length, 0);

  const primaryKeys = useMemo(
    () => new Set(groupedRows.flatMap((group) => group.rows.map((row) => row.key))),
    [groupedRows],
  );

  const presentBuckets = useMemo(
    () => new Set(groupedRows.map((group) => group.bucket)),
    [groupedRows],
  );

  return (
    <MarketMacroPanelShell
      accent="navy"
      className={`${isEmpty ? marketStyles.marketCompactEmptyPanel : ""} ${marketStyles.crossAssetPanelShell} ${depthCompact ? marketStyles.crossAssetPanelDepthCompact : ""}`}
      hideMetaDate
      icon={MarketIconCrossAsset}
      kicker="CROSS"
      meta={panel.meta}
      statusLabel={panel.stateLabel}
      testId={testId}
      title={panel.title}
    >
      {isEmpty ? (
        <p className={marketStyles.panelEmpty}>{panel.stateDetail}</p>
      ) : (
        <div
          className={`${marketStyles.crossAssetBars} ${depthCompact ? marketStyles.crossAssetBarsDepthCompact : ""}`}
          data-testid="module-home-cross-asset-bars"
        >
          {groupedRows.map(({ bucket, rows }) => (
              <section className={marketStyles.crossAssetBucket} key={bucket}>
                <header className={marketStyles.crossAssetBucketHead}>
                  <span className={marketStyles.crossAssetBucketKicker}>{resolveBucketLabel(bucket)}</span>
                  <em className={marketStyles.crossAssetBucketCount}>{rows.length}</em>
                </header>
                <div className={marketStyles.crossAssetBucketRows}>
                  {rows.map((row) => (
                    <CrossAssetBarRow depthCompact={depthCompact} row={row} key={row.key} />
                  ))}
                </div>
              </section>
            ))}
          {depthCompact ? (
            <MarketCrossAssetGapBlock
              allRows={panel.rows}
              crisisExplain={crisisExplain}
              deskIntel={deskIntel}
              liquidityRow={liquidityRow}
              presentBuckets={presentBuckets}
              primaryKeys={primaryKeys}
            />
          ) : null}
          <footer className={marketStyles.crossAssetPanelFoot}>
            <span>
              展示 {visibleCount}/{panel.rows.length} 条
            </span>
            <Link to="/cross-asset" className={marketStyles.marketIbLink}>
              跨资产页 →
            </Link>
          </footer>
        </div>
      )}
    </MarketMacroPanelShell>
  );
}
