import { type PnlByBusinessDrilldownRecommendation, type PnlByBusinessInsightModel, type PnlByBusinessViewMode } from "./pnlByBusinessPageModel";
import { EM_DASH } from "../../utils/format";

export function PnlByBusinessInsightStrip({
  insight,
  viewMode,
  balanceSourcePending,
  manualAdjustmentAuditLoading,
  manualAdjustmentAuditUnavailable,
}: {
  insight: PnlByBusinessInsightModel;
  viewMode: PnlByBusinessViewMode;
  balanceSourcePending: boolean;
  manualAdjustmentAuditLoading: boolean;
  manualAdjustmentAuditUnavailable: boolean;
}) {
  const confidenceClass =
    insight.confidenceLabel === "可分析"
      ? "pnl-by-business-insight-strip__confidence--ready"
      : insight.confidenceLabel === "预警/降级"
        ? "pnl-by-business-insight-strip__confidence--warning"
        : "pnl-by-business-insight-strip__confidence--limited";
  const ftpStatusLabel =
    balanceSourcePending
      ? "FTP / 日均暂列（余额来源待核实）"
      : viewMode === "formal"
      ? "不适用（仅对账）"
      : viewMode === "monthly"
        ? insight.ftpAvailable
          ? "月度 FTP 可分析"
          : "月度 FTP 字段待核对"
        : insight.ftpAvailable
          ? insight.adbEvidenceStatus === "ytd_fallback"
            ? "FTP 可分析（YTD 日均）"
            : insight.adbEvidenceStatus === "loading"
              ? "FTP 可分析（ADB 复核中）"
              : "FTP 可分析"
          : insight.zeroAdbCount > 0
            ? insight.adbEvidenceStatus === "ytd_fallback"
              ? `${insight.zeroAdbCount} 项日均为0（源数据真零）`
              : `${insight.zeroAdbCount} 项日均为0`
            : insight.missingAdbCount > 0
              ? `${insight.missingAdbCount} 项缺日均`
              : `${insight.missingFtpFieldCount} 项缺 FTP 字段`;
  const ftpToneClass = insight.ftpAvailable && !balanceSourcePending
    ? "pnl-by-business-insight-strip__value--positive"
    : viewMode === "formal"
      ? ""
      : "pnl-by-business-insight-strip__value--warning";
  const formalToneClass =
    insight.formalUntracedCount > 0 ? "pnl-by-business-insight-strip__value--negative" : "";
  const dragToneClass =
    insight.topDragDisplay === EM_DASH
      ? "pnl-by-business-insight-strip__value--positive"
      : "pnl-by-business-insight-strip__value--negative";

  return (
    <section className="pnl-by-business-insight-strip" data-testid="pnl-by-business-insight-strip">
      <div className="pnl-by-business-insight-strip__lead">
        <span className={`pnl-by-business-insight-strip__confidence ${confidenceClass}`}>
          {insight.confidenceLabel}
        </span>
        <div>
          <strong>领导判断</strong>
          <span>{balanceSourcePending ? "先取得正确余额源表并重算，再判断收益率和 FTP 后收益。" : insight.nextStep}</span>
          {viewMode === "formal" ? <small>{insight.topShareDisplay}</small> : null}
        </div>
      </div>
      <div className="pnl-by-business-insight-strip__grid">
        <div>
          <small>最大拖累</small>
          <strong className={dragToneClass}>{insight.topDragLabel}</strong>
          <span>{insight.topDragDisplay}</span>
        </div>
        <div>
          <small>FTP / 日均</small>
          <strong className={ftpToneClass}>{ftpStatusLabel}</strong>
          <span>
            {viewMode === "formal"
              ? "手工调整不适用"
              : manualAdjustmentAuditLoading
                ? "手工调整审批读取中"
                : manualAdjustmentAuditUnavailable
                  ? "手工调整审批数量待核对"
                  : viewMode === "ytd"
                    ? `${insight.manualAdjustmentCount} 条所选报表日已批准调整`
                    : `${insight.manualAdjustmentCount} 条手工调整`}
          </span>
        </div>
        <div>
          <small>正式对账</small>
          <strong className={formalToneClass}>{insight.formalUntracedValueDisplay}</strong>
          <span>{insight.formalUntracedDisplay}</span>
        </div>
      </div>
      {insight.formalTriageDisplay ? (
        <div className="pnl-by-business-insight-strip__triage">{insight.formalTriageDisplay}</div>
      ) : null}
    </section>
  );
}

export function PnlByBusinessDrilldownRecommendationStrip({
  recommendation,
}: {
  recommendation: PnlByBusinessDrilldownRecommendation;
}) {
  return (
    <section
      className="pnl-by-business-drilldown-recommendation"
      data-testid="pnl-by-business-drilldown-recommendation"
    >
      <div className="pnl-by-business-drilldown-recommendation__lead">
        <span>{recommendation.priorityLabel}</span>
        <strong>下一步下钻</strong>
        <small>{recommendation.reasonLabel}</small>
      </div>
      <div className="pnl-by-business-drilldown-recommendation__grid">
        <div>
          <small>目标业务</small>
          <strong>{recommendation.targetBusinessLabel}</strong>
        </div>
        <div>
          <small>优先维度</small>
          <strong>{recommendation.dimensionLabel}</strong>
        </div>
        <div>
          <small>动作</small>
          <strong>{recommendation.actionLabel}</strong>
        </div>
        <div>
          <small>证据限制</small>
          <strong>{recommendation.evidenceLabel}</strong>
        </div>
      </div>
    </section>
  );
}
