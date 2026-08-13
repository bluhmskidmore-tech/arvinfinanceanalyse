import { lazy, Suspense } from "react";

import { Button as AntButton, Drawer as AntDrawer } from "antd";

import { isAgentFrontendEnabled } from "../../../app/navigation";
import styles from "./riskOverview.module.css";

const LazyAgentPanel = lazy(() =>
  import("../../agent/AgentPanel").then((module) => ({ default: module.AgentPanel })),
);

export type RiskOverviewAgentDrawerProps = {
  open: boolean;
  reportDate: string;
  currentFilters: Record<string, unknown>;
  onClose: () => void;
};

/**
 * 风险概览页复核助手抽屉：整体懒加载，antd Drawer 与 AgentPanel 都不进入首屏启动链路。
 * page_context 契约与驾驶舱/债券分析页一致（AgentPanel 内部固定 readOnly）。
 */
export function RiskOverviewAgentDrawer({
  open,
  reportDate,
  currentFilters,
  onClose,
}: RiskOverviewAgentDrawerProps) {
  if (!isAgentFrontendEnabled()) {
    return null;
  }

  return (
    <AntDrawer
      placement="left"
      width={560}
      open={open}
      onClose={onClose}
      data-testid="risk-overview-agent-drawer"
      title="复核助手"
      extra={
        <AntButton type="text" onClick={onClose} aria-label="关闭抽屉">
          关闭
        </AntButton>
      }
    >
      <div className={`theme-dh-api ${styles.roAgentDrawerBody}`}>
        {open ? (
          <Suspense fallback={null}>
            <LazyAgentPanel
              pageId="risk-overview"
              reportDate={reportDate || null}
              currentFilters={currentFilters}
              contextNote="risk-overview 利率风险总览观察上下文"
            />
          </Suspense>
        ) : null}
      </div>
    </AntDrawer>
  );
}
