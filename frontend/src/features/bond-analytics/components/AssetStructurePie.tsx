import { Typography } from "antd";
import { SectionCard } from "../../../components/SectionCard";
import { BORDER, panelStyle } from "./bondAnalyticsCockpitTokens";

const { Paragraph } = Typography;

/** 独立饼图占位：组合资产结构请使用驾驶舱「债券资产结构」或 KRD 明细中的真实占比图。 */
export function AssetStructurePie() {
  return (
    <SectionCard
      title="债券资产结构"
      style={{ ...panelStyle("#ffffff"), border: `1px solid ${BORDER}` }}
    >
      <div
        role="status"
        aria-live="polite"
        style={{
          minHeight: 240,
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
        本卡片未接独立接口；请在概览驾驶舱「债券资产结构」或「曲线风险」明细查看按资产类的真实权重与市值。
      </div>
      <Paragraph type="secondary" style={{ marginTop: 4, marginBottom: 0, fontSize: 12 }}>
        已移除静态示意切片，避免与真实持仓口径混淆。
      </Paragraph>
    </SectionCard>
  );
}

export default AssetStructurePie;
