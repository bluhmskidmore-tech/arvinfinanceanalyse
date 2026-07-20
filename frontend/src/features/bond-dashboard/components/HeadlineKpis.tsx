import { ArrowDownOutlined, ArrowUpOutlined } from "@ant-design/icons";
import { Col, Row, Spin } from "antd";

import type { BondDashboardHeadlinePayload, Numeric } from "../../../api/contracts";
import styles from "../bondDashboard.module.css";
import {
  formatDv01Wan,
  formatMomRatio,
  formatRatePercent,
  formatYears,
  formatYi,
} from "../utils/format";

type KpiKey =
  | "total_market_value"
  | "unrealized_pnl"
  | "weighted_ytm"
  | "weighted_duration"
  | "weighted_coupon"
  | "credit_spread_median"
  | "total_dv01";

const KPI_DEFS: {
  key: KpiKey;
  label: string;
  unit: string;
  format: (v: Numeric | null | undefined) => string;
}[] = [
  { key: "total_market_value", label: "债券持仓规模", unit: "亿", format: formatYi },
  { key: "unrealized_pnl", label: "未实现损益", unit: "亿", format: formatYi },
  { key: "weighted_ytm", label: "加权到期收益率", unit: "%", format: formatRatePercent },
  { key: "weighted_duration", label: "加权久期", unit: "年", format: formatYears },
  { key: "weighted_coupon", label: "加权票息率", unit: "%", format: formatRatePercent },
  { key: "credit_spread_median", label: "信用利差(中位数)", unit: "%", format: formatRatePercent },
  { key: "total_dv01", label: "DV01合计", unit: "万元", format: formatDv01Wan },
];

export function HeadlineKpis({
  data,
  loading,
}: {
  data: BondDashboardHeadlinePayload | undefined;
  loading: boolean;
}) {
  if (loading && !data) {
    return (
      <div className={styles.kpiLoading}>
        <Spin />
      </div>
    );
  }
  if (!data) return null;

  const { kpis, prev_kpis } = data;

  return (
    <Row gutter={[12, 12]} data-testid="bond-dashboard-headline-kpis">
      {KPI_DEFS.map((def) => {
        const raw = kpis[def.key];
        const prevRaw = prev_kpis?.[def.key];
        const display = def.format(raw);
        const mom = formatMomRatio(raw, prevRaw);
        const up = mom !== null && mom.startsWith("+");
        const down = mom !== null && mom.startsWith("-");
        const momTone = mom === null ? "none" : up ? "up" : down ? "down" : "flat";

        return (
          <Col
            xs={24}
            sm={12}
            md={8}
            lg={6}
            xl={3}
            key={def.key}
            data-testid={`bond-dashboard-kpi-${def.key}`}
          >
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>{def.label}</div>
              <div className={styles.kpiValue}>
                {display}
                {display === "—" ? null : <span className={styles.kpiUnit}>{def.unit}</span>}
              </div>
              <div className={styles.kpiMom} data-tone={momTone}>
                {mom ? (
                  <>
                    {up ? <ArrowUpOutlined /> : down ? <ArrowDownOutlined /> : null}
                    <span>环比 {mom}</span>
                  </>
                ) : (
                  <span>环比 —</span>
                )}
              </div>
            </div>
          </Col>
        );
      })}
    </Row>
  );
}
