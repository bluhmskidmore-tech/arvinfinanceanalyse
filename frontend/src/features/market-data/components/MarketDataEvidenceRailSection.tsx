import type { ReactNode } from "react";

type MarketDataEvidenceRailSectionProps = {
  children: ReactNode;
};

export function MarketDataEvidenceRailSection({ children }: MarketDataEvidenceRailSectionProps) {
  return (
    <section className="market-data-section-block market-data-evidence-section" data-testid="market-data-evidence-section">
      <div className="market-data-evidence-section-head" data-testid="market-data-evidence-section-head">
        <span className="market-data-evidence-section-kicker">数据来源</span>
        <strong className="market-data-evidence-section-title">口径与链路摘要</strong>
        <span className="market-data-evidence-section-hint">正式 / 分析 / 降级 / 待补齐状态，首屏只读</span>
      </div>
      {children}
    </section>
  );
}
