import { type PnlByBusinessManualAdjustmentPayload, type PnlByBusinessManualAdjustmentRequest, type PnlByBusinessYtdItem } from "../../api/contracts";
import { EM_DASH } from "../../utils/format";
import { formatPnlWan } from "./pnlByBusinessDisplay";
import { type ManualAdjustmentDraft } from "./pnlByBusinessAdjustmentState";

function formatAdjustmentStatus(status: string): string {
  if (status === "approved") {
    return "已批准";
  }
  if (status === "pending") {
    return "待确认";
  }
  if (status === "rejected") {
    return "已撤销";
  }
  return status || EM_DASH;
}

function formatAdjustmentEvent(eventType: string): string {
  if (eventType === "created") {
    return "新增";
  }
  if (eventType === "edited") {
    return "编辑";
  }
  if (eventType === "revoked") {
    return "撤销";
  }
  if (eventType === "restored") {
    return "恢复";
  }
  return eventType || EM_DASH;
}
export function PnlByBusinessManualAdjustmentPanel({
  rows,
  selectedReportDate,
  selectedBusinessRow,
  selectedRowKey,
  draft,
  editingAdjustmentId,
  adjustmentError,
  readError,
  isLoading,
  isSaving,
  isActionBusy,
  adjustments,
  events,
  onSelectRowKey,
  onDraftChange,
  onSubmit,
  onEdit,
  onCancelEdit,
  onRevoke,
  onRestore,
}: {
  rows: PnlByBusinessYtdItem[];
  selectedReportDate: string;
  selectedBusinessRow: PnlByBusinessYtdItem | undefined;
  selectedRowKey: string;
  draft: ManualAdjustmentDraft;
  editingAdjustmentId: string | null;
  adjustmentError: string;
  readError: string | null;
  isLoading: boolean;
  isSaving: boolean;
  isActionBusy: boolean;
  adjustments: PnlByBusinessManualAdjustmentPayload[];
  events: PnlByBusinessManualAdjustmentPayload[];
  onSelectRowKey: (rowKey: string) => void;
  onDraftChange: <K extends keyof ManualAdjustmentDraft>(key: K, value: ManualAdjustmentDraft[K]) => void;
  onSubmit: () => void;
  onEdit: (item: PnlByBusinessManualAdjustmentPayload) => void;
  onCancelEdit: () => void;
  onRevoke: (adjustmentId: string) => void;
  onRestore: (adjustmentId: string) => void;
}) {
  return (
    <section
      className="pnl-by-business-analysis-block pnl-by-business-adjustment-panel"
      data-testid="pnl-by-business-manual-adjustments"
    >
      <div className="pnl-by-business-analysis-heading">
        <div>
          <h2>手工调整</h2>
          <p>
            {selectedReportDate} · {selectedBusinessRow?.business_type ?? EM_DASH}
          </p>
        </div>
        <span className="pnl-by-business-section-pill">{readError ? "读取失败" : `${adjustments.length} 当前`}</span>
      </div>

      <div className="pnl-by-business-adjustment-form">
        <label className="pnl-by-business-filter-label">
          业务种类
          <select
            aria-label="pnl-by-business-adjustment-row"
            className="pnl-by-business-control"
            value={selectedRowKey}
            onChange={(event) => onSelectRowKey(event.target.value)}
          >
            {rows.map((row) => (
              <option key={row.row_key} value={row.row_key}>
                {row.business_type}
              </option>
            ))}
          </select>
        </label>
        <label className="pnl-by-business-filter-label">
          调整金额（元）
          <input
            aria-label="pnl-by-business-adjustment-amount"
            className="pnl-by-business-control"
            inputMode="decimal"
            value={draft.manual_adjustment}
            onChange={(event) => onDraftChange("manual_adjustment", event.target.value)}
          />
        </label>
        <label className="pnl-by-business-filter-label">
          审批状态
          <select
            aria-label="pnl-by-business-adjustment-status"
            className="pnl-by-business-control"
            value={draft.approval_status}
            onChange={(event) =>
              onDraftChange(
                "approval_status",
                event.target.value as PnlByBusinessManualAdjustmentRequest["approval_status"],
              )
            }
          >
            <option value="approved">已批准</option>
            <option value="pending">待确认</option>
            <option value="rejected">已撤销</option>
          </select>
        </label>
        <label className="pnl-by-business-filter-label pnl-by-business-adjustment-reason-field">
          原因
          <input
            aria-label="pnl-by-business-adjustment-reason"
            className="pnl-by-business-control"
            value={draft.reason ?? ""}
            onChange={(event) => onDraftChange("reason", event.target.value)}
          />
        </label>
        <div className="pnl-by-business-adjustment-actions">
          <button
            type="button"
            className="pnl-by-business-action-button pnl-by-business-action-button-primary"
            disabled={isSaving || Boolean(readError) || !selectedReportDate || !selectedRowKey}
            onClick={onSubmit}
          >
            {editingAdjustmentId ? "保存编辑" : "保存调整"}
          </button>
          {editingAdjustmentId ? (
            <button
              type="button"
              className="pnl-by-business-action-button"
              disabled={isSaving}
              onClick={onCancelEdit}
            >
              取消
            </button>
          ) : null}
        </div>
      </div>
      {adjustmentError ? <div className="pnl-by-business-adjustment-error">{adjustmentError}</div> : null}
      {readError ? <div className="pnl-by-business-adjustment-error">{readError}</div> : null}

      <div className="pnl-by-business-adjustment-columns">
        <div className="pnl-by-business-adjustment-list">
          <div className="pnl-by-business-adjustment-list-heading">
            <strong>当前调整</strong>
            <span>{isLoading ? "读取中" : readError ? "读取失败" : `${adjustments.length} 条`}</span>
          </div>
          {isLoading ? (
            <div className="pnl-by-business-analysis-state">加载中</div>
          ) : readError ? (
            <div className="pnl-by-business-analysis-state">审批记录不可用，未按 0 条处理。</div>
          ) : adjustments.length === 0 ? (
            <div className="pnl-by-business-analysis-state">暂无手工调整</div>
          ) : (
            <div className="pnl-by-business-table-shell pnl-by-business-adjustment-table-shell">
              <table className="pnl-by-business-table pnl-by-business-adjustment-table">
                <thead>
                  <tr>
                    <th>业务种类</th>
                    <th>金额（万元）</th>
                    <th>状态</th>
                    <th>原因</th>
                    <th>最近事件</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {adjustments.map((item) => (
                    <tr key={`adjustment-current-${item.adjustment_id}`}>
                      <td>{item.business_type || item.row_key}</td>
                      <td>{formatPnlWan(item.manual_adjustment)}</td>
                      <td>{formatAdjustmentStatus(item.approval_status)}</td>
                      <td>{item.reason || EM_DASH}</td>
                      <td>{formatAdjustmentEvent(item.event_type)}</td>
                      <td>
                        <div className="pnl-by-business-row-actions">
                          <button type="button" onClick={() => onEdit(item)} disabled={isActionBusy}>
                            编辑
                          </button>
                          <button
                            type="button"
                            onClick={() => onRevoke(item.adjustment_id)}
                            disabled={isActionBusy || item.approval_status !== "approved"}
                          >
                            撤销
                          </button>
                          <button
                            type="button"
                            onClick={() => onRestore(item.adjustment_id)}
                            disabled={isActionBusy || item.approval_status !== "rejected"}
                          >
                            恢复
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="pnl-by-business-adjustment-list">
          <div className="pnl-by-business-adjustment-list-heading">
            <strong>历史事件</strong>
            <span>{isLoading ? "读取中" : readError ? "读取失败" : `${events.length} 条`}</span>
          </div>
          {isLoading ? (
            <div className="pnl-by-business-analysis-state">加载中</div>
          ) : readError ? (
            <div className="pnl-by-business-analysis-state">历史事件不可用，未按 0 条处理。</div>
          ) : events.length === 0 ? (
            <div className="pnl-by-business-analysis-state">暂无历史事件</div>
          ) : (
            <div className="pnl-by-business-table-shell pnl-by-business-adjustment-table-shell">
              <table className="pnl-by-business-table pnl-by-business-adjustment-table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>事件</th>
                    <th>业务种类</th>
                    <th>金额（万元）</th>
                    <th>状态</th>
                    <th>原因</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((item) => (
                    <tr key={`adjustment-event-${item.adjustment_id}-${item.event_type}-${item.created_at}`}>
                      <td>{item.created_at}</td>
                      <td>{formatAdjustmentEvent(item.event_type)}</td>
                      <td>{item.business_type || item.row_key}</td>
                      <td>{formatPnlWan(item.manual_adjustment)}</td>
                      <td>{formatAdjustmentStatus(item.approval_status)}</td>
                      <td>{item.reason || EM_DASH}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
