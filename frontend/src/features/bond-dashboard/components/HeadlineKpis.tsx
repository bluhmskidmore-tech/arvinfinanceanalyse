import { ArrowDownOutlined, ArrowUpOutlined } from "@ant-design/icons";
import { Card, Col, Row, Spin } from "antd";

import type { BondDashboardHeadlinePayload, Numeric } from "../../../api/contracts";
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
  format: (v: Numeric | number | null | undefined) => string;
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
      <div style={{ textAlign: "center", padding: 48 }}>
        <Spin />
      </div>
    );
  }
  if (!data) return null;

  const { kpis, prev_kpis } = data;

  return (
    <Row gutter={[16, 16]} data-testid="bond-dashboard-headline-kpis">
      {KPI_DEFS.map((def) => {
        const raw = kpis[def.key];
        const prevRaw = prev_kpis?.[def.key];
        const display = def.format(raw);
        const mom = formatMomRatio(raw, prevRaw);
        const up = mom !== null && mom.startsWith("+");
        const down = mom !== null && mom.startsWith("-");
        const changeColor = up ? "#cf1322" : down ? "#389e0d" : "rgba(0,0,0,0.45)";

        return (
          <Col
            xs={24}
            sm={12}
            md={8}
            lg={6}
            style={{ flex: "1 1 140px", minWidth: 140 }}
            key={def.key}
            data-testid={`bond-dashboard-kpi-${def.key}`}
          >
            <Card
              size="small"
              styles={{ body: { padding: "16px 12px" } }}
              style={{
                borderRadius: 8,
                boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
                height: "100%",
              }}
            >
              <div style={{ fontSize: 13, color: "rgba(0,0,0,0.55)", marginBottom: 8 }}>
                {def.label}
              </div>
              <div style={{ fontSize: 28, fontWeight: 700, lineHeight: 1.15, color: "#1677ff" }}>
                {display}
                <span style={{ fontSize: 13, fontWeight: 500, marginLeft: 4, color: "rgba(0,0,0,0.45)" }}>
                  {def.unit}
                </span>
              </div>
              <div style={{ fontSize: 12, marginTop: 8, color: changeColor, display: "flex", alignItems: "center", gap: 4 }}>
                {mom ? (
                  <>
                    {up ? <ArrowUpOutlined /> : down ? <ArrowDownOutlined /> : null}
                    <span>环比 {mom}</span>
                  </>
                ) : (
                  <span style={{ color: "rgba(0,0,0,0.35)" }}>环比 —</span>
                )}
              </div>
            </Card>
          </Col>
        );
      })}
    </Row>
  );
}
