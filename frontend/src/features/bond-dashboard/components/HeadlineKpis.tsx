import { ArrowDownOutlined, ArrowUpOutlined } from "@ant-design/icons";
import { Card, Col, Row, Spin } from "antd";

import type { BondDashboardHeadlinePayload, Numeric } from "../../../api/contracts";
import { designTokens, ibTokens, tabularNumsStyle } from "../../../theme/designSystem";
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

const dt = designTokens;

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
    <Row gutter={[dt.space[3], dt.space[3]]} data-testid="bond-dashboard-headline-kpis">
      {KPI_DEFS.map((def) => {
        const raw = kpis[def.key];
        const prevRaw = prev_kpis?.[def.key];
        const display = def.format(raw);
        const mom = formatMomRatio(raw, prevRaw);
        const up = mom !== null && mom.startsWith("+");
        const down = mom !== null && mom.startsWith("-");
        const changeColor = up
          ? ibTokens.color.up
          : down
            ? ibTokens.color.down
            : ibTokens.color.inkMuted;

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
            <Card
              size="small"
              styles={{ body: { padding: `${dt.space[3]}px ${dt.space[3] - 2}px` } }}
              style={{
                borderRadius: ibTokens.radius,
                boxShadow: ibTokens.shadow,
                height: "100%",
                borderColor: ibTokens.color.hairline,
              }}
            >
              <div
                style={{
                  fontSize: dt.fontSize[13],
                  color: ibTokens.color.inkSecondary,
                  marginBottom: dt.space[2],
                }}
              >
                {def.label}
              </div>
              <div
                style={{
                  fontSize: dt.fontSize[24],
                  fontWeight: 700,
                  lineHeight: 1.15,
                  color: ibTokens.color.accent,
                  ...tabularNumsStyle,
                }}
              >
                {display}
                {display === "—" ? null : (
                  <span
                    style={{
                      fontSize: dt.fontSize[13],
                      fontWeight: 500,
                      marginLeft: 4,
                      color: ibTokens.color.inkMuted,
                    }}
                  >
                    {def.unit}
                  </span>
                )}
              </div>
              <div
                style={{
                  fontSize: dt.fontSize[12],
                  marginTop: dt.space[2],
                  color: mom ? changeColor : ibTokens.color.inkMuted,
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  ...tabularNumsStyle,
                }}
              >
                {mom ? (
                  <>
                    {up ? <ArrowUpOutlined /> : down ? <ArrowDownOutlined /> : null}
                    <span>环比 {mom}</span>
                  </>
                ) : (
                  <span>环比 —</span>
                )}
              </div>
            </Card>
          </Col>
        );
      })}
    </Row>
  );
}
