import { Typography } from "antd";
import { SectionCard } from "../../../components/SectionCard";
import { designTokens } from "../../../theme/designSystem";
import { BORDER, panelStyle } from "./bondAnalyticsCockpitTokens";

const { Paragraph } = Typography;

const dt = designTokens;

export function RiskTrendChart() {
  return (
    <SectionCard
      title="风险趋势（近12周）"
      style={{ ...panelStyle(dt.color.neutral[50]), border: `1px solid ${BORDER}` }}
    >
      <div
        role="status"
        aria-live="polite"
        style={{
          minHeight: 220,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: `${dt.space[4]}px ${dt.space[3]}px`,
          textAlign: "center",
          color: dt.color.neutral[600],
          fontSize: dt.fontSize[13],
          lineHeight: dt.lineHeight.relaxed,
        }}
      >
        周频净敞口、负债比与对手方集中度序列暂无可用接口；上方 KPI 与明细区仍走真实报表数据。
      </div>
      <Paragraph type="secondary" style={{ marginTop: dt.space[1], marginBottom: 0, fontSize: dt.fontSize[12] }}>
        接口就绪后可在此挂载 ECharts 序列，不再使用前端合成曲线。
      </Paragraph>
    </SectionCard>
  );
}

export default RiskTrendChart;
