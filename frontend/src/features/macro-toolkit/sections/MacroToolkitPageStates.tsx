import { ArrowDownOutlined, ReloadOutlined } from "@ant-design/icons";
import { Alert, Button } from "antd";

import { PageSectionLead, PageStateSurface } from "../../../components/page/PagePrimitives";
import { MT_SHELL_TOPBAR_RIGHT } from "../lib/macroToolkitPageChrome";
import { MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE } from "../lib/macroToolkitPageModel";
import type { MacroToolkitDeferredContentStage } from "../lib/macroToolkitPageModel";
import {
  MacroToolkitContractBoundary,
  MacroToolkitReadScopeBlocker,
} from "./MacroToolkitPrimitives";

type RetryableQuery = {
  refetch: () => Promise<unknown>;
  isFetching: boolean;
};

export function MacroToolkitPageErrorState({
  queryErrorText,
  analysisQuery,
  scriptsQuery,
  strategyQuery,
  hasReadScopeBlocker,
  failedReadMessages,
}: {
  queryErrorText: string;
  analysisQuery: RetryableQuery;
  scriptsQuery: RetryableQuery;
  strategyQuery: RetryableQuery;
  hasReadScopeBlocker: boolean;
  failedReadMessages: string[];
}) {
  return (
      <PageStateSurface
        variant="error"
        testId="macro-toolkit-error-state"
        className="macro-toolkit-error-state"
        title="宏观工具暂不可用"
        description={queryErrorText || "后端宏观模块没有返回可展示数据。"}
        actions={
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              void analysisQuery.refetch();
              void scriptsQuery.refetch();
              void strategyQuery.refetch();
            }}
            loading={analysisQuery.isFetching || scriptsQuery.isFetching || strategyQuery.isFetching}
          >
            重试读取
          </Button>
        }
      >
        <MacroToolkitContractBoundary />
        {hasReadScopeBlocker ? <MacroToolkitReadScopeBlocker /> : null}
        <div className="macro-toolkit-error-sources" aria-label="宏观工具失败来源">
          <span>失败来源</span>
          {failedReadMessages.length ? (
            failedReadMessages.map((message, index) => (
              <small key={`${message}-${index}`}>{message}</small>
            ))
          ) : (
            <small>后端宏观模块没有返回可展示数据。</small>
          )}
        </div>
      </PageStateSurface>
  );
}

export function MacroToolkitInitialAnalysisLoading() {
  return (
        <>
          <div data-testid="macro-toolkit-initial-analysis-loading">
            <Alert
              type="info"
              showIcon
              message="核心分析加载中"
              description="页面口径边界已就绪；核心信号和脚本注册表会在后端返回后自动补上。"
            />
          </div>
          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="信号"
              title="核心信号"
              description="等待后端宏观分析结果返回。"
            />
            <div className="macro-toolkit-empty-output">核心分析加载中，暂不显示占位结论。</div>
          </section>
          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="风险"
              title="市场踩踏风险"
              description="等待 A 股宽度、跌停、成交与回落压力判断返回。"
            />
            <div className="macro-toolkit-empty-output">市场踩踏风险加载中，暂不推导风险等级。</div>
          </section>
        </>
  );
}

export function MacroToolkitHeaderControls({
  clearFullAnalysisCache,
  analysisQuery,
  scriptsQuery,
  strategyQuery,
  isMacroRefreshing,
  deferredContentStage,
  receiptTechnicalDetailsExpanded,
  revealAllDeferredContent,
}: {
  clearFullAnalysisCache: (options?: { preserveCrisisGapRepairFeedback?: boolean }) => Promise<void>;
  analysisQuery: RetryableQuery;
  scriptsQuery: RetryableQuery;
  strategyQuery: RetryableQuery;
  isMacroRefreshing: boolean;
  deferredContentStage: MacroToolkitDeferredContentStage;
  receiptTechnicalDetailsExpanded: boolean;
  revealAllDeferredContent: () => void;
}) {
  return (
        <div className={`${MT_SHELL_TOPBAR_RIGHT} macro-toolkit-page__header-controls`}>
          <Button
            className="macro-toolkit-page__dh-topbar-btn"
            icon={<ReloadOutlined />}
            onClick={() => {
              void clearFullAnalysisCache();
              void analysisQuery.refetch();
              void scriptsQuery.refetch();
              void strategyQuery.refetch();
            }}
            loading={isMacroRefreshing}
          >
            刷新结果
          </Button>
          <Button
            className="macro-toolkit-page__dh-topbar-btn"
            icon={<ReloadOutlined />}
            onClick={() => void scriptsQuery.refetch()}
            loading={scriptsQuery.isFetching}
          >
            刷新注册表
          </Button>
          <Button
            className="macro-toolkit-page__dh-topbar-btn"
            data-testid="macro-toolkit-expand-all-content"
            icon={<ArrowDownOutlined />}
            aria-label="展开全部内容以便页内搜索或打印"
            disabled={
              deferredContentStage >= MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE &&
              receiptTechnicalDetailsExpanded
            }
            onClick={revealAllDeferredContent}
          >
            {deferredContentStage >= MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE &&
            receiptTechnicalDetailsExpanded
              ? "已展开全部"
              : "展开全部"}
          </Button>
        </div>
  );
}
