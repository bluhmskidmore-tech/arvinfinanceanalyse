import type { LedgerPnlAnalysisPayload, LedgerPnlSummaryPayload } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { findPeriodComparisonRow, formatMoney, moneyTone } from "../models/ledgerPnlDisplay";
import { LEDGER_PNL_SECTION_IDS } from "../models/ledgerPnlPageConstants";
import { formatEvidenceRows, formatMetaQuality } from "../models/ledgerPnlSourceEvidence";
import {
  appendLedgerDrill,
  buildLedgerAnalysisAuditState,
  collectLedgerNextDrills,
  focusLedgerFormalContractTarget,
  formalContractRemediationDrill,
  type LedgerFunctionalAuditProps,
} from "../models/ledgerPnlAuditModel";
import {
  buildFormalContractMaterialChecklist,
  formalContractExecutionStatus,
  formalContractMaterialSummary,
  formalContractReadbackAction,
  formalContractRemediationConclusion,
  shortFormalContractReadbackAction,
  summarizeFormalIndicatorContractGaps,
} from "../models/ledgerPnlFormalContractModel";
import { LedgerMoneyDisplay, LedgerPnlSectionLead } from "./LedgerPnlSectionPresentation";

function LedgerFunctionalAuditStrip(props: LedgerFunctionalAuditProps) {
  const state = buildLedgerAnalysisAuditState(props);
  const analysisMeta = props.analysisEnvelope?.result_meta;
  const analysisPayload = props.analysisEnvelope?.result;
  const candidateReady = analysisPayload?.analysis_status === "ready";
  const candidateNextDrills = collectLedgerNextDrills(props.datesMeta, analysisMeta);
  const formalNextDrill = formalContractRemediationDrill(props.formalIndicatorSourceContract);
  const nextDrills = appendLedgerDrill(candidateNextDrills, formalNextDrill);
  const formalGapSummary = summarizeFormalIndicatorContractGaps(
    props.formalIndicatorSourceContract,
    props.isFormalContractLoading,
    props.isFormalContractError,
  );
  const materialChecklist = buildFormalContractMaterialChecklist(
    props.formalIndicatorSourceContract?.remediation,
  );
  const executionStatus = formalContractExecutionStatus({
    contract: props.formalIndicatorSourceContract,
    isLoading: props.isFormalContractLoading,
    isError: props.isFormalContractError,
    materialChecklist,
  });
  const readbackAction = formalContractReadbackAction({
    contract: props.formalIndicatorSourceContract,
    isLoading: props.isFormalContractLoading,
    isError: props.isFormalContractError,
    materialChecklist,
  });
  const formalConclusion = formalContractRemediationConclusion({
    contract: props.formalIndicatorSourceContract,
    isLoading: props.isFormalContractLoading,
    isError: props.isFormalContractError,
    materialChecklist,
    readbackAction,
  });
  const candidateEvidencePath = candidateNextDrills[0]?.label ?? (candidateReady ? "候选分析证据完整" : "等待分析证据");
  const candidateEvidenceSummary = `${analysisMeta?.result_kind ?? "ledger_pnl.analysis"} · evidence ${formatEvidenceRows(analysisMeta)}`;
  const formalEvidencePath = props.requestedReportMonth
    ? formalNextDrill?.label ?? shortFormalContractReadbackAction(readbackAction)
    : "先选择报告日生成 report_month";
  const formalEvidenceActionable =
    props.formalIndicatorSourceContract?.formal_use_allowed !== true;
  const materialSummary = formalContractMaterialSummary({
    contract: props.formalIndicatorSourceContract,
    isLoading: props.isFormalContractLoading,
    isError: props.isFormalContractError,
    materialChecklist,
  });
  return (
    <section
      data-testid="ledger-pnl-functional-audit-strip"
      className={`ledger-pnl-functional-strip ledger-pnl-functional-strip--${state.tone}`}
    >
      <div className="ledger-pnl-functional-strip__main">
        <div className="ledger-pnl-functional-strip__eyebrow">功能性审计</div>
        <h2 className="ledger-pnl-functional-strip__title">{state.title}</h2>
        <div className="ledger-pnl-functional-strip__detail">{state.detail}</div>
      </div>
      <div className="ledger-pnl-functional-strip__headline-facts">
        <div>
          <span>解析报告日</span>
          <strong>{state.resolvedDate}</strong>
        </div>
        <div>
          <span>数据截至日</span>
          <strong>{state.asOfDate}</strong>
        </div>
        <div>
          <span>分析证据行</span>
          <strong>{state.evidenceRows}</strong>
        </div>
        <div>
          <span>候选分析状态</span>
          <strong>{state.analysisStatus}</strong>
        </div>
        <div>
          <span>正式边界</span>
          <strong>{state.formalStatus}</strong>
        </div>
      </div>
      <details className="ledger-pnl-functional-strip__audit">
        <summary className="ledger-pnl-functional-strip__audit-summary">
          审计明细与判断链
        </summary>
        <div className="ledger-pnl-functional-strip__audit-body">
      <div className="ledger-pnl-functional-strip__facts">
        <div>
          <span>请求报告日</span>
          <strong>{state.requestedDate}</strong>
        </div>
        <div>
          <span>分析质量</span>
          <strong>{formatMetaQuality(analysisMeta)}</strong>
        </div>
        <div>
          <span>来源版本</span>
          <strong>{state.sourceVersion}</strong>
        </div>
        <div>
          <span>分析口径</span>
          <strong>{state.basisStatus}</strong>
        </div>
        <div>
          <span>报告日匹配</span>
          <strong>{state.dateStatus}</strong>
        </div>
        <div>
          <span>候选分析证据</span>
          <strong>{candidateEvidenceSummary}</strong>
        </div>
        <div>
          <span>来源状态</span>
          <strong>{state.sourceStatus}</strong>
        </div>
        <div>
          <span>来源证据</span>
          <strong>{state.evidenceStatus}</strong>
        </div>
        <div>
          <span>月度工作簿</span>
          <strong>{state.monthlyAnalysisStatus}</strong>
        </div>
        <div>
          <span>正式契约缺口</span>
          <strong>
            {formalGapSummary.label ??
              `正式待接入 ${formalGapSummary.formalPending} / QDB候选 ${formalGapSummary.qdbCandidateAligned} / 需对账 ${formalGapSummary.needsReconciliation}`}
          </strong>
        </div>
      </div>
      <div className="ledger-pnl-functional-strip__explainability">
        <span>候选分析审计</span>
        <div className="ledger-pnl-functional-strip__explainability-list">
          <strong>{state.analysisStatus}</strong>
          <em>{candidateEvidenceSummary}</em>
          <em>账务口径 {state.basisStatus}</em>
          <em>候选补证入口 {candidateEvidencePath}</em>
        </div>
      </div>
      <div data-testid="ledger-pnl-decision-path" className="ledger-pnl-functional-strip__decision-path">
        <span>判断链</span>
        <div className="ledger-pnl-functional-strip__decision-list">
          <div>
            <span>正式状态</span>
            <strong>{state.formalStatus}</strong>
          </div>
          <div>
            <span>候选分析状态</span>
            <strong>{state.analysisStatus}</strong>
          </div>
          <div>
            <span>候选补证路径</span>
            <strong>{candidateEvidencePath}</strong>
          </div>
          <div>
            <span>分析证据处理路径</span>
            <strong>{state.evidenceAction}</strong>
          </div>
          <div>
            <span>报告日处理路径</span>
            <strong>{state.dateAction}</strong>
          </div>
          <div>
            <span>来源处理路径</span>
            <strong>{state.sourceAction}</strong>
          </div>
          <div>
            <span>月度分析工作簿</span>
            <strong>{state.monthlyAnalysisStatus}</strong>
          </div>
          <div>
            <span>月度补证路径</span>
            <strong>{state.monthlyAnalysisAction}</strong>
          </div>
          <div>
            <span>正式补证路径</span>
            {formalEvidenceActionable ? (
              <button
                type="button"
                className="ledger-pnl-functional-strip__evidence-button"
                aria-label={`正式补证路径 ${formalEvidencePath}`}
                onClick={() =>
                  focusLedgerFormalContractTarget({
                    requestedReportMonth: props.requestedReportMonth,
                    formalIndicatorSourceContract: props.formalIndicatorSourceContract,
                  })
                }
              >
                {formalEvidencePath}
              </button>
            ) : (
              <strong>{formalEvidencePath}</strong>
            )}
          </div>
          <div>
            <span>正式补证结论</span>
            <strong>{formalConclusion}</strong>
          </div>
          <div>
            <span>材料完整性</span>
            <strong>{materialSummary}</strong>
          </div>
          <div>
            <span>执行状态</span>
            <strong>{executionStatus}</strong>
          </div>
          <div>
            <span>回读动作</span>
            <strong>{shortFormalContractReadbackAction(readbackAction)}</strong>
          </div>
        </div>
      </div>
      {nextDrills.length > 0 ? (
        <div className="ledger-pnl-functional-strip__drill">
          <span>下一步补证</span>
          <div className="ledger-pnl-functional-strip__drill-list">
            {nextDrills.map((drill) => (
              <div key={drill.key} className="ledger-pnl-functional-strip__drill-item">
                {drill.key.startsWith("formal-contract-remediation|") ? (
                  <button
                    type="button"
                    className="ledger-pnl-functional-strip__evidence-button"
                    aria-label={`下一步补证 ${drill.label}`}
                    onClick={() =>
                      focusLedgerFormalContractTarget({
                        requestedReportMonth: props.requestedReportMonth,
                        formalIndicatorSourceContract: props.formalIndicatorSourceContract,
                      })
                    }
                  >
                    {drill.label}
                  </button>
                ) : (
                  <strong>{drill.label}</strong>
                )}
                {drill.detail ? <em>{drill.detail}</em> : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}
        </div>
      </details>
    </section>
  );
}

/**
 * 01「当日结论」经营结论卡：数据全部来自页面已加载的 /analysis 与 /summary 响应
 * （conclusion / period_comparison 既有字段 + summary 资产负债三项），零新增请求、
 * 零前端金额计算；正负号 tone 仅用于展示，不改变数值。
 * 当期值取 conclusion.*（no_previous_period 等状态下 period_comparison.rows 为空，
 * 但当期数值仍应可见，不能因为没有上一期对比就把当期结论也一并抹掉）；
 * 变化/上期值取 period_comparison.rows（无可比期时后端字段本身缺失，formatMoney 已回退 EM_DASH）。
 */
function LedgerBusinessConclusionCard(props: {
  analysisPayload: LedgerPnlAnalysisPayload | undefined;
  summary: LedgerPnlSummaryPayload | undefined;
  statusTitle: string;
}) {
  const { analysisPayload, summary, statusTitle } = props;
  const periodRows = analysisPayload?.period_comparison.rows;
  const allPnlChange = findPeriodComparisonRow(periodRows, "all_pnl")?.change;
  const corePnlChange = findPeriodComparisonRow(periodRows, "core_pnl")?.change;
  const other5Previous = findPeriodComparisonRow(periodRows, "other_5_pnl")?.previous;
  const previousReportDate = analysisPayload?.period_comparison.previous_report_date ?? null;
  const balanceUnavailable = !summary || summary.data_status === "no_data";

  return (
    <div className="ledger-pnl-conclusion-card" data-testid="ledger-pnl-conclusion-card">
      <div className="ledger-pnl-conclusion-card__headline">
        <span className="ledger-pnl-conclusion-card__headline-label">全量损益</span>
        <span
          className="ledger-pnl-conclusion-card__headline-value"
          data-tone={moneyTone(analysisPayload?.conclusion.all_pnl)}
        >
          <LedgerMoneyDisplay text={formatMoney(analysisPayload?.conclusion.all_pnl)} />
        </span>
        <span className="ledger-pnl-conclusion-card__headline-change" data-tone={moneyTone(allPnlChange)}>
          较上一可用报告期 {formatMoney(allPnlChange)}
        </span>
      </div>

      <div className="ledger-pnl-conclusion-card__composition">
        <div className="ledger-pnl-conclusion-card__metric">
          <span className="ledger-pnl-conclusion-card__metric-label">核心损益</span>
          <span
            className="ledger-pnl-conclusion-card__metric-value"
            data-tone={moneyTone(analysisPayload?.conclusion.core_pnl)}
          >
            <LedgerMoneyDisplay text={formatMoney(analysisPayload?.conclusion.core_pnl)} />
          </span>
          <span className="ledger-pnl-conclusion-card__metric-secondary" data-tone={moneyTone(corePnlChange)}>
            变化 {formatMoney(corePnlChange)}
          </span>
        </div>
        <div className="ledger-pnl-conclusion-card__metric">
          <span className="ledger-pnl-conclusion-card__metric-label">其他 5* 损益</span>
          <span
            className="ledger-pnl-conclusion-card__metric-value"
            data-tone={moneyTone(analysisPayload?.conclusion.other_5_pnl)}
          >
            <LedgerMoneyDisplay text={formatMoney(analysisPayload?.conclusion.other_5_pnl)} />
          </span>
          <span className="ledger-pnl-conclusion-card__metric-secondary" data-tone={moneyTone(other5Previous)}>
            上期 {formatMoney(other5Previous)}
          </span>
        </div>
      </div>

      <div className="ledger-pnl-conclusion-card__balance">
        <div className="ledger-pnl-conclusion-card__metric">
          <span className="ledger-pnl-conclusion-card__metric-label">总资产</span>
          <span className="ledger-pnl-conclusion-card__metric-value">
            <LedgerMoneyDisplay text={balanceUnavailable ? EM_DASH : formatMoney(summary?.ledger_total_assets)} />
          </span>
        </div>
        <div className="ledger-pnl-conclusion-card__metric">
          <span className="ledger-pnl-conclusion-card__metric-label">总负债</span>
          <span className="ledger-pnl-conclusion-card__metric-value">
            <LedgerMoneyDisplay text={balanceUnavailable ? EM_DASH : formatMoney(summary?.ledger_total_liabilities)} />
          </span>
        </div>
        <div className="ledger-pnl-conclusion-card__metric">
          <span className="ledger-pnl-conclusion-card__metric-label">净资产</span>
          <span className="ledger-pnl-conclusion-card__metric-value">
            <LedgerMoneyDisplay text={balanceUnavailable ? EM_DASH : formatMoney(summary?.ledger_net_assets)} />
          </span>
        </div>
      </div>

      <div className="ledger-pnl-conclusion-card__status" data-testid="ledger-pnl-conclusion-card-status">
        <span className="ledger-pnl-conclusion-card__status-badge">候选口径</span>
        <span className="ledger-pnl-conclusion-card__status-text">
          上一可用报告期 {previousReportDate ?? EM_DASH} · {statusTitle}
        </span>
      </div>
    </div>
  );
}

export function LedgerPnlAuditVerdict({
  audit,
  summary,
}: {
  audit: LedgerFunctionalAuditProps;
  summary: LedgerPnlSummaryPayload | undefined;
}) {
  const ledgerAuditState = buildLedgerAnalysisAuditState(audit);
  /** analysis 尚未返回或报错时保持审计条骨架/警示行为，不出现空结论卡。 */
  const hasLedgerAnalysisPayload = Boolean(audit.analysisEnvelope?.result);

  return (
      <section id={LEDGER_PNL_SECTION_IDS.verdict} className="ledger-pnl-section">
        <LedgerPnlSectionLead title="当日结论" note="总账候选口径" />
        {hasLedgerAnalysisPayload ? (
          <LedgerBusinessConclusionCard
            analysisPayload={audit.analysisEnvelope?.result}
            summary={summary}
            statusTitle={ledgerAuditState.title}
          />
        ) : null}
        <details className="ledger-pnl-verdict-audit-collapse" open={!hasLedgerAnalysisPayload}>
          <summary className="ledger-pnl-verdict-audit-collapse__summary">
            审计与证据详情
          </summary>
          <LedgerFunctionalAuditStrip {...audit} />
        </details>
      </section>
  );
}
