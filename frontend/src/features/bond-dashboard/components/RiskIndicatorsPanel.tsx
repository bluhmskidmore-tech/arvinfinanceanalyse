import { Button, Card } from "antd";

import type { Numeric, RiskIndicatorsPayload } from "../../../api/contracts";
import { EM_DASH } from "../../../pageModel";
import styles from "../bondDashboard.module.css";
import { formatDv01Wan, formatRatePercent, formatYears, formatYi, nativeToNumber } from "../utils/format";

function withUnit(value: string, unit: string): string {
  const separator = unit === "%" ? "" : " ";
  return value === EM_DASH ? EM_DASH : `${value}${separator}${unit}`;
}

function formatConvexity(value: Numeric | null | undefined): string {
  const raw = nativeToNumber(value);
  return raw === null ? EM_DASH : raw.toFixed(4);
}

const ROWS: {
  label: string;
  key: keyof RiskIndicatorsPayload;
  format: (v: Numeric | null | undefined) => string;
}[] = [
  { label: "组合市值", key: "total_market_value", format: (v) => withUnit(formatYi(v), "亿") },
  { label: "DV01", key: "total_dv01", format: (v) => withUnit(formatDv01Wan(v), "万元") },
  { label: "加权久期", key: "weighted_duration", format: (v) => withUnit(formatYears(v), "年") },
  { label: "信用占比", key: "credit_ratio", format: (v) => withUnit(formatRatePercent(v), "%") },
  { label: "凸性(加权)", key: "weighted_convexity", format: formatConvexity },
  { label: "利差 DV01", key: "total_spread_dv01", format: (v) => withUnit(formatDv01Wan(v), "万元") },
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
    <Card
      data-testid="bond-dashboard-risk-indicators-panel"
      loading={loading}
      title="风险指标"
      extra={<Button type="link">更多</Button>}
      rootClassName={styles.card}
    >
      <div className={styles.riskList}>
        {ROWS.map((r) => (
          <div
            key={r.key}
            data-testid={`bond-dashboard-risk-row-${String(r.key)}`}
            className={styles.riskRow}
          >
            <span className={styles.riskRowLabel}>{r.label}</span>
            <span className={styles.riskRowValue}>
              {data ? r.format(data[r.key] as Numeric | null | undefined) : EM_DASH}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}
