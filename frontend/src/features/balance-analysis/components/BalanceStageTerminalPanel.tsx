import type { ReactNode } from "react";

type BalanceStageTerminalPanelProps = {
  title: string;
  children: ReactNode;
  wide?: boolean;
};

/** 读面平卡：panel 平底 + 发丝描边 + 13px 面板题（首页平卡语言）。 */
export function BalanceStageTerminalPanel({
  title,
  children,
  wide = false,
}: BalanceStageTerminalPanelProps) {
  return (
    <article
      className={`balance-analysis-panel${wide ? " balance-analysis-panel--wide" : ""}`}
    >
      <h3 className="balance-analysis-panel__title">{title}</h3>
      {children}
    </article>
  );
}
