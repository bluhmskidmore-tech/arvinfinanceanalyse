import { Card, Col, Row, Tag, Typography } from "antd";

import { dailyNimStressFromKpi, fmtDecimalRatePct } from "../utils/nimStress";
import type { LiabilityYieldKpi } from "../../../api/contracts";

const { Text } = Typography;

/** 中国配色：红=上涨，绿=下跌（用于 NIM 变动方向）。 */
function deltaColor(delta: number | null): string {
  if (delta === null || !Number.isFinite(delta)) {
    return "rgba(0,0,0,0.45)";
  }
  if (delta > 0) {
    return "#cf1322";
  }
  if (delta < 0) {
    return "#389e0d";
  }
  return "rgba(0,0,0,0.65)";
}

export function LiabilityNimStressPanel({
  yieldKpi,
}: {
  yieldKpi: LiabilityYieldKpi | null;
}) {
  const stress = dailyNimStressFromKpi(yieldKpi);
  const bpText =
    stress.delta === null || !Number.isFinite(stress.delta)
      ? "—"
      : `${(stress.delta * 10000).toFixed(0)} bp`;

  return (
    <Card size="small" title="压力测试：NIM 敏感性（+50bps）">
      <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 12 }}>
        口径：资产收益率 − 金融市场同业负债成本（全口径 TYWL + 发行同业存单）；冲击为负债成本 +50bps。
      </Text>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" styles={{ body: { background: "#fafafa" } }}>
            <Text type="secondary">资产收益率</Text>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{fmtDecimalRatePct(stress.ay)}</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" styles={{ body: { background: "#fafafa" } }}>
            <Text type="secondary">金融市场同业负债成本</Text>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{fmtDecimalRatePct(stress.mlc)}</div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              （增值税前）
            </Text>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" styles={{ body: { background: "#fafafa" } }}>
            <Text type="secondary">当前 NIM</Text>
            <div
              style={{
                fontSize: 22,
                fontWeight: 700,
                color:
                  stress.nim !== null && stress.nim < 0 ? "#cf1322" : "rgba(0,0,0,0.88)",
              }}
            >
              {fmtDecimalRatePct(stress.nim)}
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <Text strong style={{ color: "#531dab" }}>
                  压力后 NIM（+50bps）
                </Text>
                {stress.isCritical ? (
                  <Tag color="red" style={{ marginLeft: 8 }}>
                    NIM 预警
                  </Tag>
                ) : null}
              </div>
            </div>
            <div
              style={{
                marginTop: 8,
                fontSize: 22,
                fontWeight: 700,
                color:
                  stress.projected !== null && stress.projected < 0 ? "#cf1322" : "rgba(0,0,0,0.88)",
              }}
            >
              {fmtDecimalRatePct(stress.projected)}
            </div>
            <div style={{ marginTop: 8, fontWeight: 600, color: deltaColor(stress.delta) }}>Δ {bpText}</div>
          </Card>
        </Col>
      </Row>
    </Card>
  );
}
