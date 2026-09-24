import type { Numeric, RiskIndicatorsPayload } from "../../../api/contracts";
import { EM_DASH } from "../../../pageModel";
import { formatDv01Wan, formatRatePercent, nativeToNumber } from "../utils/format";

function withUnit(value: string, unit: string): string {
  const separator = unit === "%" ? "" : " ";
  return value === EM_DASH ? EM_DASH : `${value}${separator}${unit}`;
}

/* 展示收敛 2 位（与后端 Numeric.display 精度一致）；完整原值走行 title。 */
function formatConvexity(value: Numeric | null | undefined): string {
  const raw = nativeToNumber(value);
  return raw === null ? EM_DASH : raw.toFixed(2);
}

function convexityTitle(value: Numeric | null | undefined): string | undefined {
  const raw = nativeToNumber(value);
  return raw === null ? undefined : `原值 ${raw}`;
}

/*
 * 组合市值 / DV01 / 加权久期与 01 区 KPI 带逐字同值，2026-08-14 去重后
 * 本面板只保留 KPI 带未含的风险读数（后端 RiskIndicatorsPayload 亦无
 * 关键期限 DV01、再投资结构等增量字段可补）。
 */
const ROWS: {
  label: string;
  key: keyof RiskIndicatorsPayload;
  format: (v: Numeric | null | undefined) => string;
  /** 悬停披露完整原值（如凸性展示收敛 2 位后）。 */
  title?: (v: Numeric | null | undefined) => string | undefined;
}[] = [
  { label: "信用占比", key: "credit_ratio", format: (v) => withUnit(formatRatePercent(v), "%") },
  {
    label: "凸性(加权)",
    key: "weighted_convexity",
    format: formatConvexity,
    title: convexityTitle,
  },
  /* 质量披露：承载凸性字段的市值占比，解释上一行加权凸性的口径覆盖面。 */
  {
    label: "凸性覆盖率",
    key: "weighted_convexity_coverage_ratio",
    format: (v) => withUnit(formatRatePercent(v), "%"),
  },
  { label: "利差 DV01（万元/bp）", key: "total_spread_dv01", format: formatDv01Wan },
  { label: "1年内再投资占比", key: "reinvestment_ratio_1y", format: (v) => withUnit(formatRatePercent(v), "%") },
];

export function RiskIndicatorsPanel({
  data,
  loading,
}: {
  data: RiskIndicatorsPayload | undefined;
  loading: boolean;
}) {
  return (
    <div
      data-testid="bond-dashboard-risk-indicators-panel"
      className="bond-dashboard-page__panel bond-dashboard-table-panel"
    >
      <h3 className="bond-dashboard-table-panel__title">风险指标</h3>
      {loading ? (
        <p className="bond-dashboard-page__surface bond-dashboard-page__surface--loading">
          载入中…
        </p>
      ) : (
        <div className="bond-dashboard-risk-list">
          {ROWS.map((r) => {
            const value = data ? (data[r.key] as Numeric | null | undefined) : undefined;
            return (
              <div
                key={r.key}
                data-testid={`bond-dashboard-risk-row-${String(r.key)}`}
                className="bond-dashboard-risk-list__row"
              >
                <span className="bond-dashboard-risk-list__label">{r.label}</span>
                <span
                  className="bond-dashboard-risk-list__value"
                  title={data ? r.title?.(value) : undefined}
                >
                  {data ? r.format(value) : EM_DASH}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
