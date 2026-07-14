import type { Dayjs } from "dayjs";
import { ClockCircleOutlined, ReloadOutlined, SafetyCertificateOutlined, SearchOutlined } from "@ant-design/icons";
import { Button as AntButton } from "antd";

import { formatGeneratedAtLabel } from "../lib/stockAnalysisPageCopy";
import { SA_SHELL_NUM } from "../lib/stockAnalysisPageChrome";

type ToolbarTone = "negative" | "neutral" | "positive" | "warning";

type StockAnalysisWorkbenchActionsProps = {
  pickerDisplay: Dayjs | null;
  queueSearchText: string;
  dataStatusLabel: string;
  dataStatusTone: ToolbarTone;
  gateStatusLabel: string;
  gateStatusTone: ToolbarTone;
  loopStatusLabel: string;
  loopStatusTone: ToolbarTone;
  formalUseAllowed: boolean;
  routeLabel: string;
  agentDrawerOpen: boolean;
  generatedAt?: string | null;
  onAsOfOverrideChange: (value: string | null) => void;
  onQueueSearchTextChange: (value: string) => void;
  onOpenAgentDrawer: () => void;
  onRefresh: () => void;
  isRefreshing?: boolean;
  refreshStatusMessage?: string | null;
  refreshStatusTone?: ToolbarTone;
};

export function StockAnalysisWorkbenchActions({
  pickerDisplay,
  queueSearchText,
  dataStatusLabel,
  dataStatusTone,
  gateStatusLabel,
  gateStatusTone,
  loopStatusLabel,
  loopStatusTone,
  formalUseAllowed,
  routeLabel,
  agentDrawerOpen,
  generatedAt,
  onAsOfOverrideChange,
  onQueueSearchTextChange,
  onOpenAgentDrawer,
  onRefresh,
  isRefreshing = false,
  refreshStatusMessage,
  refreshStatusTone = "neutral",
}: StockAnalysisWorkbenchActionsProps) {
  return (
    <div className="stock-analysis-page__workbench-actions">
      <input
        type="date"
        aria-label="as-of-date-picker"
        className="stock-analysis-page__dh-date-picker border-default-200 rounded-md px-3 py-2 text-sm"
        data-testid="stock-analysis-as-of-picker"
        value={pickerDisplay?.format("YYYY-MM-DD") || ""}
        onChange={(e) => {
          onAsOfOverrideChange(e.target.value || null);
        }}
      />
      <label className="stock-analysis-page__queue-search" aria-label="检索股票、行业、信号">
        <SearchOutlined aria-hidden="true" />
        <input
          data-testid="stock-analysis-queue-search"
          value={queueSearchText}
          placeholder="检索股票、行业、信号"
          onChange={(event) => {
            onQueueSearchTextChange(event.target.value);
          }}
        />
      </label>
      <div className="stock-analysis-page__toolbar-status-row" aria-label="复核状态">
        <span
          className="stock-analysis-page__toolbar-status-dot"
          data-tone={dataStatusTone}
          data-testid="stock-analysis-toolbar-data-status"
        >
          {dataStatusLabel}
        </span>
        <span
          className="stock-analysis-page__toolbar-status-dot"
          data-tone={gateStatusTone}
          data-testid="stock-analysis-toolbar-gate-status"
        >
          {gateStatusLabel}
        </span>
        <span
          className="stock-analysis-page__toolbar-status-dot"
          data-tone={loopStatusTone}
          data-testid="stock-analysis-toolbar-loop-status"
        >
          {loopStatusLabel}
        </span>
        <span
          className="stock-analysis-page__toolbar-status-dot stock-analysis-page__toolbar-status-dot--formal"
          data-tone={formalUseAllowed ? "positive" : "warning"}
          data-testid="stock-analysis-toolbar-formal-status"
        >
          使用边界：{formalUseAllowed ? "正式口径可用" : "仅供观察"}
        </span>
      </div>
      <span className="stock-analysis-page__toolbar-route-chip" data-testid="stock-analysis-toolbar-route">
        数据入口 {routeLabel}
      </span>
      <span
        className="stock-analysis-page__complete-evidence-toggle"
        data-testid="stock-analysis-complete-evidence-toggle"
        role="status"
        title="完整证据的业务口径尚未确认，当前不执行该筛选。"
      >
        <span>完整证据：口径待确认</span>
      </span>
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
      <AntButton
        data-testid="stock-analysis-refresh"
        className="stock-analysis-page__dh-topbar-btn"
        icon={<ReloadOutlined />}
        loading={isRefreshing}
        disabled={isRefreshing}
        onClick={onRefresh}
        aria-label="重算选股与门禁并重新读取观察队列"
      >
        {isRefreshing ? "重算中" : "重算选股与门禁"}
      </AntButton>
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
  );
}
