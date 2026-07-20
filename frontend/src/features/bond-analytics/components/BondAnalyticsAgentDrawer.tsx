import { lazy, Suspense } from "react";

import { Button as AntButton, Drawer as AntDrawer } from "antd";

import styles from "./BondAnalyticsViewContent.module.css";

const LazyAgentPanel = lazy(() =>
  import("../../agent/AgentPanel").then((module) => ({ default: module.AgentPanel })),
);

export type BondAnalyticsAgentDrawerProps = {
  open: boolean;
  reportDate: string;
  currentFilters: Record<string, unknown>;
  onClose: () => void;
};

/**
 * 债券分析页复核助手抽屉：整体懒加载，antd Drawer 与 AgentPanel 都不进入首屏启动链路。
 * page_context 契约与驾驶舱/股票分析页一致（AgentPanel 内部固定 readOnly）。
 */
export function BondAnalyticsAgentDrawer({
  open,
  reportDate,
  currentFilters,
  onClose,
}: BondAnalyticsAgentDrawerProps) {
  return (
    <AntDrawer
      placement="left"
      width={560}
      open={open}
      onClose={onClose}
      data-testid="bond-analysis-agent-drawer"
      title="复核助手"
      extra={
        <AntButton type="text" onClick={onClose} aria-label="关闭抽屉">
          关闭
        </AntButton>
      }
    >
      <div className={styles.agentDrawerBody}>
        {open ? (
          <Suspense fallback={null}>
            <LazyAgentPanel
              pageId="bond-analysis"
              reportDate={reportDate || null}
              currentFilters={currentFilters}
              contextNote="bond-analysis 债券分析工作台上下文"
            />
          </Suspense>
        ) : null}
      </div>
    </AntDrawer>
  );
}
