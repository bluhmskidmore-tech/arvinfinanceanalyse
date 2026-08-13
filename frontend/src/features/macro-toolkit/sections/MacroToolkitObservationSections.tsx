import { ClockCircleOutlined, DatabaseOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Alert, Tag } from "antd";

import type {
  MacroToolkitAShareRiskPayload,
  MacroToolkitAnalysisPayload,
  MacroToolkitCapabilityResult,
  MacroToolkitIndicator,
  MacroToolkitSignalCard,
  MacroToolkitShadowPortfolioReport,
  MacroToolkitStrategySummary,
} from "../../../api/macroToolkitClient";
import { PageSectionLead } from "../../../components/page/PagePrimitives";
import { EM_DASH } from "../../../utils/format";
import { formatValue } from "../lib/macroToolkitCrisisSupport";
import { CapabilityResultCard } from "./MacroToolkitCapabilityCards";
import {
  formatObservationEvidence,
  formatObservationSignalStance,
  formatObservationSignalTitle,
  formatQueryError,
  formatRiskMetric,
  formatSignalCardScore,
  latestIndicatorDate,
  riskLevelColor,
  riskLevelTone,
  toneTagColor,
} from "../lib/macroToolkitDisplayFormat";
import { MetricTile } from "../lib/MacroToolkitStatusPrimitives";
import { compactText, statusColor, statusLabel } from "../lib/macroToolkitPanelShared";
import {
  shadowPortfolioObservationText,
  strategyObservationDetail,
  strategyObservationNote,
} from "../lib/macroToolkitStrategyDisplaySupport";
import { ScoreTrack } from "./MacroToolkitPrimitives";

function observationSignalRiskSummary(
  signal: MacroToolkitSignalCard | null,
  risk: MacroToolkitAShareRiskPayload | undefined,
  isLoading: boolean,
) {
  if (isLoading) {
    return "观察证据加载中，暂不形成合读判断。";
  }
  if (!signal && !risk) {
    return "主信号和风险预警待确认，当前不形成观察判断。";
  }
  if (!risk) {
    return "主信号已返回，风险证据延后确认；先不放大信号解释权重。";
  }
  if (!signal) {
    return "风险预警已返回，主信号待确认；先按风险边界观察。";
  }
  const signalTone = signal.tone;
  const riskTone = riskLevelTone(risk.risk_level);
  if (signalTone === "positive" && riskTone === "negative") {
    return "主信号偏正面，但市场踩踏风险偏高，先压低信号解释权重。";
  }
  if (signalTone === "negative" && riskTone === "positive") {
    return "主信号偏谨慎，市场踩踏风险暂低，继续观察是否修复。";
  }
  if (riskTone === "negative") {
    return "风险预警偏高，观察结论优先参考风险边界。";
  }
  return "主信号和风险预警未明显冲突，可继续观察证据延续性。";
}

export function ObservationSignalRiskComparison({
  signalCards,
  primarySignal,
  risk,
  isLoading = false,
}: {
  signalCards: MacroToolkitSignalCard[];
  primarySignal: MacroToolkitSignalCard | null;
  risk?: MacroToolkitAShareRiskPayload;
  isLoading?: boolean;
}) {
  const signal = primarySignal ?? signalCards.find((card) => card.score != null) ?? signalCards[0] ?? null;
  const signalTone = signal?.tone ?? "missing";
  const riskTone = risk ? riskLevelTone(risk.risk_level) : "missing";
  const riskScore = risk?.risk_score === null || risk?.risk_score === undefined ? EM_DASH : risk.risk_score;
  const riskSummary = risk?.summary || (isLoading ? "观察证据加载中" : "风险摘要待确认。");
  const signalEvidence = signal ? formatObservationEvidence(signal.evidence) : isLoading ? "观察证据加载中" : "主信号证据待确认";
  const riskContent = risk ? (
    <>
      <strong>{`${risk.risk_name} · ${riskScore}`}</strong>
      <p title={riskSummary}>{compactText(riskSummary, 68)}</p>
      <div className="macro-toolkit-observation-signal-risk__metrics">
        <span>
          <small>上涨家数</small>
          <b>{formatRiskMetric(risk.metrics.up_count)}</b>
        </span>
        <span>
          <small>跌停家数</small>
          <b>{formatRiskMetric(risk.metrics.limit_down_count)}</b>
        </span>
        <span>
          <small>成交额/20日</small>
          <b>{formatRiskMetric(risk.metrics.turnover_ratio_ma20, "ratio")}</b>
        </span>
      </div>
    </>
  ) : (
    <>
      <strong>{isLoading ? "观察证据加载中" : "完整分析后确认风险边界"}</strong>
      <p title={riskSummary}>
        {isLoading ? compactText(riskSummary, 68) : "需合并 A股宽度、跌停和成交压力。"}
      </p>
    </>
  );
  return (
    <div className="macro-toolkit-observation-signal-risk" aria-label="信号风险对照">
      <div className="macro-toolkit-observation-signal-risk__grid">
        <div className={`macro-toolkit-observation-signal-risk__lane macro-toolkit-observation-signal-risk__lane--${signalTone}`}>
          <div className="macro-toolkit-observation-signal-risk__lane-head">
            <span>核心信号</span>
            <Tag color={toneTagColor(signalTone)}>
              {signal ? formatObservationSignalStance(signal) : isLoading ? "加载中" : "待确认"}
            </Tag>
          </div>
          <strong>{signal ? formatObservationSignalTitle(signal) : isLoading ? "观察证据加载中" : "信号待确认"}</strong>
          <div className="macro-toolkit-observation-signal-risk__score">
            <b>{signal ? formatSignalCardScore(signal) : isLoading ? "加载中" : "待确认"}</b>
            <ScoreTrack score={signal?.score} />
          </div>
          <small title={signalEvidence}>{compactText(signalEvidence, 58)}</small>
        </div>

        <div className={`macro-toolkit-observation-signal-risk__lane macro-toolkit-observation-signal-risk__lane--${riskTone}`}>
          <div className="macro-toolkit-observation-signal-risk__lane-head">
            <span>风险预警</span>
            <div className="macro-toolkit-tag-row">
              <Tag color={risk ? statusColor(risk.status) : "default"}>
                {risk ? statusLabel(risk.status) : isLoading ? "加载中" : "证据缺口"}
              </Tag>
              {risk ? <Tag color={riskLevelColor(risk.risk_level)}>{risk.risk_name}</Tag> : null}
            </div>
          </div>
          {riskContent}
        </div>
      </div>

      <div className="macro-toolkit-observation-signal-risk__note">
        <span>观察判断</span>
        <strong>{observationSignalRiskSummary(signal, risk, isLoading)}</strong>
        <small>仅用于只读宏观观察，不作为正式投资信号。</small>
      </div>
    </div>
  );
}

export function InvestmentEvidenceSummary({
  indicators,
  strategySummaries,
  strategySupplyState,
  fullRealStrategyCount,
  partialRealStrategyCount,
  degradedStrategyCount,
  sampleStrategyCount,
  shadowPortfolioReport,
}: {
  indicators: MacroToolkitIndicator[];
  strategySummaries: MacroToolkitStrategySummary[];
  strategySupplyState: string;
  fullRealStrategyCount: number;
  partialRealStrategyCount: number;
  degradedStrategyCount: number;
  sampleStrategyCount: number;
  shadowPortfolioReport: MacroToolkitShadowPortfolioReport | null;
}) {
  const usableIndicators = indicators.filter((indicator) => indicator.quality === "ok");
  const missingIndicators = indicators.length - usableIndicators.length;
  const visibleIndicators = indicators.slice(0, 3);
  const shadowObservation = shadowPortfolioObservationText(shadowPortfolioReport);
  const shadowObservationDetail = shadowPortfolioReport
    ? "影子组合仅作观察边界，不进入正式投资信号。"
    : shadowObservation.detail;
  const bestStrategy = strategySummaries.find((strategy) => strategy.status === "complete") ?? strategySummaries[0] ?? null;
  return (
    <div className="macro-toolkit-investment-evidence" aria-label="投研证据摘要">
      <div className="macro-toolkit-investment-evidence__head">
        <div>
          <span>证据支撑</span>
          <strong>策略、指标和影子组合边界压缩成观察支撑</strong>
        </div>
        <Tag color="gold">非正式投资信号</Tag>
      </div>
      <div className="macro-toolkit-investment-evidence__lanes">
        <div className="macro-toolkit-investment-evidence__lane">
          <div className="macro-toolkit-investment-evidence__lane-head">
            <span>策略证据</span>
            <strong>{fullRealStrategyCount}/{strategySummaries.length || 0}</strong>
          </div>
          <div className="macro-toolkit-investment-evidence__metric-row">
            <MetricTile
              icon={<DatabaseOutlined />}
              label="真实供数"
              value={`${fullRealStrategyCount}/${strategySummaries.length || 0}`}
              detail={strategyObservationDetail(
                strategySummaries,
                fullRealStrategyCount,
                partialRealStrategyCount,
                degradedStrategyCount,
                sampleStrategyCount,
              )}
              tone={fullRealStrategyCount > 0 ? "neutral" : "missing"}
              detailMaxLength={42}
            />
            <MetricTile
              icon={<SafetyCertificateOutlined />}
              label={shadowObservation.label}
              value={shadowObservation.value}
              detail={shadowObservationDetail}
              tone={shadowObservation.tone}
              detailMaxLength={42}
            />
          </div>
          <div className="macro-toolkit-investment-evidence__note">
            <span>{bestStrategy?.label ?? "策略摘要"}</span>
            <small>{strategyObservationNote(bestStrategy, strategySupplyState)}</small>
          </div>
        </div>
        <div className="macro-toolkit-investment-evidence__lane">
          <div className="macro-toolkit-investment-evidence__lane-head">
            <span>指标证据</span>
            <strong>{usableIndicators.length}/{indicators.length || 0}</strong>
          </div>
          <div className="macro-toolkit-investment-evidence__metric-row">
            <MetricTile
              icon={<DatabaseOutlined />}
              label="数据源已确认"
              value={missingIndicators ? "待补齐" : "已确认"}
              detail={missingIndicators ? `${missingIndicators} 个指标待补齐。` : "当前观察指标均可用。"}
              tone={missingIndicators ? "missing" : "neutral"}
              detailMaxLength={42}
            />
            <MetricTile
              icon={<ClockCircleOutlined />}
              label="最新值日期"
              value={latestIndicatorDate(indicators)}
              detail="观察指标的最新值日期。"
              tone="neutral"
              detailMaxLength={42}
            />
          </div>
          <div className="macro-toolkit-investment-evidence__indicators" aria-label="观察指标摘要">
            {visibleIndicators.map((indicator) => (
              <span key={indicator.alias}>
                <strong>{indicator.label}</strong>
                <small>
                  {formatValue(indicator.latest_value, indicator.unit)} · {indicator.latest_date ?? EM_DASH}
                </small>
              </span>
            ))}
          </div>
        </div>
        <div className="macro-toolkit-investment-evidence__note macro-toolkit-investment-evidence__note--boundary">
          <span>观察边界</span>
          <small>完整审计留在工具页；本页只保留证据支撑，不作为正式投资信号。</small>
        </div>
      </div>
    </div>
  );
}

export function MacroToolkitInvestmentEvidenceSection({
  analysis,
  showOperations,
  selectedEvidenceHref,
  strategySummaries,
  strategySupplyState,
  fullRealStrategyCount,
  partialRealStrategyCount,
  degradedStrategyCount,
  sampleStrategyCount,
  shadowPortfolioReport,
  strategyQuery,
}: {
  analysis: MacroToolkitAnalysisPayload;
  showOperations: boolean;
  selectedEvidenceHref: string | null;
  strategySummaries: MacroToolkitStrategySummary[];
  strategySupplyState: string;
  fullRealStrategyCount: number;
  partialRealStrategyCount: number;
  degradedStrategyCount: number;
  sampleStrategyCount: number;
  shadowPortfolioReport: MacroToolkitShadowPortfolioReport | null;
  strategyQuery: { isFetching: boolean; isError: boolean; error: unknown };
}) {
  return (
    <section
      id="macro-toolkit-strategy-detail"
      data-testid="macro-toolkit-investment-evidence-detail"
      className={`macro-toolkit-section ${
        selectedEvidenceHref === "#macro-toolkit-strategy-detail" ? "macro-toolkit-section--audit-focus" : ""
      }`}
    >
      <PageSectionLead
        eyebrow="交叉验证"
        title="投研证据摘要"
        description="策略链路、影子组合边界与指标覆盖的观察结论。"
      />
      <InvestmentEvidenceSummary
        indicators={analysis.indicators}
        strategySummaries={strategySummaries}
        strategySupplyState={strategySupplyState}
        fullRealStrategyCount={fullRealStrategyCount}
        partialRealStrategyCount={partialRealStrategyCount}
        degradedStrategyCount={degradedStrategyCount}
        sampleStrategyCount={sampleStrategyCount}
        shadowPortfolioReport={shadowPortfolioReport}
      />
      {!showOperations && strategyQuery.isFetching && !strategySummaries.length ? (
        <Alert
          type="info"
          showIcon
          message="策略证据正在生成"
          description="核心信号已先返回；完整策略证据打开完整分析后确认。"
        />
      ) : strategyQuery.isError ? (
        <Alert type="warning" showIcon message="策略证据暂不可用" description={formatQueryError(strategyQuery.error)} />
      ) : null}
    </section>
  );
}

export function MacroToolkitObservationDecisionSummary({
  decisionSummaryResult,
  isCoreAnalysis,
  analysisBasis,
}: {
  decisionSummaryResult: MacroToolkitCapabilityResult | null;
  isCoreAnalysis: boolean;
  analysisBasis?: string | null;
}) {
  return (
      <div
        className="macro-toolkit-observation-decision"
        data-testid="macro-observation-decision-summary"
        aria-label="宏观决策摘要主结论"
      >
        {analysisBasis === "mock" ? (
          <Alert
            type="warning"
            showIcon
            data-testid="macro-observation-decision-mock-flag"
            message="模拟数据"
            description="当前决策摘要由前端模拟数据生成，仅用于界面演示，不代表宏观分析结论。"
          />
        ) : null}
        {decisionSummaryResult ? (
          <>
            <CapabilityResultCard result={decisionSummaryResult} />
            {decisionSummaryResult.warnings.length ? (
              <Alert
                type="warning"
                showIcon
                message="决策摘要限制"
                description={decisionSummaryResult.warnings.join(" / ")}
              />
            ) : null}
          </>
        ) : (
          <Alert
            type="info"
            showIcon
            message="宏观决策摘要暂未返回"
            description={
              isCoreAnalysis
                ? "核心分析已先返回；决策摘要需打开完整分析后确认。"
                : "后端未返回决策摘要结果，本页不推导宏观结论。"
            }
          />
        )}
      </div>
  );
}

export function MacroToolkitObservationComparisonSection({
  signalCards,
  primarySignal,
  risk,
  isLoading = false,
}: {
  signalCards: MacroToolkitSignalCard[];
  primarySignal: MacroToolkitSignalCard | null;
  risk?: MacroToolkitAShareRiskPayload;
  isLoading?: boolean;
}) {
  return (
    <section className="macro-toolkit-section">
      <PageSectionLead
        eyebrow="对照"
        title="信号风险对照"
        description="把主信号和市场踩踏风险放在同一张观察卡里，先看一致性，再看证据边界。"
      />
      <ObservationSignalRiskComparison
        signalCards={signalCards}
        primarySignal={primarySignal}
        risk={risk}
        isLoading={isLoading}
      />
    </section>
  );
}
