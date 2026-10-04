import { lazy, Suspense } from "react";

import { Button as AntButton, Drawer as AntDrawer } from "antd";

import { isAgentFrontendEnabled } from "../../../app/navigation";
import "./PnlAttributionView.css";

const LazyAgentPanel = lazy(() =>
  import("../../agent/AgentPanel").then((module) => ({ default: module.AgentPanel })),
);

export type PnlAttributionAgentDrawerProps = {
  open: boolean;
  reportDate: string | null;
  currentFilters: Record<string, unknown>;
  onClose: () => void;
};

/**
 * 损益归因页复核助手抽屉：整体懒加载，AgentPanel 保持共享只读语义。
 * 双口径日期与页签状态仅作为 page_context 传递，不参与前端计算。
 */
export function PnlAttributionAgentDrawer({
  open,
  reportDate,
  currentFilters,
  onClose,
}: PnlAttributionAgentDrawerProps) {
  if (!isAgentFrontendEnabled()) {
    return null;
  }

  return (
    <AntDrawer
      placement="left"
      width={560}
      open={open}
      onClose={onClose}
      rootClassName="theme-dh-api pnl-attribution-agent-drawer"
      data-testid="pnl-attribution-agent-drawer"
      data-moss-theme-scope="pnl-attribution"
      title={
        <div className="pnl-attribution-agent-drawer__title-copy">
          <div className="pnl-attribution-agent-drawer__eyebrow">只读计划 · 人工签字</div>
          <div className="pnl-attribution-agent-drawer__title">损益复核助手</div>
        </div>
      }
      extra={
        <AntButton type="text" onClick={onClose} aria-label="关闭抽屉">
          关闭
        </AntButton>
      }
    >
      <div
        className="theme-dh-api pnl-attribution-agent-drawer-body"
        data-moss-theme-scope="agent"
      >
        {open ? (
          <Suspense fallback={null}>
            <LazyAgentPanel
              pageId="pnl-attribution"
              reportDate={reportDate}
              currentFilters={currentFilters}
              contextNote="pnl-attribution 双口径损益归因观察上下文；产品分类经营口径与正式 FI / Campisi 口径不得跨口径汇总或闭合；Agent 输出保持 formal_use_allowed=false，仅供人工复核。"
              defaultQuestion="/pnl-review"
            />
          </Suspense>
        ) : null}
      </div>
    </AntDrawer>
  );
}
