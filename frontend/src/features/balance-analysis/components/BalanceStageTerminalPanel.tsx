import type { ReactNode } from "react";

import dhStyles from "../../workbench/dashboard-home/dashboardHome.module.css";

type BalanceStageTerminalPanelProps = {
  title: string;
  children: ReactNode;
  wide?: boolean;
};

export function BalanceStageTerminalPanel({
  title,
  children,
  wide = false,
}: BalanceStageTerminalPanelProps) {
  return (
    <article
      className={`${dhStyles.dhCard} ${dhStyles.dhTerminalPanel}${wide ? ` ${dhStyles.dhTerminalPanelWide}` : ""}`}
    >
      <div className={dhStyles.dhTerminalPanelHead}>
        <h3>{title}</h3>
      </div>
      {children}
    </article>
  );
}
