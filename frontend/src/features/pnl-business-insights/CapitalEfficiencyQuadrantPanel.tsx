import { useMemo } from "react";

import type {
  PnlByBusinessScaleYieldQuadrantKey,
  PnlByBusinessScaleYieldQuadrantRow,
  PnlByBusinessScaleYieldQuadrantSummary,
} from "../../api/contracts";
import { designTokens } from "../../theme/designSystem";

type QuadrantDefinition = {
  key: PnlByBusinessScaleYieldQuadrantKey;
  title: string;
  hint: string;
};

const QUADRANTS: QuadrantDefinition[] = [
  { key: "LARGE_HIGH", title: "规模较大 · 收益较高", hint: "相对当期中位数的描述性分类" },
  { key: "LARGE_LOW", title: "规模较大 · 收益较低", hint: "相对当期中位数的描述性分类" },
  { key: "SMALL_HIGH", title: "规模较小 · 收益较高", hint: "相对当期中位数的描述性分类" },
  { key: "SMALL_LOW", title: "规模较小 · 收益较低", hint: "相对当期中位数的描述性分类" },
];

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

const quadrantRowStyle = {
  display: "flex",
  justifyContent: "space-between",
  gap: 12,
  padding: "6px 0",
  borderBottom: `1px solid ${designTokens.color.neutral[100]}`,
  fontSize: 13,
  color: designTokens.color.neutral[800],
} as const;

function numberValue(value: string | null): number | null {
  if (value === null || value === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatPct(value: string | null, digits = 2): string {
  const parsed = numberValue(value);
  return parsed === null ? "—" : `${parsed.toFixed(digits)}%`;
}

function QuadrantCard({
  definition,
  rows,
}: {
  definition: QuadrantDefinition;
  rows: PnlByBusinessScaleYieldQuadrantRow[];
}) {
  return (
    <div
      className="pnl-by-business-insights-quadrant-card"
      data-testid={`capital-efficiency-quadrant-${definition.key.toLowerCase()}`}
    >
      <div className="pnl-by-business-insights-quadrant-card__header">
        <strong>{definition.title}</strong>
        <span>{definition.hint}</span>
      </div>
      {rows.length === 0 ? (
        <div>暂无业务种类落入该象限</div>
      ) : (
        rows.map((row) => (
          <div key={row.row_key} style={quadrantRowStyle}>
            <span>{row.business_type}</span>
            <span>
              日均份额 {formatPct(row.scale_share_pct)} · FTP后年化 {formatPct(row.ftp_net_annualized_yield_pct)}
            </span>
          </div>
        ))
      )}
    </div>
  );
}

export function CapitalEfficiencyQuadrantPanel({
  summary,
}: {
  summary: PnlByBusinessScaleYieldQuadrantSummary;
}) {
  const rowsByQuadrant = useMemo(() => {
    const grouped = new Map<PnlByBusinessScaleYieldQuadrantKey, PnlByBusinessScaleYieldQuadrantRow[]>(
      QUADRANTS.map((definition) => [definition.key, []]),
    );
    for (const row of summary.rows) {
      grouped.get(row.quadrant_key)?.push(row);
    }
    return grouped;
  }, [summary.rows]);

  const available =
    summary.available && summary.eligible_row_count >= summary.minimum_eligible_rows;

  return (
    <div data-testid="capital-efficiency-quadrant-panel">
      <div style={noteStyle} data-testid="capital-efficiency-quadrant-note">
        规模轴使用 YTD 日均余额份额，收益轴使用 FTP 后年化收益率；人民币等值、父级业务口径。
        {available ? (
          <>
            {" "}
            日均余额份额中位数 {formatPct(summary.scale_share_median_pct)}，FTP后年化收益率中位数{" "}
            {formatPct(summary.ftp_net_annualized_yield_median_pct)}。象限仅用于当期相对比较，不构成增减配置建议。
          </>
        ) : null}
      </div>

      {available ? (
        <div style={quadrantGridStyle} data-testid="capital-efficiency-quadrant-grid">
          {QUADRANTS.map((definition) => (
            <QuadrantCard
              key={definition.key}
              definition={definition}
              rows={rowsByQuadrant.get(definition.key) ?? []}
            />
          ))}
        </div>
      ) : (
        <div style={emptyStateStyle} data-testid="capital-efficiency-quadrant-empty">
          有效父级业务 {summary.eligible_row_count} 个，至少需要 {summary.minimum_eligible_rows} 个，暂不进行象限分类。
        </div>
      )}
    </div>
  );
}
