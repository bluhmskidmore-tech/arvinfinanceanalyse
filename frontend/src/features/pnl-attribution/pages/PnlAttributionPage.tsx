import { PnlAttributionView } from "../components/PnlAttributionView";

const pageStyle = {
  padding: "8px 4px 32px",
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
