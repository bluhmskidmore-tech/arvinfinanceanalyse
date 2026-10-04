import type { LedgerPnlFormalFinancialIndicatorContractPayload } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import {
  LEDGER_PNL_FORMAL_CONTRACT_PANEL_ID,
  LEDGER_PNL_FORMAL_CONTRACT_RELEASE_GATE_ID,
  LEDGER_PNL_FORMAL_CONTRACT_MATERIAL_CHECKLIST_ID,
} from "../models/ledgerPnlPageConstants";
import {
  buildFormalContractActionQueue,
  buildFormalContractDecision,
  buildFormalContractMaterialChecklist,
  contractActionTitle,
  formalContractExecutionStatus,
  formalContractReadbackAction,
  formalSourceContractTone,
  formatContractMetricValue,
  formatFormalContractNote,
  formatFormalContractValue,
  registeredPendingReleaseGate,
  sourceStatusLabels,
} from "../models/ledgerPnlFormalContractModel";

export function LedgerPnlFormalSourceContractPanel(props: {
  contract: LedgerPnlFormalFinancialIndicatorContractPayload | undefined;
  requestedReportMonth: string;
  isLoading: boolean;
  isError: boolean;
}) {
  const metrics = props.contract?.metrics ?? [];
  const counts = {
    formal_pending: metrics.filter((metric) => metric.source_status === "formal_pending").length,
    candidate_qdb_aligned: metrics.filter((metric) => metric.source_status === "candidate_qdb_aligned").length,
    needs_reconciliation: metrics.filter((metric) => metric.source_status === "needs_reconciliation").length,
  };
  const decision = buildFormalContractDecision(props.contract, props.isLoading, props.isError);
  const contractNote = formatFormalContractNote(props.contract);
  const actionQueue = buildFormalContractActionQueue(metrics);
  const hasActionQueue = actionQueue.length > 0;
  const releaseGate = registeredPendingReleaseGate(props.contract);
  const materialChecklist = buildFormalContractMaterialChecklist(props.contract?.remediation);
  const executionStatus = formalContractExecutionStatus({
    contract: props.contract,
    isLoading: props.isLoading,
    isError: props.isError,
    materialChecklist,
  });
  const readbackAction = formalContractReadbackAction({
    contract: props.contract,
    isLoading: props.isLoading,
    isError: props.isError,
    materialChecklist,
  });

  return (
    <section
      id={LEDGER_PNL_FORMAL_CONTRACT_PANEL_ID}
      data-testid="ledger-pnl-formal-indicator-source-contract-panel"
      tabIndex={-1}
      className="ledger-pnl-analysis__status-panel ledger-pnl-analysis__status-panel--source-contract"
    >
      <div className="ledger-pnl-analysis__status-header">
        <div>
          <h3 className="ledger-pnl-analysis__status-title">正式财务指标源契约</h3>
          <div className="ledger-pnl-analysis__status-subtitle">
            Excel 样本值、系统候选值与正式展示值分列；正式值没有来源时保持未接入。
          </div>
        </div>
        <div className="ledger-pnl-analysis__status-summary">
          <span>report_month {props.contract?.report_month || props.requestedReportMonth || EM_DASH}</span>
          <span>sample_status {props.contract?.sample_status ?? EM_DASH}</span>
          <span>formal_use_allowed={String(props.contract?.formal_use_allowed ?? false)}</span>
          <span>formal_pending {counts.formal_pending}</span>
          <span>candidate_qdb_aligned {counts.candidate_qdb_aligned}</span>
          <span>needs_reconciliation {counts.needs_reconciliation}</span>
        </div>
      </div>

      <div
        data-testid="ledger-pnl-formal-indicator-source-contract-decision"
        className={`ledger-pnl-analysis__source-contract-decision ledger-pnl-analysis__source-contract-decision--${decision.tone}`}
      >
        <strong>{decision.title}</strong>
        <span>{decision.detail}</span>
      </div>

      {contractNote ? (
        <div className="ledger-pnl-analysis__source-contract-note">{contractNote}</div>
      ) : null}

      {releaseGate ? (
        <div
          id={LEDGER_PNL_FORMAL_CONTRACT_RELEASE_GATE_ID}
          data-testid="ledger-pnl-formal-indicator-source-contract-release-gate"
          tabIndex={-1}
          className="ledger-pnl-analysis__source-contract-release-gate"
        >
          <strong>release_gate {releaseGate.status}</strong>
          {releaseGate.blocking_reason ? <span>{releaseGate.blocking_reason}</span> : null}
          {releaseGate.required_evidence?.length ? (
            <div>
              <span>required_evidence</span>
              {releaseGate.required_evidence.map((item) => (
                <small key={item}>{item}</small>
              ))}
            </div>
          ) : null}
          {releaseGate.readback_action ? (
            <small>readback_action {releaseGate.readback_action}</small>
          ) : null}
        </div>
      ) : null}

      {props.isLoading ? (
        <div className="ledger-pnl-analysis__empty">正式财务指标源契约读取中</div>
      ) : props.isError ? (
        <div className="ledger-pnl-analysis__empty">正式财务指标源契约读取失败</div>
      ) : metrics.length > 0 ? (
        <>
          {hasActionQueue ? (
            <div
              data-testid="ledger-pnl-formal-indicator-source-contract-action-queue"
              className="ledger-pnl-analysis__source-contract-actions"
            >
              <div className="ledger-pnl-analysis__source-contract-actions-header">
                <strong>下一步核账队列</strong>
                <span>先处理有系统候选但未对齐的项目，再补正式来源。</span>
              </div>
              <div className="ledger-pnl-analysis__source-contract-action-list">
                {actionQueue.map((metric, index) => (
                  <article
                    key={metric.metric_key}
                    data-testid={`ledger-pnl-formal-indicator-source-contract-action-item-${metric.metric_key}`}
                    className="ledger-pnl-analysis__source-contract-action-item"
                  >
                    <strong>{index + 1}</strong>
                    <div>
                      <span>{metric.metric_name}</span>
                      <em>{contractActionTitle(metric)}</em>
                      <small>
                        Excel {formatContractMetricValue(metric.excel_value, metric.unit)} / 系统候选值{" "}
                        {formatContractMetricValue(metric.system_value, metric.unit)}
                      </small>
                      {metric.reconciliation_gap ? (
                        <small>对账差异 {formatContractMetricValue(metric.reconciliation_gap, metric.unit)}</small>
                      ) : null}
                      <small>{metric.cell_ref}</small>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ) : null}

          <div className="ledger-pnl-analysis__source-contract-list">
            {metrics.map((metric) => {
              const tone = formalSourceContractTone(metric);
              return (
                <article
                  key={metric.metric_key}
                  data-testid={`ledger-pnl-formal-indicator-source-contract-row-${metric.metric_key}`}
                  className={`ledger-pnl-analysis__status-row ledger-pnl-analysis__status-row--${tone}`}
                >
                  <div className="ledger-pnl-analysis__status-main">
                    <span className="ledger-pnl-analysis__status-name">{metric.metric_name}</span>
                    <span className="ledger-pnl-analysis__status-badge">
                      {metric.source_status}
                    </span>
                  </div>
                  <div className="ledger-pnl-analysis__source-contract-status">
                    {sourceStatusLabels[metric.source_status]}
                  </div>
                  <div className="ledger-pnl-analysis__source-contract-values">
                    <div>
                      <span>正式展示值</span>
                      <strong>{formatFormalContractValue(metric.value, metric.unit)}</strong>
                    </div>
                    <div>
                      <span>Excel 样本值</span>
                      <strong>{formatContractMetricValue(metric.excel_value, metric.unit)}</strong>
                    </div>
                    <div>
                      <span>系统候选值</span>
                      <strong>{formatContractMetricValue(metric.system_value, metric.unit)}</strong>
                    </div>
                  </div>
                  {metric.reconciliation_gap ? (
                    <div className="ledger-pnl-analysis__source-contract-gap">
                      对账差异 {metric.reconciliation_gap}
                    </div>
                  ) : null}
                  <div className="ledger-pnl-analysis__status-source">{metric.missing_reason}</div>
                  <div className="ledger-pnl-analysis__source-contract-ref">{metric.cell_ref}</div>
                </article>
              );
            })}
          </div>
        </>
      ) : props.contract?.sample_status === "missing_contract" ? (
        <div className="ledger-pnl-analysis__source-contract-actions">
          <div className="ledger-pnl-analysis__source-contract-actions-header">
            <strong>缺契约补证动作</strong>
            <span>
              {props.contract.remediation?.action_label ??
                `登记 ${props.contract.report_month || props.requestedReportMonth || EM_DASH} 正式财务指标契约`}
            </span>
          </div>
          <div className="ledger-pnl-analysis__source-contract-action-list">
            <article className="ledger-pnl-analysis__source-contract-action-item">
              <strong>1</strong>
              <div>
                <span>
                  {props.contract.remediation?.action_detail ??
                    "从 Excel 正式样本冻结 source contract，再重新核对 QDB 候选值。"}
                </span>
                <div
                  id={LEDGER_PNL_FORMAL_CONTRACT_MATERIAL_CHECKLIST_ID}
                  data-testid="ledger-pnl-formal-indicator-source-contract-material-checklist"
                  tabIndex={-1}
                  className="ledger-pnl-analysis__source-contract-material-checklist"
                >
                  <strong>{materialChecklist.summary}</strong>
                  {materialChecklist.rows.map((row) => (
                    <small key={row.key}>
                      <span>{row.label}</span>
                      {row.value || "待补"}
                    </small>
                  ))}
                  <small>
                    <span>执行状态</span>
                    {executionStatus}
                  </small>
                  <small>
                    <span>回读动作</span>
                    {readbackAction}
                  </small>
                </div>
                <small>正式值保持未接入，不能用分析候选值补齐。</small>
              </div>
            </article>
          </div>
        </div>
      ) : (
        <div className="ledger-pnl-analysis__empty">暂无正式财务指标源契约数据</div>
      )}
    </section>
  );
}
