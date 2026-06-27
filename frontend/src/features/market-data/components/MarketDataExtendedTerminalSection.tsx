import { Collapse } from "antd";
import type { ReactNode } from "react";

type MarketDataExtendedTerminalSectionProps = {
  sourcePendingCount: number;
  children: ReactNode;
};

function extendedTerminalLabel(sourcePendingCount: number) {
  const pendingHint =
    sourcePendingCount > 0 ? ` · ${sourcePendingCount} 项未接入` : "";
  return `未接入数据源（期货·成交）${pendingHint} · 点击展开`;
}

export function MarketDataExtendedTerminalSection({
  sourcePendingCount,
  children,
}: MarketDataExtendedTerminalSectionProps) {
  return (
    <section
      className="market-data-section-block market-data-extended-terminal-section"
      data-testid="market-data-extended-terminal-section"
    >
      <Collapse
        className="market-data-extended-terminal-collapse"
        data-testid="market-data-extended-terminal-collapse"
        bordered={false}
        defaultActiveKey={[]}
        items={[
          {
            key: "extended",
            label: extendedTerminalLabel(sourcePendingCount),
            forceRender: true,
            children: (
              <div className="market-data-extended-terminal-body">{children}</div>
            ),
          },
        ]}
      />
    </section>
  );
}
