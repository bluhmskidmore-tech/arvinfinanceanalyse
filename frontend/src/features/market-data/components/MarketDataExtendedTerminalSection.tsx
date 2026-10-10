import { Collapse } from "antd";
import type { ReactNode } from "react";

type MarketDataExtendedTerminalSectionProps = {
  sourcePendingCount: number;
  children: ReactNode;
};

// 区块头走眉标语言（muted 11px 眉标 + ink 标题 + muted 计数徽标）；
// 未接入明细清单只在体内摘要行出现一次（DESIGN §6 状态去重），展开提示交给 Collapse 箭头。
function extendedTerminalLabel(sourcePendingCount: number) {
  return (
    <span className="market-data-extended-terminal-label">
      <span className="market-data-extended-terminal-label__kicker">扩展终端</span>
      <strong>国债期货 / 现券成交 / 信用成交</strong>
      {sourcePendingCount > 0 ? (
        <span className="market-data-extended-terminal-label__count">未接入 {sourcePendingCount}</span>
      ) : null}
    </span>
  );
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
