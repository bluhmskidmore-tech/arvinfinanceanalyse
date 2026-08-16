import { Typography } from "antd";
import { EvidencePanel } from "../../../components/page/PagePrimitives";
import { designTokens } from "../../../theme/designSystem";

const { Paragraph } = Typography;

const dt = designTokens;

export function RiskTrendChart() {
  return (
    <EvidencePanel
      heading="风险趋势（近12周）"
      style={{
        border: "1px solid var(--ib-hairline)",
        borderRadius: "var(--dh-api-radius, 6px)",
        background: "var(--ib-surface)",
        boxShadow: "none",
      }}
    >
      {/* 空态收缩（DESIGN §5）：无数据分组收缩到消息框自身高度，居中一句话说明。 */}
      <div
        role="status"
        aria-live="polite"
        style={{
          minHeight: 88,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: `${dt.space[3]}px ${dt.space[3]}px`,
          textAlign: "center",
          color: "var(--ib-ink-muted)",
          fontSize: dt.fontSize[12],
          lineHeight: dt.lineHeight.relaxed,
        }}
      >
        周频净敞口、负债比与对手方集中度序列暂无可用接口；上方 KPI 与明细区仍走真实报表数据。
      </div>
      <Paragraph
        type="secondary"
        style={{ marginTop: 0, marginBottom: 0, fontSize: dt.fontSize[11], textAlign: "center" }}
      >
        接口就绪后可在此挂载 ECharts 序列，不再使用前端合成曲线。
      </Paragraph>
    </EvidencePanel>
  );
}

export default RiskTrendChart;
