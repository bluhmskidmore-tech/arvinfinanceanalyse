import { Card, Col, Row, Typography } from "antd";

import type { LiabilityAdbMonthlyItem } from "../../../api/contracts";

const { Text } = Typography;

export function LiabilityNimStressMonthlyPanel({
  adbMonth,
}: {
  adbMonth: LiabilityAdbMonthlyItem | null;
}) {
  const nim = adbMonth?.net_interest_margin;
  const projected =
    nim !== null && nim !== undefined && Number.isFinite(nim) ? nim - 0.5 : null;

  return (
    <Card size="small" title="压力测试：NIM 敏感性（+50bps）">
      <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 12 }}>
        口径：月度日均（ADB 月度收益率/付息率；若缺失则仅展示结构）。
      </Text>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" styles={{ body: { background: "#fafafa" } }}>
            <Text type="secondary">资产收益率（月日均）</Text>
            <div style={{ fontSize: 22, fontWeight: 700 }}>
              {adbMonth?.asset_yield === null || adbMonth?.asset_yield === undefined
                ? "—"
                : `${adbMonth.asset_yield.toFixed(2)}%`}
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" styles={{ body: { background: "#fafafa" } }}>
            <Text type="secondary">负债付息率（月日均）</Text>
            <div style={{ fontSize: 22, fontWeight: 700 }}>
              {adbMonth?.liability_cost === null || adbMonth?.liability_cost === undefined
                ? "—"
                : `${adbMonth.liability_cost.toFixed(2)}%`}
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" styles={{ body: { background: "#fafafa" } }}>
            <Text type="secondary">当前 NIM（月日均）</Text>
            <div
              style={{
                fontSize: 22,
                fontWeight: 700,
                color:
                  nim !== null && nim !== undefined && nim < 0 ? "#cf1322" : "rgba(0,0,0,0.88)",
              }}
            >
              {nim === null || nim === undefined ? "—" : `${nim.toFixed(2)}%`}
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small">
            <Text strong style={{ color: "#531dab" }}>
              压力后 NIM（+50bps）
            </Text>
            <div
              style={{
                marginTop: 8,
                fontSize: 22,
                fontWeight: 700,
                color:
                  projected !== null && projected < 0 ? "#cf1322" : "rgba(0,0,0,0.88)",
              }}
            >
              {projected === null ? "—" : `${projected.toFixed(2)}%`}
            </div>
            <div style={{ marginTop: 8, fontWeight: 600, color: "#389e0d" }}>
              {nim === null || nim === undefined ? "Δ —" : "−50 bp（NIM 下行）"}
            </div>
          </Card>
        </Col>
      </Row>
    </Card>
  );
}
