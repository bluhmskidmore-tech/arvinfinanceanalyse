import type {
  LedgerPnlAdditivityCheck,
  LedgerPnlArrangementRule,
  LedgerPnlFormalIndicatorRuleChecksPayload,
  LedgerPnlRatioRecomputationCheck,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { LEDGER_PNL_RULE_CHECKS_PANEL_ID } from "../models/ledgerPnlPageConstants";
import { formatContractMetricValue } from "../models/ledgerPnlFormalContractModel";

function ruleCheckBadgeTone(status: string) {
  if (status === "matched" || status === "exact" || status === "pass") {
    return "ok";
  }
  if (status === "mismatch" || status === "fail") {
    return "danger";
  }
  return "neutral";
}

function formatRuleCheckValue(value: string | number | null | undefined, unit: string) {
  return formatContractMetricValue(value, unit);
}

function RatioRecomputationTable(props: { rows: LedgerPnlRatioRecomputationCheck[] }) {
  if (props.rows.length === 0) {
    return <div className="ledger-pnl-analysis__empty">暂无比率复算检查</div>;
  }
  return (
    <table className="ledger-pnl-analysis__residual-table">
      <thead>
        <tr>
          <th>指标</th>
          <th>契约值</th>
          <th>复算值</th>
          <th>差异</th>
          <th>状态</th>
          <th>说明</th>
        </tr>
      </thead>
      <tbody>
        {props.rows.map((row) => (
          <tr key={row.check_key} data-testid={`ledger-pnl-rule-checks-ratio-row-${row.check_key}`}>
            <td>{row.metric_name}</td>
            <td>{formatRuleCheckValue(row.contract_value, row.unit)}</td>
            <td>{formatRuleCheckValue(row.recomputed_value, row.unit)}</td>
            <td>{formatRuleCheckValue(row.diff, row.unit)}</td>
            <td>
              <span
                className={`ledger-pnl-analysis__status-badge ledger-pnl-analysis__status-badge--${ruleCheckBadgeTone(row.status)}`}
              >
                {row.status}
              </span>
            </td>
            <td>
              {row.status === "insufficient_inputs" && row.missing_inputs?.length
                ? `缺失输入：${row.missing_inputs.join("；")}`
                : row.note ?? EM_DASH}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AdditivityChecksTable(props: { rows: LedgerPnlAdditivityCheck[] }) {
  if (props.rows.length === 0) {
    return <div className="ledger-pnl-analysis__empty">暂无合并勾稽检查</div>;
  }
  return (
    <table className="ledger-pnl-analysis__residual-table">
      <thead>
        <tr>
          <th>勾稽项</th>
          <th>总额</th>
          <th>分项合计</th>
          <th>残差</th>
          <th>状态</th>
          <th>说明</th>
        </tr>
      </thead>
      <tbody>
        {props.rows.map((row) => (
          <tr key={row.check_key} data-testid={`ledger-pnl-rule-checks-additivity-row-${row.check_key}`}>
            <td>{row.metric_name}</td>
            <td>{formatRuleCheckValue(row.total_value, row.unit)}</td>
            <td>{formatRuleCheckValue(row.components_sum, row.unit)}</td>
            <td>{formatRuleCheckValue(row.residual, row.unit)}</td>
            <td>
              <span
                className={`ledger-pnl-analysis__status-badge ledger-pnl-analysis__status-badge--${ruleCheckBadgeTone(row.status)}`}
              >
                {row.status}
              </span>
            </td>
            <td>{row.status === "residual_present" ? row.note ?? "残差需在正式来源接入时解释" : "分项合计与总额一致"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function arrangementRuleDetail(rule: LedgerPnlArrangementRule) {
  if (rule.status === "insufficient_inputs" && rule.missing_inputs?.length) {
    return `缺失输入：${rule.missing_inputs.join("；")}`;
  }
  if (rule.status === "pass" || rule.status === "fail") {
    return `实际值 ${rule.actual_value ?? EM_DASH}${rule.unit ?? ""} ${rule.comparator ?? "<="} 目标值 ${rule.target_value ?? EM_DASH}${rule.unit ?? ""}（${rule.quarter_end_type ?? EM_DASH}）`;
  }
  if (rule.status === "informational") {
    return `管理层测算假设：${rule.assumption_value ?? EM_DASH}${rule.assumption_unit ?? ""}。${rule.note ?? ""}`;
  }
  if (rule.status === "summary") {
    return `引用勾稽 ${rule.referenced_additivity_check_keys?.join("、") ?? EM_DASH}；exact ${rule.exact_count ?? 0} / residual_present ${rule.residual_present_count ?? 0}`;
  }
  return rule.note ?? EM_DASH;
}

function ArrangementRulesList(props: { rows: LedgerPnlArrangementRule[] }) {
  if (props.rows.length === 0) {
    return <div className="ledger-pnl-analysis__empty">暂无安排规则检查</div>;
  }
  return (
    <div className="ledger-pnl-analysis__status-list">
      {props.rows.map((rule) => (
        <article
          key={rule.rule_key}
          data-testid={`ledger-pnl-rule-checks-arrangement-row-${rule.rule_key}`}
          className="ledger-pnl-analysis__status-row"
        >
          <div className="ledger-pnl-analysis__status-main">
            <span className="ledger-pnl-analysis__status-name">{rule.rule_name}</span>
            <span
              className={`ledger-pnl-analysis__status-badge ledger-pnl-analysis__status-badge--${ruleCheckBadgeTone(rule.status)}`}
            >
              {rule.status}
            </span>
          </div>
          <div className="ledger-pnl-analysis__status-source">{arrangementRuleDetail(rule)}</div>
          <div className="ledger-pnl-analysis__source-contract-ref">{rule.source_ref}</div>
        </article>
      ))}
    </div>
  );
}

export function LedgerPnlFormalRuleChecksPanel(props: {
  ruleChecks: LedgerPnlFormalIndicatorRuleChecksPayload | undefined;
  requestedReportMonth: string;
  isLoading: boolean;
  isError: boolean;
}) {
  const { ruleChecks, requestedReportMonth, isLoading, isError } = props;
  const summary = ruleChecks?.summary;

  return (
    <section
      id={LEDGER_PNL_RULE_CHECKS_PANEL_ID}
      data-testid="ledger-pnl-formal-indicator-rule-checks-panel"
      tabIndex={-1}
      className="ledger-pnl-analysis__status-panel"
    >
      <div className="ledger-pnl-analysis__status-header">
        <div>
          <h3 className="ledger-pnl-analysis__status-title">规则符合性检查</h3>
          <div className="ledger-pnl-analysis__status-subtitle">
            对冻结契约值做比率复算、合并勾稽与管理安排规则校验；仅用于契约分析核对，不产生新的正式指标值。
          </div>
        </div>
        <div className="ledger-pnl-analysis__status-summary">
          <span>report_month {ruleChecks?.report_month || requestedReportMonth || EM_DASH}</span>
          <span>formal_use_allowed={String(ruleChecks?.formal_use_allowed ?? false)}</span>
          <span>sample_status {ruleChecks?.sample_status ?? EM_DASH}</span>
          {summary ? (
            <>
              <span>比率复算 {summary.ratio_recomputation.matched}/{summary.ratio_recomputation.total} matched</span>
              <span>勾稽 {summary.additivity_checks.exact}/{summary.additivity_checks.total} exact</span>
              <span>安排规则 {summary.arrangement_rules.pass}/{summary.arrangement_rules.total} pass</span>
            </>
          ) : null}
        </div>
      </div>

      {isLoading ? (
        <div className="ledger-pnl-analysis__empty">规则符合性检查读取中</div>
      ) : isError ? (
        <div className="ledger-pnl-analysis__empty">规则符合性检查读取失败</div>
      ) : !ruleChecks || ruleChecks.sample_status === "missing_contract" ? (
        <details className="ledger-pnl-governance-details">
          <summary>
            {(ruleChecks?.report_month || requestedReportMonth || "本月")} 正式契约缺失，规则检查无法执行；展开补证步骤
          </summary>
          <div
            data-testid="ledger-pnl-rule-checks-missing-contract"
            className="ledger-pnl-analysis__source-contract-actions"
          >
            <div className="ledger-pnl-analysis__source-contract-actions-header">
              <strong>
                {(ruleChecks?.report_month || requestedReportMonth || "本月")} 正式契约缺失，无法执行规则检查
              </strong>
              <span>{ruleChecks?.contract_note ?? "后台未登记该月正式财务指标契约，规则符合性检查无法执行。"}</span>
            </div>
            {ruleChecks?.remediation ? (
              <div className="ledger-pnl-analysis__source-contract-action-list">
                <article className="ledger-pnl-analysis__source-contract-action-item">
                  <strong>1</strong>
                  <div>
                    <span>{ruleChecks.remediation.action_label}</span>
                    <small>{ruleChecks.remediation.action_detail}</small>
                    <small>登记入口 {ruleChecks.remediation.registration_target}</small>
                    <small>验证 {ruleChecks.remediation.verification}</small>
                  </div>
                </article>
              </div>
            ) : null}
          </div>
        </details>
      ) : (
        <details className="ledger-pnl-governance-details">
          <summary>展开比率复算、合并勾稽与管理安排规则明细</summary>
          <div className="ledger-pnl-analysis__table ledger-pnl-analysis__residual-table-wrap">
            <div className="ledger-pnl-analysis__table-title">比率复算</div>
            <RatioRecomputationTable rows={ruleChecks.ratio_recomputation} />
          </div>

          <div className="ledger-pnl-analysis__table ledger-pnl-analysis__residual-table-wrap">
            <div className="ledger-pnl-analysis__table-title">合并勾稽</div>
            <AdditivityChecksTable rows={ruleChecks.additivity_checks} />
          </div>

          <div className="ledger-pnl-analysis__table ledger-pnl-analysis__residual-table-wrap">
            <div className="ledger-pnl-analysis__table-title">管理安排规则</div>
            <ArrangementRulesList rows={ruleChecks.arrangement_rules} />
          </div>
        </details>
      )}
    </section>
  );
}
