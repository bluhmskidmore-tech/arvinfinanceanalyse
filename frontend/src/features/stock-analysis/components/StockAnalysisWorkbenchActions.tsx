import type { Dayjs } from "dayjs";
import { ClockCircleOutlined, ReloadOutlined, SafetyCertificateOutlined, SearchOutlined } from "@ant-design/icons";
import { Button, DatePicker, Typography } from "antd";

import { formatGeneratedAtLabel } from "../lib/stockAnalysisPageCopy";
import { SA_SHELL_NUM } from "../lib/stockAnalysisPageChrome";

const { Text } = Typography;

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
  completeEvidenceOnly: boolean;
  agentDrawerOpen: boolean;
  generatedAt?: string | null;
  onAsOfOverrideChange: (value: string | null) => void;
  onQueueSearchTextChange: (value: string) => void;
  onCompleteEvidenceOnlyChange: (value: boolean) => void;
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
  completeEvidenceOnly,
  agentDrawerOpen,
  generatedAt,
  onAsOfOverrideChange,
  onQueueSearchTextChange,
  onCompleteEvidenceOnlyChange,
  onOpenAgentDrawer,
  onRefresh,
  isRefreshing = false,
  refreshStatusMessage,
  refreshStatusTone = "neutral",
}: StockAnalysisWorkbenchActionsProps) {
  return (
    <div className="stock-analysis-page__workbench-actions">
      <DatePicker
        allowClear
        aria-label="as-of-date-picker"
        className="stock-analysis-page__dh-date-picker"
        data-testid="stock-analysis-as-of-picker"
        value={pickerDisplay}
        onChange={(_, iso) => {
          onAsOfOverrideChange(Array.isArray(iso) ? (iso[0] ?? null) : iso || null);
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
      </div>
      <label
        className="stock-analysis-page__complete-evidence-toggle"
        data-testid="stock-analysis-complete-evidence-toggle"
      >
        <input
          type="checkbox"
          checked={completeEvidenceOnly}
          onChange={(event) => {
            onCompleteEvidenceOnlyChange(event.target.checked);
          }}
        />
        <span>仅完整证据</span>
      </label>
      <Button
        type="default"
        className="stock-analysis-page__agent-entry stock-analysis-page__dh-topbar-btn stock-analysis-page__agent-entry--quiet"
        data-testid="stock-analysis-agent-open"
        icon={<SafetyCertificateOutlined />}
        onClick={onOpenAgentDrawer}
        aria-expanded={agentDrawerOpen}
      >
        复核助手
      </Button>
      <Button
        data-testid="stock-analysis-refresh"
        className="stock-analysis-page__dh-topbar-btn"
        icon={<ReloadOutlined />}
        loading={isRefreshing}
        disabled={isRefreshing}
        onClick={onRefresh}
        aria-label="刷新并重新计算选股"
      >
        {isRefreshing ? "重新计算中" : "刷新选股"}
      </Button>
      {refreshStatusMessage ? (
        <Text
          className="stock-analysis-page__refresh-feedback"
          data-testid="stock-analysis-refresh-feedback"
          data-tone={refreshStatusTone}
          role="status"
        >
          {refreshStatusMessage}
        </Text>
      ) : null}
      {generatedAt ? (
        <Text
          type="secondary"
          className={`${SA_SHELL_NUM} stock-analysis-page__generated-at stock-analysis-page__visually-hidden`}
          title={generatedAt}
        >
          <ClockCircleOutlined /> {formatGeneratedAtLabel(generatedAt)}
        </Text>
      ) : null}
    </div>
  );
}
