import type {
  BalanceAnalysisDecisionItemStatusRow,
  BalanceAnalysisEventCalendarRow,
  BalanceAnalysisRiskAlertRow,
  BalanceAnalysisWorkbookOperationalSection,
} from "../../../api/contracts";
import {
  formatBalanceBusinessTextDisplay,
  formatBalanceDecisionWorkflowStatusDisplay,
  formatBalanceGovernedSeverityDisplay,
  formatBalanceWorkbookCellDisplay,
  formatBalanceWorkbookOperationalSectionKeyDisplay,
} from "../pages/balanceAnalysisPageModel";
import {
  hasWorkbookFields,
  renderWorkbookContractMismatch,
  renderWorkbookEmptyState,
} from "./BalanceWorkbookAnalysisPanels";

export function renderDecisionItemsPanel(
  rows: BalanceAnalysisDecisionItemStatusRow[],
  {
    selectedKey,
    updatingKey,
    onSelect,
    onUpdateStatus,
  }: {
    selectedKey: string | null;
    updatingKey: string | null;
    onSelect: (row: BalanceAnalysisDecisionItemStatusRow) => void;
    onUpdateStatus: (
      row: BalanceAnalysisDecisionItemStatusRow,
      status: "confirmed" | "dismissed",
    ) => void;
  },
) {
  if (rows.length === 0) {
    return renderWorkbookEmptyState("暂无治理事项。");
  }
  const hasRequiredFields = rows.every(
    (row) =>
      row.decision_key &&
      row.title &&
      row.action_label &&
      row.severity &&
      row.reason &&
      row.source_section &&
      row.rule_id &&
      row.rule_version &&
      row.latest_status &&
      row.latest_status.decision_key &&
      row.latest_status.status,
  );
  if (!hasRequiredFields) {
    return renderWorkbookContractMismatch(
      { key: "decision_items" },
      "Workbook contract mismatch：决策事项字段不完整。",
    );
  }

  return (
    <div data-testid="balance-analysis-workbook-table-decision_items" className="balance-analysis-mini-list">
      {rows.map((row, index) => (
        <article
          key={row.decision_key}
          className="balance-analysis-ledger-card"
          data-selected={selectedKey === row.decision_key ? "true" : "false"}
        >
          <div className="balance-analysis-mini-topline">
            <div className="balance-analysis-mini-label balance-analysis-mini-label--strong">
              {formatBalanceBusinessTextDisplay(row.title)}
            </div>
            <span className="balance-analysis-panel-badge">{formatBalanceGovernedSeverityDisplay(row.severity)}</span>
          </div>
          <div className="balance-analysis-ledger-copy-text">
            {formatBalanceBusinessTextDisplay(row.reason)}
          </div>
          <div className="balance-analysis-ledger-meta-row">
            <span>{formatBalanceBusinessTextDisplay(row.action_label)}</span>
            <span>{formatBalanceDecisionWorkflowStatusDisplay(row.latest_status.status)}</span>
            <span>
              更新人：{row.latest_status.updated_by ? row.latest_status.updated_by : "未更新"}
            </span>
          </div>
          <div className="balance-analysis-action-row">
            <button
              data-testid={`balance-analysis-decision-confirm-${index}`}
              type="button"
              disabled={updatingKey === row.decision_key}
              className="balance-analysis-mini-button"
              onClick={() => onUpdateStatus(row, "confirmed")}
            >
              确认
            </button>
            <button
              data-testid={`balance-analysis-decision-dismiss-${index}`}
              type="button"
              disabled={updatingKey === row.decision_key}
              className="balance-analysis-mini-button"
              onClick={() => onUpdateStatus(row, "dismissed")}
            >
              忽略
            </button>
            <button
              data-testid={`balance-analysis-decision-view-status-${index}`}
              type="button"
              className="balance-analysis-mini-button"
              onClick={() => onSelect(row)}
            >
              详情
            </button>
          </div>
        </article>
      ))}
    </div>
  );
}

export function renderEventCalendarPanel(
  table: Extract<BalanceAnalysisWorkbookOperationalSection, { section_kind: "event_calendar" }>,
  {
    onSelect,
    selectedKey,
  }: {
    onSelect: (row: BalanceAnalysisEventCalendarRow) => void;
    selectedKey: string | null;
  },
) {
  if (table.rows.length === 0) {
    return renderWorkbookEmptyState("暂无治理事项。");
  }
  if (
    !hasWorkbookFields(table.rows, [
      "event_date",
      "event_type",
      "title",
      "source",
      "impact_hint",
      "source_section",
    ])
  ) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：事件日历字段不完整。");
  }

  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} className="balance-analysis-mini-list">
      {table.rows.map((row, index) => (
        <button
          key={`${table.key}-${index}`}
          type="button"
          onClick={() => onSelect(row)}
          className="balance-analysis-right-rail-button"
        >
          <article
            className="balance-analysis-ledger-card"
            data-selected={selectedKey === `${row.event_date}:${row.title}` ? "true" : "false"}
          >
            <div className="balance-analysis-mini-topline">
              <div className="balance-analysis-mini-label balance-analysis-mini-label--strong">
                {formatBalanceBusinessTextDisplay(row.title)}
              </div>
              <div className="balance-analysis-mini-value--info">{formatBalanceWorkbookCellDisplay(row.event_date)}</div>
            </div>
            <div className="balance-analysis-ledger-copy-text">
              {formatBalanceBusinessTextDisplay(row.impact_hint)}
            </div>
            <div className="balance-analysis-ledger-meta-row">
              <span>{formatBalanceBusinessTextDisplay(row.event_type)}</span>
              <span>{formatBalanceBusinessTextDisplay(row.source)}</span>
            </div>
          </article>
        </button>
      ))}
    </div>
  );
}

export function renderRiskAlertsPanel(
  table: Extract<BalanceAnalysisWorkbookOperationalSection, { section_kind: "risk_alerts" }>,
  {
    onSelect,
    selectedKey,
  }: {
    onSelect: (row: BalanceAnalysisRiskAlertRow) => void;
    selectedKey: string | null;
  },
) {
  if (table.rows.length === 0) {
    return renderWorkbookEmptyState("暂无治理事项。");
  }
  if (
    !hasWorkbookFields(table.rows, [
      "title",
      "severity",
      "reason",
      "source_section",
      "rule_id",
      "rule_version",
    ])
  ) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：风险预警字段不完整。");
  }

  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} className="balance-analysis-mini-list">
      {table.rows.map((row, index) => (
        <button
          key={`${table.key}-${index}`}
          type="button"
          onClick={() => onSelect(row)}
          className="balance-analysis-right-rail-button"
        >
          <article
            className="balance-analysis-ledger-card balance-analysis-ledger-card--warning"
            data-selected={selectedKey === `${row.severity}:${row.title}` ? "true" : "false"}
          >
            <div className="balance-analysis-mini-topline">
              <div className="balance-analysis-mini-label balance-analysis-mini-label--strong">
                {formatBalanceBusinessTextDisplay(row.title)}
              </div>
              <span className="balance-analysis-panel-badge balance-analysis-panel-badge--warning">
                {formatBalanceGovernedSeverityDisplay(row.severity)}
              </span>
            </div>
            {/* title 保留后端原文（含源字段名），正文走显示层中文化。 */}
            <div
              className="balance-analysis-ledger-copy-text balance-analysis-ledger-copy-text--warning"
              title={row.reason}
            >
              {formatBalanceBusinessTextDisplay(row.reason)}
            </div>
            <div className="balance-analysis-ledger-meta-row balance-analysis-ledger-meta-row--warning">
              <span>{formatBalanceWorkbookOperationalSectionKeyDisplay(row.source_section)}</span>
            </div>
          </article>
        </button>
      ))}
    </div>
  );
}

export function renderWorkbookRightRailPanel(table: BalanceAnalysisWorkbookOperationalSection) {
  void table;
  return null;
}
