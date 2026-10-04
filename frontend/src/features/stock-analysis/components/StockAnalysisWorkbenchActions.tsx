import { ClockCircleOutlined, ReloadOutlined, SafetyCertificateOutlined, SearchOutlined } from "@ant-design/icons";
import { Button as AntButton } from "antd";

import { isAgentFrontendEnabled } from "../../../app/navigation";
import { formatGeneratedAtLabel } from "../lib/stockAnalysisPageCopy";
import { SA_SHELL_NUM } from "../lib/stockAnalysisPageChrome";
import {
  RESEARCH_DESK_POOL_TABS,
  type ResearchDeskPoolTab,
} from "../lib/stockAnalysisResearchDeskModel";

type ToolbarTone = "negative" | "neutral" | "positive" | "warning";

type StockAnalysisWorkbenchActionsProps = {
  pickerDisplay: string | null;
  queueSearchText: string;
  marketFilter?: "all" | "SH" | "SZ";
  onMarketFilterChange?: (value: "all" | "SH" | "SZ") => void;
  sectorOptions?: Array<[string, string]>;
  selectedSectorCode?: string | null;
  onSelectSector?: (sectorCode: string | null) => void;
  signalOptions?: Array<[string, string]>;
  signalFilter?: string;
  onSignalFilterChange?: (value: string) => void;
  poolTab?: ResearchDeskPoolTab;
  onPoolTabChange?: (value: ResearchDeskPoolTab) => void;
  /**
   * 以下四个状态文案只用于工具栏内的 aria-live 播报（屏幕阅读器），
   * 可见的状态条由页面级 DataStatusStrip 统一渲染，这里不再重复绘制。
   */
  queueStatusLabel?: string;
  gateStatusLabel?: string;
  loopStatusLabel?: string;
  formalUseLabel?: string;
  agentDrawerOpen: boolean;
  agentEnabled?: boolean;
  generatedAt?: string | null;
  onAsOfOverrideChange: (value: string | null) => void;
  onQueueSearchTextChange: (value: string) => void;
  onOpenAgentDrawer: () => void;
  onRefresh: () => void;
  /** 轻量刷新（仅重新读取数据）；未提供时回退到 onRefresh。 */
  onRefetch?: () => void;
  isRefreshing?: boolean;
  refreshStatusMessage?: string | null;
  refreshStatusTone?: ToolbarTone;
};

export function StockAnalysisWorkbenchActions({
  pickerDisplay,
  queueSearchText,
  marketFilter = "all",
  onMarketFilterChange,
  sectorOptions = [],
  selectedSectorCode = null,
  onSelectSector,
  signalOptions = [],
  signalFilter = "",
  onSignalFilterChange,
  poolTab = "queue",
  onPoolTabChange,
  queueStatusLabel,
  gateStatusLabel,
  loopStatusLabel,
  formalUseLabel,
  agentDrawerOpen,
  agentEnabled = true,
  generatedAt,
  onAsOfOverrideChange,
  onQueueSearchTextChange,
  onOpenAgentDrawer,
  onRefresh,
  onRefetch,
  isRefreshing = false,
  refreshStatusMessage,
  refreshStatusTone = "neutral",
}: StockAnalysisWorkbenchActionsProps) {
  return (
    <div className="stock-analysis-page__workbench-actions">
      <span className="stock-analysis-page__visually-hidden" role="status" aria-live="polite">
        {[queueStatusLabel, gateStatusLabel, loopStatusLabel, formalUseLabel].filter(Boolean).join(" · ")}
      </span>
      <div className="stock-analysis-page__workbench-actions-row stock-analysis-page__workbench-actions-row--context">
        <label className="stock-analysis-page__workbench-field" aria-label="选择观察日">
          <span className="stock-analysis-page__workbench-field-label">观察日</span>
          <input
            type="date"
            className="stock-analysis-page__dh-date-picker border-default-200 rounded-md px-3 py-2 text-sm"
            data-testid="stock-analysis-as-of-picker"
            value={pickerDisplay ?? ""}
            onChange={(e) => {
              onAsOfOverrideChange(e.target.value || null);
            }}
          />
        </label>
        <label className="stock-analysis-page__queue-search" aria-label="检索股票、行业、信号">
          <SearchOutlined aria-hidden="true" />
          <input
            data-testid="stock-analysis-queue-search"
            value={queueSearchText}
            placeholder="全球 / 股票 / 行业 / 信号 搜索…"
            onChange={(event) => {
              onQueueSearchTextChange(event.target.value);
            }}
          />
        </label>
        <label className="stock-analysis-page__workbench-select">
          <span className="stock-analysis-page__visually-hidden">市场筛选</span>
          <select
            aria-label="市场筛选"
            value={marketFilter}
            onChange={(event) => onMarketFilterChange?.(event.target.value as "all" | "SH" | "SZ")}
          >
            <option value="all">全部市场</option>
            <option value="SH">沪市</option>
            <option value="SZ">深市</option>
          </select>
        </label>
        <label className="stock-analysis-page__workbench-select">
          <span className="stock-analysis-page__visually-hidden">行业筛选</span>
          <select
            aria-label="行业筛选"
            value={selectedSectorCode ?? ""}
            onChange={(event) => onSelectSector?.(event.target.value || null)}
          >
            <option value="">申万一级行业</option>
            {sectorOptions.map(([code, label]) => (
              <option key={code} value={code}>{label}</option>
            ))}
          </select>
        </label>
        <label className="stock-analysis-page__workbench-select">
          <span className="stock-analysis-page__visually-hidden">信号类型</span>
          <select
            aria-label="信号类型"
            value={signalFilter}
            onChange={(event) => onSignalFilterChange?.(event.target.value)}
          >
            <option value="">信号类型</option>
            {signalOptions.map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
        </label>
        <label className="stock-analysis-page__workbench-select stock-analysis-page__workbench-select--view">
          <span className="stock-analysis-page__visually-hidden">研究视图</span>
          <select
            aria-label="研究视图"
            value={poolTab}
            onChange={(event) => onPoolTabChange?.(event.target.value as ResearchDeskPoolTab)}
          >
            {RESEARCH_DESK_POOL_TABS.map(([tab, label]) => (
              <option key={tab} value={tab}>
                我的视图：{label}
              </option>
            ))}
          </select>
        </label>
        <div className="stock-analysis-page__workbench-ops-cluster">
          {isAgentFrontendEnabled() && agentEnabled ? (
            <AntButton
              type="text"
              className="stock-analysis-page__agent-entry stock-analysis-page__dh-topbar-btn stock-analysis-page__agent-entry--quiet"
              data-testid="stock-analysis-agent-open"
              icon={<SafetyCertificateOutlined />}
              onClick={onOpenAgentDrawer}
              aria-expanded={agentDrawerOpen}
            >
              复核助手
            </AntButton>
          ) : null}
          <AntButton
            data-testid="stock-analysis-refetch"
            className="stock-analysis-page__dh-topbar-btn stock-analysis-page__agent-entry--quiet"
            icon={<ReloadOutlined />}
            onClick={() => (onRefetch ?? onRefresh)()}
            aria-label="刷新数据"
          >
            刷新
          </AntButton>
          <AntButton
            data-testid="stock-analysis-refresh"
            className="stock-analysis-page__dh-topbar-btn stock-analysis-page__dh-topbar-btn--primary"
            icon={<ReloadOutlined />}
            loading={isRefreshing}
            disabled={isRefreshing}
            onClick={onRefresh}
            aria-label="重新计算选股与门禁并重新读取观察队列"
          >
            {isRefreshing ? "重选标的中" : "重选标的"}
          </AntButton>
        </div>
      </div>
      <div className="stock-analysis-page__workbench-actions-row stock-analysis-page__workbench-actions-row--ops">
        {refreshStatusMessage ? (
          <span
            className="stock-analysis-page__refresh-feedback"
            data-testid="stock-analysis-refresh-feedback"
            data-tone={refreshStatusTone}
            role="status"
          >
            {refreshStatusMessage}
          </span>
        ) : null}
        {generatedAt ? (
          <span
            className={`text-default-500 ${SA_SHELL_NUM} stock-analysis-page__generated-at stock-analysis-page__visually-hidden`}
            title={generatedAt}
          >
            <ClockCircleOutlined /> {formatGeneratedAtLabel(generatedAt)}
          </span>
        ) : null}
      </div>
    </div>
  );
}
