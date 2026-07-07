import { useMemo } from "react";

import type { PnlByBusinessYtdItem } from "../../api/contracts";
import { isParentZqtzBusinessRow } from "../pnl/pnlByBusinessPageModel";
import { designTokens } from "../../theme/designSystem";

export type CapitalEfficiencyQuadrantKey = "large_high" | "large_low" | "small_high" | "small_low";

export type CapitalEfficiencyQuadrantRow = {
  row_key: string;
  business_type: string;
  proportion_pct: number;
  ftp_net_annualized_yield_pct: number;
};

export type CapitalEfficiencyQuadrantBucket = {
  key: CapitalEfficiencyQuadrantKey;
  title: string;
  hint: string;
  rows: CapitalEfficiencyQuadrantRow[];
};

export type CapitalEfficiencyQuadrantModel = {
  hasEnoughData: boolean;
  proportionMedianPct: number | null;
  yieldMedianPct: number | null;
  buckets: CapitalEfficiencyQuadrantBucket[];
};

const QUADRANT_DEFS: Array<{ key: CapitalEfficiencyQuadrantKey; title: string; hint: string }> = [
  { key: "large_high", title: "规模大 · 效率高", hint: "重点关注：增配价值" },
  { key: "large_low", title: "规模大 · 效率低", hint: "重点关注：是否压缩" },
  { key: "small_high", title: "规模小 · 效率高", hint: "重点关注：是否值得增配" },
  { key: "small_low", title: "规模小 · 效率低", hint: "重点关注：边际业务" },
];

function toNumber(value: string | null | undefined): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function median(values: number[]): number | null {
  if (values.length === 0) {
    return null;
  }
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

function classifyQuadrant(
  row: CapitalEfficiencyQuadrantRow,
  proportionMedianPct: number,
  yieldMedianPct: number,
): CapitalEfficiencyQuadrantKey {
  const isLarge = row.proportion_pct >= proportionMedianPct;
  const isHigh = row.ftp_net_annualized_yield_pct >= yieldMedianPct;
  if (isLarge && isHigh) {
    return "large_high";
  }
  if (isLarge && !isHigh) {
    return "large_low";
  }
  if (!isLarge && isHigh) {
    return "small_high";
  }
  return "small_low";
}

export function buildCapitalEfficiencyQuadrantModel(items: PnlByBusinessYtdItem[]): CapitalEfficiencyQuadrantModel {
  const eligibleRows: CapitalEfficiencyQuadrantRow[] = items
    .filter(isParentZqtzBusinessRow)
    .reduce<CapitalEfficiencyQuadrantRow[]>((acc, item) => {
      const proportion = toNumber(item.proportion);
      const yieldPct = toNumber(item.ftp_net_annualized_yield_pct);
      if (proportion === null || yieldPct === null) {
        return acc;
      }
      acc.push({
        row_key: item.row_key,
        business_type: item.business_type,
        proportion_pct: proportion * 100,
        ftp_net_annualized_yield_pct: yieldPct,
      });
      return acc;
    }, []);

  if (eligibleRows.length === 0) {
    return {
      hasEnoughData: false,
      proportionMedianPct: null,
      yieldMedianPct: null,
      buckets: QUADRANT_DEFS.map((def) => ({ ...def, rows: [] })),
    };
  }

  const proportionMedianPct = median(eligibleRows.map((row) => row.proportion_pct)) as number;
  const yieldMedianPct = median(eligibleRows.map((row) => row.ftp_net_annualized_yield_pct)) as number;

  const rowsByQuadrant = new Map<CapitalEfficiencyQuadrantKey, CapitalEfficiencyQuadrantRow[]>(
    QUADRANT_DEFS.map((def) => [def.key, []]),
  );
  for (const row of eligibleRows) {
    const key = classifyQuadrant(row, proportionMedianPct, yieldMedianPct);
    rowsByQuadrant.get(key)!.push(row);
  }
  for (const rows of rowsByQuadrant.values()) {
    rows.sort((a, b) => b.proportion_pct - a.proportion_pct);
  }

  return {
    hasEnoughData: true,
    proportionMedianPct,
    yieldMedianPct,
    buckets: QUADRANT_DEFS.map((def) => ({ ...def, rows: rowsByQuadrant.get(def.key) ?? [] })),
  };
}

const noteStyle = {
  margin: "0 0 16px",
  padding: 14,
  borderRadius: designTokens.radius.md,
  border: `1px solid ${designTokens.color.info[200]}`,
  background: designTokens.color.info[50],
  color: designTokens.color.neutral[700],
  fontSize: 13,
  lineHeight: 1.6,
} as const;

const emptyStateStyle = {
  padding: 16,
  borderRadius: designTokens.radius.md,
  border: `1px dashed ${designTokens.color.neutral[200]}`,
  color: designTokens.color.neutral[600],
  fontSize: 13,
} as const;

const quadrantGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(2, minmax(240px, 1fr))",
  gap: designTokens.space[4],
} as const;

const quadrantCardStyle = {
  padding: 14,
  borderRadius: designTokens.radius.md,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: designTokens.color.neutral[50],
  minHeight: 148,
} as const;

const quadrantCardHeaderStyle = {
  display: "flex",
  flexDirection: "column",
  gap: 2,
  marginBottom: 10,
} as const;

const quadrantTitleStyle = {
  fontSize: 14,
  fontWeight: 600,
  color: designTokens.color.neutral[900],
} as const;

const quadrantHintStyle = {
  fontSize: 12,
  color: designTokens.color.info[700],
} as const;

const quadrantRowStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: 12,
  padding: "6px 0",
  borderBottom: `1px solid ${designTokens.color.neutral[100]}`,
  fontSize: 13,
  color: designTokens.color.neutral[800],
} as const;

const quadrantEmptyRowStyle = {
  fontSize: 12,
  color: designTokens.color.neutral[500],
  padding: "6px 0",
} as const;

function formatPercentValue(value: number, digits = 2): string {
  return `${value.toFixed(digits)}%`;
}

function QuadrantCard({ bucket }: { bucket: CapitalEfficiencyQuadrantBucket }) {
  return (
    <div style={quadrantCardStyle} data-testid={`capital-efficiency-quadrant-${bucket.key}`}>
      <div style={quadrantCardHeaderStyle}>
        <span style={quadrantTitleStyle}>{bucket.title}</span>
        <span style={quadrantHintStyle}>{bucket.hint}</span>
      </div>
      {bucket.rows.length === 0 ? (
        <div style={quadrantEmptyRowStyle}>暂无业务种类落入此象限</div>
      ) : (
        bucket.rows.map((row) => (
          <div key={row.row_key} style={quadrantRowStyle}>
            <span>{row.business_type}</span>
            <span>
              份额 {formatPercentValue(row.proportion_pct)} · 收益率{" "}
              {formatPercentValue(row.ftp_net_annualized_yield_pct)}
            </span>
          </div>
        ))
      )}
    </div>
  );
}

export function CapitalEfficiencyQuadrantPanel({ items }: { items: PnlByBusinessYtdItem[] }) {
  const model = useMemo(() => buildCapitalEfficiencyQuadrantModel(items), [items]);

  return (
    <div data-testid="capital-efficiency-quadrant-panel">
      <div style={noteStyle} data-testid="capital-efficiency-quadrant-note">
        分割线为当期父级行的份额与FTP后年化收益率中位数，仅用于本页展示分类，不代表业务已确认的分类标准，不参与任何组合指标重算。
        {model.hasEnoughData ? (
          <>
            {" "}
            当期份额中位数 {formatPercentValue(model.proportionMedianPct as number)}，FTP后年化收益率中位数{" "}
            {formatPercentValue(model.yieldMedianPct as number)}。
          </>
        ) : null}
      </div>

      {model.hasEnoughData ? (
        <div style={quadrantGridStyle} data-testid="capital-efficiency-quadrant-grid">
          {model.buckets.map((bucket) => (
            <QuadrantCard key={bucket.key} bucket={bucket} />
          ))}
        </div>
      ) : (
        <div style={emptyStateStyle} data-testid="capital-efficiency-quadrant-empty">
          暂无足够的份额（proportion）与FTP后年化收益率（ftp_net_annualized_yield_pct）数据用于象限计算。
        </div>
      )}
    </div>
  );
}
