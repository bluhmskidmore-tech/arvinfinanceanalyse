import { useMemo } from "react";

import type {
  PnlByBusinessScaleYieldQuadrantKey,
  PnlByBusinessScaleYieldQuadrantRow,
  PnlByBusinessScaleYieldQuadrantSummary,
} from "../../api/contracts";

type QuadrantDefinition = {
  key: PnlByBusinessScaleYieldQuadrantKey;
  label: string;
  title: string;
  hint: string;
};

const QUADRANTS: QuadrantDefinition[] = [
  {
    key: "LARGE_HIGH",
    label: "核心收益观察",
    title: "规模较大、收益较高",
    hint: "资源占用与FTP后收益均不低于当期中位数，关注收益持续性。",
  },
  {
    key: "LARGE_LOW",
    label: "重点原因核查",
    title: "规模较大、收益较低",
    hint: "资源占用不低于中位数，FTP后收益低于中位数，优先核查收益成因。",
  },
  {
    key: "SMALL_HIGH",
    label: "收益持续性观察",
    title: "规模较小、收益较高",
    hint: "资源占用低于中位数，FTP后收益不低于中位数，辨别收益是否稳定。",
  },
  {
    key: "SMALL_LOW",
    label: "策略职能核查",
    title: "规模较小、收益较低",
    hint: "两轴均低于当期中位数，结合流动性、做市或服务职能解读。",
  },
];

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
        <span>{definition.label}</span>
        <strong>{definition.title}</strong>
        <p>{definition.hint}</p>
      </div>
      {rows.length === 0 ? (
        <div>暂无业务种类落入该象限</div>
      ) : (
        rows.map((row) => (
          <div key={row.row_key} className="pnl-by-business-insights-quadrant-row">
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
      <div className="pnl-by-business-insights-quadrant-note" data-testid="capital-efficiency-quadrant-note">
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
        <div className="pnl-by-business-insights-quadrant-grid" data-testid="capital-efficiency-quadrant-grid">
          {QUADRANTS.map((definition) => (
            <QuadrantCard
              key={definition.key}
              definition={definition}
              rows={rowsByQuadrant.get(definition.key) ?? []}
            />
          ))}
        </div>
      ) : (
        <div className="pnl-by-business-insights-quadrant-empty" data-testid="capital-efficiency-quadrant-empty">
          有效父级业务 {summary.eligible_row_count} 个，至少需要 {summary.minimum_eligible_rows} 个，暂不进行象限分类。
        </div>
      )}
    </div>
  );
}
