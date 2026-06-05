import { PnlAttributionView } from "../components/PnlAttributionView";
import { designTokens } from "../../../theme/designSystem";

const pageStyle = {
  padding: `${designTokens.space[2]}px ${designTokens.space[1]}px ${designTokens.space[7]}px`,
  maxWidth: 1280,
  margin: "0 auto",
} as const;

/**
 * 损益归因工作台：规模/利率、TPL–市场、损益构成、高级归因与 Campisi 四效应。
 */
export default function PnlAttributionPage() {
  return (
    <div style={pageStyle}>
      <PnlAttributionView />
    </div>
  );
}
