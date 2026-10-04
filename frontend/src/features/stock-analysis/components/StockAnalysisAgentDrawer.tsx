import { lazy, Suspense } from "react";
import { Button as AntButton, Drawer as AntDrawer } from "antd";

import type { AgentPageContext } from "../../../api/contracts";
import { TextSkeleton } from "../../../components/Skeletons";
import { stockAnalysisPageCssVars } from "../lib/stockAnalysisTokens";

const LazyAgentPanel = lazy(() =>
  import("../../agent/AgentPanel").then((module) => ({ default: module.AgentPanel })),
);

type StockAnalysisAgentDrawerProps = {
  open: boolean;
  context: AgentPageContext;
  onClose: () => void;
};

export function StockAnalysisAgentDrawer({
  open,
  context,
  onClose,
}: StockAnalysisAgentDrawerProps) {
  return (
    <AntDrawer
      placement="left"
      width={560}
      open={open}
      onClose={onClose}
      className="stock-analysis-page__agent-drawer"
      data-testid="stock-analysis-agent-drawer"
      data-moss-theme-scope="stock-analysis"
      title="复核助手"
      extra={
        <AntButton type="text" onClick={onClose} aria-label="关闭抽屉">
          关闭
        </AntButton>
      }
    >
      <div
        style={stockAnalysisPageCssVars}
        className="theme-dh-api stock-analysis-page__agent-drawer-body"
        data-moss-theme-scope="stock-analysis"
      >
        {open ? (
          <Suspense fallback={<TextSkeleton className="w-full" />}>
            <LazyAgentPanel
              pageId="stock-analysis"
              currentFilters={context.current_filters}
              defaultFilters={{ research_domain: "stock" }}
              selectedRows={context.selected_rows}
              contextNote={context.context_note ?? null}
            />
          </Suspense>
        ) : null}
      </div>
    </AntDrawer>
  );
}
