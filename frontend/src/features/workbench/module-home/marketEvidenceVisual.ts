import type { ComponentType } from "react";

import type { ModuleHomeDetailRow } from "./moduleHomeModel";
import {
  MarketIconCommodity,
  MarketIconCredit,
  MarketIconCrisis,
  MarketIconEquity,
  MarketIconFx,
  MarketIconLiquidity,
  MarketIconMacroToolkit,
  MarketIconRisk,
  type MarketIconProps,
} from "./marketHomeIcons";

export type MarketVisualAccent = "navy" | "green" | "gold" | "slate";

type MarketVisualSpec = {
  icon: ComponentType<MarketIconProps>;
  accent: MarketVisualAccent;
  kicker: string;
};

const SIGNAL_VISUALS: Record<string, MarketVisualSpec> = {
  liquidity: { icon: MarketIconLiquidity, accent: "gold", kicker: "LQD" },
  risk_appetite: { icon: MarketIconRisk, accent: "slate", kicker: "RISK" },
  credit: { icon: MarketIconCredit, accent: "green", kicker: "CRDT" },
  a_share_stampede_risk: { icon: MarketIconCrisis, accent: "slate", kicker: "A股" },
  crisis_score_cn: { icon: MarketIconCrisis, accent: "slate", kicker: "CRIS" },
  outputs: { icon: MarketIconMacroToolkit, accent: "navy", kicker: "OUT" },
};

const MACRO_SIGNAL_META_EVIDENCE = /^(?:score|regime)=/i;

export type CrossAssetBucket = "equity" | "fx" | "commod" | "other";

export type CrossAssetTraderBucket = "rates" | CrossAssetBucket;

const TRADER_CROSS_ASSET_MAX_ROWS = 16;

const TRADER_CROSS_ASSET_BUCKET_ORDER: CrossAssetTraderBucket[] = ["rates", "equity", "fx", "commod", "other"];

const TRADER_CROSS_ASSET_BUCKET_CAPS: Record<CrossAssetTraderBucket, number> = {
  rates: 4,
  equity: 5,
  fx: 4,
  commod: 4,
  other: 2,
};

const CROSS_ASSET_BUCKET_LABELS: Record<CrossAssetBucket, string> = {
  equity: "EQUITY",
  fx: "FX",
  commod: "COMMOD",
  other: "OTHER",
};

const CROSS_ASSET_BUCKET_VISUALS: Record<CrossAssetBucket, MarketVisualSpec> = {
  equity: { icon: MarketIconEquity, accent: "navy", kicker: "EQUITY" },
  fx: { icon: MarketIconFx, accent: "gold", kicker: "FX" },
  commod: { icon: MarketIconCommodity, accent: "green", kicker: "COMMOD" },
  other: { icon: MarketIconMacroToolkit, accent: "slate", kicker: "OTHER" },
};

export function marketSignalVisual(key: string): MarketVisualSpec {
  return (
    SIGNAL_VISUALS[key] ?? {
      icon: MarketIconMacroToolkit,
      accent: "navy",
      kicker: "SIG",
    }
  );
}

export function crossAssetBucket(row: ModuleHomeDetailRow): CrossAssetBucket {
  const text = `${row.key} ${row.label} ${row.source}`.toUpperCase();
  if (/沪深|CSI|HS300|指数|SH000|HSI|SPX|NASDAQ/.test(text)) {
    return "equity";
  }
  if (/USD|CNY|USDCNY|汇率|FX|DXY/.test(text)) {
    return "fx";
  }
  if (/BRENT|原油|铜|铝|商品|COMMOD|期货|OIL|GOLD|WTI|南华/.test(text)) {
    return "commod";
  }
  return "other";
}

function crossAssetRowHaystack(row: ModuleHomeDetailRow): string {
  return `${row.key} ${row.label} ${row.source}`.toUpperCase();
}

export function crossAssetTraderBucket(row: ModuleHomeDetailRow): CrossAssetTraderBucket {
  const text = crossAssetRowHaystack(row);
  if (/DR007|SHIBOR|R007|FR007|回购|资金|LIQUIDITY/.test(text)) {
    return "rates";
  }
  return crossAssetBucket(row);
}

function crossAssetTraderRelevanceScore(row: ModuleHomeDetailRow): number {
  const text = crossAssetRowHaystack(row);
  if (/CSI300|沪深300|HS300/.test(text)) return 100;
  if (/DR007|SHIBOR/.test(text)) return 95;
  if (/USDCNY|USD\/CNY|USD.CNY/.test(text)) return 90;
  if (/BRENT|原油|WTI/.test(text)) return 85;
  if (/南华/.test(text)) return 80;
  if (/HSI|恒生/.test(text)) return 70;
  if (/SPX|NASDAQ|S&P/.test(text)) return 55;
  if (/DXY/.test(text)) return 50;
  return 15;
}

function crossAssetRowFamily(row: ModuleHomeDetailRow): string {
  const text = crossAssetRowHaystack(row);
  if (/CSI300|沪深300|HS300|SH000300/.test(text)) {
    if (/涨跌幅|PCT|CHANGE|CHG/.test(text)) return "csi300-change";
    if (/市盈|\bPE\b/.test(text)) return "csi300-pe";
    if (/权重|WEIGHT|TOP ?\d/.test(text)) return "csi300-weight";
    return "csi300-level";
  }
  if (/USDCNY|USD\/CNY|USD.CNY|USDCNH/.test(text)) return "usdcny";
  if (/DR007|SHIBOR|R007|FR007/.test(text)) return "rates-short";
  if (/BRENT|原油|WTI/.test(text)) return "brent";
  if (/南华/.test(text)) return "nanhua";
  if (/HSI|恒生/.test(text)) return "hsi";
  if (/SPX|NASDAQ|S&P/.test(text)) return "spx";
  if (/DXY/.test(text)) return "dxy";
  if (/铜|COPPER/.test(text)) return "copper";
  if (/铝|ALUMIN/.test(text)) return "aluminum";
  return row.key;
}

function crossAssetRowDisplayPriority(row: ModuleHomeDetailRow): number {
  const text = crossAssetRowHaystack(row);
  if (/收盘|CLOSE|SPOT|现价|LAST/.test(text)) return 100;
  if (/涨跌幅|PCT|CHANGE|CHG|日变动/.test(text)) return 95;
  if (/DR007|SHIBOR|USDCNY|BRENT|原油/.test(text)) return 90;
  if (/市盈|\bPE\b|权重|WEIGHT/.test(text)) return 15;
  return 55;
}

function crossAssetRowSortScore(row: ModuleHomeDetailRow): number {
  return crossAssetRowDisplayPriority(row) + crossAssetTraderRelevanceScore(row);
}

export function filterCrossAssetRowsForTrader(
  rows: readonly ModuleHomeDetailRow[],
  options?: { traderMode?: boolean; maxRows?: number },
): ModuleHomeDetailRow[] {
  if (options?.traderMode === false) {
    return [...rows];
  }

  const maxRows = options?.maxRows ?? TRADER_CROSS_ASSET_MAX_ROWS;
  const groups = new Map<CrossAssetTraderBucket, ModuleHomeDetailRow[]>();

  for (const row of rows) {
    const bucket = crossAssetTraderBucket(row);
    const existing = groups.get(bucket) ?? [];
    existing.push(row);
    groups.set(bucket, existing);
  }

  for (const [bucket, groupRows] of groups) {
    groupRows.sort((left, right) => crossAssetRowSortScore(right) - crossAssetRowSortScore(left));
    groups.set(bucket, groupRows);
  }

  const result: ModuleHomeDetailRow[] = [];
  for (const bucket of TRADER_CROSS_ASSET_BUCKET_ORDER) {
    const groupRows = groups.get(bucket) ?? [];
    const seenFamilies = new Set<string>();
    let takenInBucket = 0;

    for (const row of groupRows) {
      if (result.length >= maxRows || takenInBucket >= TRADER_CROSS_ASSET_BUCKET_CAPS[bucket]) {
        break;
      }
      if (crossAssetRowDisplayPriority(row) < 40) {
        continue;
      }
      if (crossAssetTraderRelevanceScore(row) < 50) {
        continue;
      }
      const family = crossAssetRowFamily(row);
      if (seenFamilies.has(family)) {
        continue;
      }
      if (crossAssetTraderRelevanceScore(row) < 20 && crossAssetRowDisplayPriority(row) < 50) {
        continue;
      }
      seenFamilies.add(family);
      result.push(row);
      takenInBucket += 1;
    }
  }

  return result;
}

export function filterCrossAssetSecondaryRows(
  rows: readonly ModuleHomeDetailRow[],
  primaryKeys: ReadonlySet<string>,
  options?: { maxRows?: number },
): ModuleHomeDetailRow[] {
  const maxRows = options?.maxRows ?? 6;

  return rows
    .filter((row) => !primaryKeys.has(row.key))
    .filter(
      (row) =>
        crossAssetTraderRelevanceScore(row) >= 40 || crossAssetRowDisplayPriority(row) >= 50,
    )
    .sort((left, right) => crossAssetRowSortScore(right) - crossAssetRowSortScore(left))
    .slice(0, maxRows);
}

export function traderCrossAssetBucketOrder(): readonly CrossAssetTraderBucket[] {
  return TRADER_CROSS_ASSET_BUCKET_ORDER;
}

export function crossAssetBucketLabel(bucket: CrossAssetBucket): string {
  return CROSS_ASSET_BUCKET_LABELS[bucket];
}

export function crossAssetBucketVisual(bucket: CrossAssetBucket): MarketVisualSpec {
  return CROSS_ASSET_BUCKET_VISUALS[bucket];
}

export function crossAssetRowVisual(row: ModuleHomeDetailRow): MarketVisualSpec {
  return crossAssetBucketVisual(crossAssetBucket(row));
}

export function parseMacroSignalValue(value: string): { stance: string; score?: string } {
  const trimmed = value.trim();
  const match = trimmed.match(/^(.+?)\s·\s(-?\d+(?:\.\d+)?)$/);
  if (match) {
    return { stance: match[1].trim(), score: match[2] };
  }
  return { stance: trimmed };
}

export function formatMacroSignalEvidence(evidence: readonly string[] | string): string {
  const lines = Array.isArray(evidence)
    ? evidence
    : evidence
        .split(" · ")
        .map((part) => part.trim())
        .filter(Boolean);

  return lines
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !MACRO_SIGNAL_META_EVIDENCE.test(line))
    .map((line) => {
      const percentile = line.match(/^percentile=(.+)$/i);
      if (percentile) {
        return `历史分位 ${percentile[1]}`;
      }
      return line;
    })
    .join(" · ");
}

export const MARKET_KPI_ACCENT: Record<string, MarketVisualAccent> = {
  "a-share-risk": "slate",
  macro: "gold",
  "ten-year": "navy",
  liquidity: "gold",
  "term-spread-10y-2y": "slate",
  "term-spread-10y-5y": "slate",
  "term-spread-10y-1y": "slate",
};
