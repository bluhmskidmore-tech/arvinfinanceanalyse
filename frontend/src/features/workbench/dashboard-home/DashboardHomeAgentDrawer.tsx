import { lazy, Suspense } from "react";

import { Button as AntButton, Drawer as AntDrawer } from "antd";

import { isAgentFrontendEnabled } from "../../../mocks/navigation";
import styles from "./dashboardHomeShell.module.css";

const LazyAgentPanel = lazy(() =>
  import("../../agent/AgentPanel").then((module) => ({ default: module.AgentPanel })),
);

export type DashboardHomeAgentDrawerProps = {
  open: boolean;
  reportDate: string;
  currentFilters: Record<string, unknown>;
  onClose: () => void;
};

/**
 * 驾驶舱复核助手抽屉：整体懒加载，antd 与 AgentPanel 都不进入首屏启动链路。
 * page_context 契约与股票分析页一致（AgentPanel 内部固定 readOnly）。
 */
export function DashboardHomeAgentDrawer({
  open,
  reportDate,
  currentFilters,
  onClose,
}: DashboardHomeAgentDrawerProps) {
  if (!isAgentFrontendEnabled()) {
    return null;
  }

  return (
    <AntDrawer
      placement="left"
      width={560}
      open={open}
      onClose={onClose}
      data-testid="dashboard-home-agent-drawer"
      title="复核助手"
      extra={
        <AntButton type="text" onClick={onClose} aria-label="关闭抽屉">
          关闭
        </AntButton>
      }
    >
      <div className={`theme-dh-api ${styles.dhAgentDrawerBody}`}>
        {open ? (
          <Suspense fallback={null}>
            <LazyAgentPanel
              pageId="dashboard"
              reportDate={reportDate || null}
              currentFilters={currentFilters}
              contextNote="dashboard-home 组合经营日报观察上下文"
            />
          </Suspense>
        ) : null}
      </div>
    </AntDrawer>
  );
}
