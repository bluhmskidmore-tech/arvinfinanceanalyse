import { Card, Col, Row, Typography } from "antd";

import type { LiabilitiesMonthlyItem, Numeric } from "../../../api/contracts";
import { isNumeric } from "../../../api/numeric";
import { formatNumeric } from "../../../utils/format";

const { Text } = Typography;

function dispNumeric(n: Numeric | null | undefined): string {
  if (!n || !isNumeric(n)) {
    return "—";
  }
  return formatNumeric(n);
}

export function LiabilityMonthlySnapshotCards({
  month,
  ytdAvgTotalLiabilities,
  ytdAvgLiabilityCost,
}: {
  month: LiabilitiesMonthlyItem | null;
  ytdAvgTotalLiabilities: Numeric | null;
  ytdAvgLiabilityCost: Numeric | null;
}) {
  if (!month) {
    return null;
  }

  return (
    <Card size="small" title="月度概览（月日均）">
      <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 12 }}>
        数值均来自 governed Numeric（展示以后端下发 display 为准）。
      </Text>
      <Row gutter={[12, 12]}>
        <Col xs={24} sm={12} lg={8}>
          <Card size="small" styles={{ body: { background: "#fafafa" } }}>
            <Text type="secondary">总负债（月日均）</Text>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{dispNumeric(month.avg_total_liabilities)}</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card size="small" styles={{ body: { background: "#fafafa" } }}>
            <Text type="secondary">同业负债（月日均）</Text>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{dispNumeric(month.avg_interbank_liabilities)}</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card size="small" styles={{ body: { background: "#fafafa" } }}>
            <Text type="secondary">发行负债（月日均）</Text>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{dispNumeric(month.avg_issued_liabilities)}</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card size="small" styles={{ body: { background: "#fafafa" } }}>
            <Text type="secondary">负债付息率</Text>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{dispNumeric(month.avg_liability_cost)}</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card size="small" styles={{ body: { background: "#fafafa" } }}>
            <Text type="secondary">环比变动（额）</Text>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{dispNumeric(month.mom_change)}</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card size="small" styles={{ body: { background: "#fafafa" } }}>
            <Text type="secondary">环比变动（%）</Text>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{dispNumeric(month.mom_change_pct)}</div>
          </Card>
        </Col>
      </Row>
      <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
        <Col xs={24} sm={12}>
          <Card size="small">
            <Text type="secondary">YTD 日均总负债</Text>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{dispNumeric(ytdAvgTotalLiabilities)}</div>
          </Card>
        </Col>
        <Col xs={24} sm={12}>
          <Card size="small">
            <Text type="secondary">YTD 平均负债成本</Text>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{dispNumeric(ytdAvgLiabilityCost)}</div>
          </Card>
        </Col>
      </Row>
    </Card>
  );
}
