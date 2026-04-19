import { Card, Col, Row, Tag, Typography } from "antd";

import type { LiabilityYieldKpi } from "../../../api/contracts";
import { dailyNimStressFromKpi } from "../utils/nimStress";

const { Text } = Typography;

/** 涓浗閰嶈壊锛氱孩=涓婃定锛岀豢=涓嬭穼锛堢敤浜?NIM 鍙樺姩鏂瑰悜锛夈€?*/
function deltaColor(deltaBp: number | null): string {
  if (deltaBp === null || !Number.isFinite(deltaBp)) {
    return "rgba(0,0,0,0.45)";
  }
  if (deltaBp > 0) {
    return "#cf1322";
  }
  if (deltaBp < 0) {
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
  const deltaBpRaw = stress.deltaBp?.raw ?? null;
  const bpText = stress.deltaBp?.display ?? "鈥?";

  return (
    <Card size="small" title="鍘嬪姏娴嬭瘯锛歂IM 鏁忔劅鎬э紙+50bps锛?>">
      <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 12 }}>
        鍙ｅ緞锛氳祫浜ф敹鐩婄巼 鈭?閲戣瀺甯傚満鍚屼笟璐熷€烘垚鏈紙鍏ㄥ彛寰?TYWL + 鍙戣鍚屼笟瀛樺崟锛夛紱鍐插嚮涓鸿礋鍊烘垚鏈?+50bps銆?
      </Text>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" styles={{ body: { background: "#fafafa" } }}>
            <Text type="secondary">璧勪骇鏀剁泭鐜?</Text>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{stress.ay?.display ?? "鈥?"}</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" styles={{ body: { background: "#fafafa" } }}>
            <Text type="secondary">閲戣瀺甯傚満鍚屼笟璐熷€烘垚鏈?</Text>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{stress.mlc?.display ?? "鈥?"}</div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              锛堝鍊肩◣鍓嶏級
            </Text>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" styles={{ body: { background: "#fafafa" } }}>
            <Text type="secondary">褰撳墠 NIM</Text>
            <div
              style={{
                fontSize: 22,
                fontWeight: 700,
                color:
                  stress.nim?.raw !== null && stress.nim?.raw !== undefined && stress.nim.raw < 0
                    ? "#cf1322"
                    : "rgba(0,0,0,0.88)",
              }}
            >
              {stress.nim?.display ?? "鈥?"}
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <Text strong style={{ color: "#531dab" }}>
                  鍘嬪姏鍚?NIM锛?50bps锛?
                </Text>
                {stress.isCritical ? (
                  <Tag color="red" style={{ marginLeft: 8 }}>
                    NIM 棰勮
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
                  stress.projected?.raw !== null &&
                  stress.projected?.raw !== undefined &&
                  stress.projected.raw < 0
                    ? "#cf1322"
                    : "rgba(0,0,0,0.88)",
              }}
            >
              {stress.projected?.display ?? "鈥?"}
            </div>
            <div style={{ marginTop: 8, fontWeight: 600, color: deltaColor(deltaBpRaw) }}>螖 {bpText}</div>
          </Card>
        </Col>
      </Row>
    </Card>
  );
}
