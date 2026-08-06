import { Card, Col, Row, Typography } from "antd";

import type { LiabilityYieldKpi } from "../../../api/liabilityAdbContracts";
import { EM_DASH } from "../../../utils/format";
import { dailyNimStressFromKpi } from "../utils/nimStress";

const { Text } = Typography;

/** 有意对齐 DESIGN IB 语义色（涨绿跌红），不再使用旧 A股红涨绿跌。 */
function deltaTone(deltaBp: number | null): "up" | "down" | "muted" | "ink" {
  if (deltaBp === null || !Number.isFinite(deltaBp)) {
    return "muted";
  }
  if (deltaBp > 0) {
    return "up";
  }
  if (deltaBp < 0) {
    return "down";
  }
  return "ink";
}

export function LiabilityNimStressPanel({
  yieldKpi,
}: {
  yieldKpi: LiabilityYieldKpi | null;
}) {
  const stress = dailyNimStressFromKpi(yieldKpi);
  const deltaBpRaw = stress.deltaBp?.raw ?? null;
  const bpText = stress.deltaBp?.display ?? EM_DASH;
  const nimNegative =
    stress.nim?.raw !== null && stress.nim?.raw !== undefined && stress.nim.raw < 0;
  const projectedNegative =
    stress.projected?.raw !== null &&
    stress.projected?.raw !== undefined &&
    stress.projected.raw < 0;

  return (
    <Card size="small" title="压力测试：NIM 敏感性（+50bps）">
      <Text type="secondary" className="liability-panel-caption">
        口径：资产收益率减金融市场同业负债成本（全口径同业往来 + 发行同业存单）；冲击为负债成本 +50bps。
      </Text>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" className="liability-metric-tile">
            <Text type="secondary">资产收益率</Text>
            <div className="liability-metric-value">{stress.ay?.display ?? EM_DASH}</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" className="liability-metric-tile">
            <Text type="secondary">金融市场同业负债成本</Text>
            <div className="liability-metric-value">{stress.mlc?.display ?? EM_DASH}</div>
            <Text type="secondary" className="liability-panel-caption--tight">
              （增值税前）
            </Text>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" className="liability-metric-tile">
            <Text type="secondary">当前 NIM</Text>
            <div
              className={`liability-metric-value${nimNegative ? " liability-metric-value--down" : ""}`}
            >
              {stress.nim?.display ?? EM_DASH}
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small">
            <div className="liability-stress-head">
              <div>
                <Text strong className="liability-stress-title">
                  压力后 NIM（+50bps）
                </Text>
                {stress.isCritical ? (
                  <span className="liability-status-pill liability-status-pill--inline">NIM 预警</span>
                ) : null}
              </div>
            </div>
            <div
              className={`liability-metric-value${projectedNegative ? " liability-metric-value--down" : ""}`}
              style={{ marginTop: 8 }}
            >
              {stress.projected?.display ?? EM_DASH}
            </div>
            <div className={`liability-metric-delta liability-metric-delta--${deltaTone(deltaBpRaw)}`}>
              变化 {bpText}
            </div>
          </Card>
        </Col>
      </Row>
    </Card>
  );
}
