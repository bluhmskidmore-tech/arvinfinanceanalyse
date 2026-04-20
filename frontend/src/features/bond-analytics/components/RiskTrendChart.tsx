import { Typography } from "antd";
import { SectionCard } from "../../../components/SectionCard";
import { BORDER, panelStyle } from "./bondAnalyticsCockpitTokens";

const { Paragraph } = Typography;

export function RiskTrendChart() {
  return (
    <SectionCard
      title="风险趋势（近12周）"
      style={{ ...panelStyle("#ffffff"), border: `1px solid ${BORDER}` }}
    >
      <div
        role="status"
        aria-live="polite"
        style={{
          minHeight: 220,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "16px 12px",
          textAlign: "center",
          color: "#5c6b82",
          fontSize: 13,
          lineHeight: 1.65,
        }}
      >
        周频净敞口、负债比与对手方集中度序列暂无可用接口；上方 KPI 与明细区仍走真实报表数据。
      </div>
      <Paragraph type="secondary" style={{ marginTop: 4, marginBottom: 0, fontSize: 12 }}>
        接口就绪后可在此挂载 ECharts 序列，不再使用前端合成曲线。
      </Paragraph>
    </SectionCard>
  );
}

export default RiskTrendChart;
