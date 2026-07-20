import { Card, Col, Row, Typography } from "antd";

import type { AdbMonthlyDataItem } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";

const { Text } = Typography;

export function LiabilityNimStressMonthlyPanel({
  adbMonth,
}: {
  adbMonth: AdbMonthlyDataItem | null;
}) {
  const nim = adbMonth?.net_interest_margin;
  const projected =
    nim !== null && nim !== undefined && Number.isFinite(nim) ? nim - 0.5 : null;
  /** 与 V1 月度卡一致：压力后 NIM（百分点）跌破 0 标红，并以 Tag 提示。 */
  const isCritical = projected !== null && Number.isFinite(projected) && projected < 0;
  const nimNegative = nim !== null && nim !== undefined && nim < 0;
  const projectedNegative = projected !== null && projected < 0;

  return (
    <Card
      size="small"
      title="压力测试：NIM 敏感性（+50bps）"
      extra={isCritical ? <span className="liability-status-pill">NIM 预警</span> : null}
    >
      <Text type="secondary" className="liability-panel-caption">
        口径：月度日均（月度收益率/付息率；若缺失则仅展示结构）。
      </Text>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" className="liability-metric-tile">
            <Text type="secondary">资产收益率（月日均）</Text>
            <div className="liability-metric-value">
              {adbMonth?.asset_yield === null || adbMonth?.asset_yield === undefined
                ? EM_DASH
                : `${adbMonth.asset_yield.toFixed(2)}%`}
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" className="liability-metric-tile">
            <Text type="secondary">负债付息率（月日均）</Text>
            <div className="liability-metric-value">
              {adbMonth?.liability_cost === null || adbMonth?.liability_cost === undefined
                ? EM_DASH
                : `${adbMonth.liability_cost.toFixed(2)}%`}
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" className="liability-metric-tile">
            <Text type="secondary">当前 NIM（月日均）</Text>
            <div
              className={`liability-metric-value${nimNegative ? " liability-metric-value--down" : ""}`}
            >
              {nim === null || nim === undefined ? EM_DASH : `${nim.toFixed(2)}%`}
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small">
            <Text strong className="liability-stress-title">
              压力后 NIM（+50bps）
            </Text>
            <div
              className={`liability-metric-value${projectedNegative ? " liability-metric-value--down" : ""}`}
              style={{ marginTop: 8 }}
            >
              {projected === null ? EM_DASH : `${projected.toFixed(2)}%`}
            </div>
            {/* 有意对齐 DESIGN IB 语义色（涨绿跌红）：冲击下行固定 --ib-down，不再使用旧 A股红涨绿跌。 */}
            <div
              className={`liability-metric-delta ${
                nim === null || nim === undefined
                  ? "liability-metric-delta--muted"
                  : "liability-metric-delta--down"
              }`}
            >
              {nim === null || nim === undefined
                ? `Δ ${EM_DASH}`
                : "−50 bp（负债成本 +50bps，NIM 同幅下行）"}
            </div>
          </Card>
        </Col>
      </Row>
    </Card>
  );
}
