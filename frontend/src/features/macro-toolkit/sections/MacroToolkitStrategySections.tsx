import {
  ClockCircleOutlined,
  DatabaseOutlined,
  InfoCircleOutlined,
  LineChartOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Alert, Button, Tag } from "antd";

import type {
  MacroToolkitChoiceStockRefreshStatus,
  MacroToolkitMacroEtfStrategySnapshot,
  MacroToolkitShadowPortfolioReport,
  MacroToolkitStrategySummary,
} from "../../../api/macroToolkitClient";
import { PageSectionLead } from "../../../components/page/PagePrimitives";
import { formatNumberValue } from "../lib/macroToolkitCrisisSupport";
import { formatQueryError } from "../lib/macroToolkitDisplayFormat";
import { MetricTile, compactText, statusColor, statusLabel } from "../lib/macroToolkitPanelShared";
import {
  admissionCriterionText,
  choiceStockRefreshDetail,
  choiceStockRefreshValue,
  choiceStockTableDetail,
  choiceStockTableSummary,
  costResultText,
  dualFrequencyAlignmentText,
  dualFrequencyCount,
  dualFrequencyHistory,
  dualFrequencyMultiplier,
  dualFrequencyRatio,
  dualFrequencySourceText,
  dualFrequencyStatus,
  dualFrequencyStatusText,
  dualFrequencyUniqueTexts,
  dualFrequencyVersionText,
  formatPlainRatio,
  formatSignedRatio,
  periodChipText,
  portfolioConstraintText,
  portfolioWeightsText,
  shadowPortfolioAdmissionText,
  shadowPortfolioCostGateText,
  shadowPortfolioCostModelText,
  shadowPortfolioFactorWindowText,
  shadowPortfolioHoldingDiff,
  shadowPortfolioObservationText,
  shadowPortfolioPeriodRangeText,
  shadowPortfolioPeriodRows,
  shadowPortfolioPeriodWinLossText,
  shadowPortfolioReviewAction,
  shadowPortfolioUnavailableDescription,
  shadowPortfolioWarningText,
  strategyDataStatus,
  strategyObservationDetail,
  strategyObservationNote,
  strategyScalarText,
  strategyTraceList,
} from "../lib/macroToolkitStrategyDisplaySupport";

export function ShadowPortfolioEvidencePack({ report }: { report: MacroToolkitShadowPortfolioReport }) {
  const candidates = report.portfolios.filter((portfolio) => portfolio.role === "shadow_candidate");
  if (!candidates.length) {
    return null;
  }
  const warnings = Array.from(new Set(report.warnings.map(shadowPortfolioWarningText).filter(Boolean)));
  return (
    <div className="macro-toolkit-shadow-evidence" aria-label="影子组合准入证据包">
      <div className="macro-toolkit-capability-result-head">
        <span>准入证据包</span>
        <Tag color="default">只读评估</Tag>
      </div>
      <div className="macro-toolkit-shadow-evidence__facts">
        <span>
          <b>规则版本</b>
          {report.rule_version}
        </span>
        <span>
          <b>回测窗口</b>
          {shadowPortfolioFactorWindowText(report)}
        </span>
        <span>
          <b>成本模型</b>
          {shadowPortfolioCostModelText(report)}
        </span>
        <span>
          <b>数据来源</b>
          {report.tables_used.join(" / ") || "数据表缺失"}
        </span>
      </div>
      <div className="macro-toolkit-shadow-evidence__actions">
        {candidates.map((candidate) => (
          <span key={`evidence-${candidate.key}`}>
            <b>评审动作</b>
            {candidate.label}：{shadowPortfolioReviewAction(candidate)}
          </span>
        ))}
      </div>
      <div className="macro-toolkit-shadow-evidence__warnings">
        {(warnings.length ? warnings : ["无额外告警。"]).map((warning) => (
          <span key={warning}>{warning}</span>
        ))}
      </div>
    </div>
  );
}

export function ShadowPortfolioReview({ report }: { report: MacroToolkitShadowPortfolioReport }) {
  const reference =
    report.portfolios.find((portfolio) => portfolio.role === "production_reference") ?? report.portfolios[0];
  const candidates = report.portfolios.filter((portfolio) => portfolio.role === "shadow_candidate");
  if (!reference || !candidates.length) {
    return null;
  }
  return (
    <div className="macro-toolkit-shadow-review" aria-label="影子组合稳健性审查">
      {candidates.map((candidate) => {
        const rows = shadowPortfolioPeriodRows(report, candidate);
        const holdingDiff = shadowPortfolioHoldingDiff(reference, candidate);
        return (
          <div className="macro-toolkit-shadow-review__item" key={`review-${candidate.key}`}>
            <div className="macro-toolkit-capability-result-head">
              <span>稳健性审查</span>
              <Tag color="blue">{candidate.label}</Tag>
            </div>
            <div className="macro-toolkit-shadow-review__facts">
              <span>
                <b>周期胜负</b>
                {shadowPortfolioPeriodWinLossText(rows)}
              </span>
              <span>
                <b>区间分布</b>
                {shadowPortfolioPeriodRangeText(rows)}
              </span>
              <span>
                <b>成本后结论</b>
                {shadowPortfolioCostGateText(reference, candidate)}
              </span>
              <span>
                <b>准入结论</b>
                {shadowPortfolioAdmissionText(candidate)}
              </span>
              <span>
                <b>持仓差异</b>
                {holdingDiff.overlapText}
              </span>
            </div>
            {candidate.admission?.criteria.length ? (
              <div className="macro-toolkit-shadow-review__criteria">
                {candidate.admission.criteria.map((criterion) => {
                  const thresholdText = admissionCriterionText(criterion.threshold);
                  return (
                    <div
                      className={`macro-toolkit-shadow-review__criterion ${
                        criterion.passed
                          ? "macro-toolkit-shadow-review__criterion--pass"
                          : "macro-toolkit-shadow-review__criterion--fail"
                      }`}
                      key={`${candidate.key}-${criterion.key}`}
                    >
                      <b>{criterion.label}</b>
                      {criterion.passed ? "通过" : "未通过"}
                      {thresholdText ? ` · ${thresholdText}` : ""}
                    </div>
                  );
                })}
              </div>
            ) : null}
            {rows.length ? (
              <div className="macro-toolkit-shadow-review__periods">
                {rows.slice(-4).map((row) => (
                  <span key={`${candidate.key}-${row.start_date}-${row.end_date}`}>{periodChipText(row)}</span>
                ))}
              </div>
            ) : null}
            <div className="macro-toolkit-shadow-holdings macro-toolkit-shadow-holdings--diff">
              <span>{holdingDiff.candidateOnlyText}</span>
              <span>{holdingDiff.referenceOnlyText}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function DualFrequencyRiskBudgetPanel({
  snapshot,
}: {
  snapshot: MacroToolkitMacroEtfStrategySnapshot;
}) {
  const candidate = snapshot.dual_frequency;
  if (!candidate) {
    return (
      <div
        className="macro-toolkit-strategy-observation macro-toolkit-dual-frequency"
        aria-label="双频风险预算候选"
      >
        <div className="macro-toolkit-strategy-observation__head">
          <div>
            <span>双频风险预算（候选）</span>
            <strong>候选快照未返回</strong>
          </div>
          <Tag color="gold">不进入下单</Tag>
        </div>
        <Alert
          type="warning"
          showIcon
          message="双频候选暂不可用"
          description="策略摘要未返回双频状态，页面不会用零值或演示值补位。"
        />
        <div className="macro-toolkit-strategy-observation__note">
          <span>观察用途</span>
          <small>非正式投资信号，不替换正式策略，不进入下单。</small>
        </div>
      </div>
    );
  }

  const boundaryConfirmed =
    snapshot.boundary === "observation_only" &&
    snapshot.execution_enabled === false &&
    candidate.boundary === "observation_only" &&
    candidate.execution_enabled === false;
  const slowCap = boundaryConfirmed ? candidate.slow?.cap : null;
  const fastState = candidate.fast?.state ?? null;
  const fastMultiplier = boundaryConfirmed ? candidate.fast?.multiplier : null;
  const preSurvivalTarget = boundaryConfirmed ? candidate.pre_survival_target_total_weight : null;
  const finalTarget = boundaryConfirmed ? candidate.final_target_total_weight : null;
  const survivalStatus = candidate.survival?.status ?? candidate.survival?.state ?? "not_evaluated";
  const status = dualFrequencyStatus(candidate);
  const dataStatus = candidate.data_status;
  const history = dualFrequencyHistory(candidate);
  const asOfDate =
    history?.effective_as_of_date ??
    history?.latest_trade_date ??
    dataStatus?.latest_trade_date ??
    candidate.fast?.signal_date ??
    candidate.as_of_date ??
    snapshot.as_of_date ??
    null;
  const sourceText = dualFrequencySourceText(candidate);
  const versionText = dualFrequencyVersionText(candidate);
  const warnings = dualFrequencyUniqueTexts(candidate.warnings ?? []);
  const amountSource = history?.sources?.market_amount;
  const amountSampleText =
    amountSource?.valid_amount_observation_count != null ||
    amountSource?.null_amount_observation_count != null
      ? `有效 ${dualFrequencyCount(amountSource?.valid_amount_observation_count)} · 空值 ${dualFrequencyCount(amountSource?.null_amount_observation_count)}`
      : "成交额样本计数未返回";
  const statusText = boundaryConfirmed ? dualFrequencyStatusText(status) : "边界待确认";
  const fastStateText = fastState ? dualFrequencyStatusText(fastState) : "待确认";
  const survivalText = dualFrequencyStatusText(survivalStatus);
  const survivalDate = candidate.survival?.signal_date ?? null;
  const survivalDetail =
    survivalStatus === "not_evaluated"
      ? "缺少权威组合净值或状态，生存层暂未评估。"
      : survivalDate
        ? `生存层数据日 ${survivalDate}`
        : "生存层状态由后端只读候选返回。";
  const headline =
    fastState && slowCap != null
      ? `快频${fastStateText}，慢频上限 ${dualFrequencyRatio(slowCap)}`
      : "快频状态或慢频上限待确认";
  const qualityDetail = [
    statusText,
    history?.status ? `历史 ${dualFrequencyStatusText(history.status)}` : "",
    dataStatus?.usable_row_count != null ? `可用 ${dataStatus.usable_row_count} 行` : "",
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div
      className="macro-toolkit-strategy-observation macro-toolkit-dual-frequency"
      aria-label="双频风险预算候选"
    >
      <div className="macro-toolkit-strategy-observation__head">
        <div>
          <span>双频风险预算（候选）</span>
          <strong>{headline}</strong>
        </div>
        <div className="macro-toolkit-tag-row">
          <Tag color={boundaryConfirmed ? statusColor(status) : "red"}>{statusText}</Tag>
          <Tag color="gold">不进入下单</Tag>
        </div>
      </div>
      {!boundaryConfirmed ? (
        <Alert
          type="error"
          showIcon
          message="只读边界未确认"
          description="候选目标值已隐藏；确认 observation_only 且执行关闭后才展示。"
        />
      ) : null}
      <div className="macro-toolkit-strategy-observation__grid">
        <MetricTile
          icon={<ThunderboltOutlined />}
          label="快频状态"
          value={fastStateText}
          detail={
            candidate.fast?.signal_date
              ? `信号数据日 ${candidate.fast.signal_date}`
              : "快频信号日期未返回。"
          }
          tone={fastState ? "neutral" : "missing"}
          testId="macro-toolkit-dual-fast-state"
          detailMaxLength={44}
        />
        <MetricTile
          icon={<SafetyCertificateOutlined />}
          label="慢频上限"
          value={dualFrequencyRatio(slowCap)}
          detail="沿用宏观 ETF 慢频仓位上限。"
          tone={slowCap == null ? "missing" : "neutral"}
          testId="macro-toolkit-dual-slow-cap"
          detailMaxLength={44}
        />
        <MetricTile
          icon={<LineChartOutlined />}
          label="快频乘数"
          value={dualFrequencyMultiplier(fastMultiplier)}
          detail="进攻为 1.00，防守保护按后端候选规则返回。"
          tone={fastMultiplier == null ? "missing" : "neutral"}
          testId="macro-toolkit-dual-fast-multiplier"
          detailMaxLength={44}
        />
        <MetricTile
          icon={<InfoCircleOutlined />}
          label="生存层前目标"
          value={dualFrequencyRatio(preSurvivalTarget)}
          detail="生存层应用前的只读候选预算。"
          tone={preSurvivalTarget == null ? "missing" : "neutral"}
          testId="macro-toolkit-dual-pre-survival"
          detailMaxLength={44}
        />
        <MetricTile
          icon={<WarningOutlined />}
          label="生存层"
          value={survivalText}
          detail={survivalDetail}
          tone={survivalStatus === "not_evaluated" ? "missing" : "neutral"}
          testId="macro-toolkit-dual-survival"
          detailMaxLength={44}
        />
        <MetricTile
          icon={<SafetyCertificateOutlined />}
          label="最终目标"
          value={dualFrequencyRatio(finalTarget)}
          detail={
            finalTarget == null
              ? "生存层未完成，最终目标保持为空。"
              : "完整候选目标，仍不进入下单。"
          }
          tone={finalTarget == null ? "missing" : "neutral"}
          testId="macro-toolkit-dual-final-target"
          detailMaxLength={44}
        />
      </div>
      <div className="macro-toolkit-strategy-trace" aria-label="双频风险预算证据">
        <span>
          <b>观察日</b>
          {candidate.as_of_date ?? snapshot.as_of_date ?? "日期未返回"}
        </span>
        <span>
          <b>数据日</b>
          {asOfDate ? `${asOfDate} · ${dualFrequencyAlignmentText(dataStatus?.as_of_alignment)}` : "日期未返回"}
        </span>
        <span title={sourceText}>
          <b>来源</b>
          {sourceText}
        </span>
        <span>
          <b>质量</b>
          {qualityDetail || "质量未返回"}
        </span>
        <span title={versionText}>
          <b>版本</b>
          {compactText(versionText, 140)}
        </span>
      </div>
      <div className="macro-toolkit-strategy-observation__note">
        <span>成交额口径</span>
        <small>成交额采用全 A 股日汇总代理，非沪深300成分成交额；源单位未确认，仅使用无量纲量比。</small>
        <small>{amountSampleText}</small>
      </div>
      {warnings.length ? (
        <div className="macro-toolkit-strategy-warnings" aria-label="双频风险预算告警">
          <Alert
            type="warning"
            showIcon
            message={`候选告警 ${warnings.length} 项`}
            description={
              <span title={warnings.join(" | ")}>{compactText(warnings.join("；"), 180)}</span>
            }
          />
        </div>
      ) : null}
      <div className="macro-toolkit-strategy-observation__note">
        <span>观察用途</span>
        <small>非正式投资信号，不替换正式策略，不进入下单。</small>
      </div>
    </div>
  );
}

export function StrategyObservationSummary({
  strategySummaries,
  strategySupplyState,
  fullRealStrategyCount,
  partialRealStrategyCount,
  degradedStrategyCount,
  sampleStrategyCount,
  shadowPortfolioReport,
}: {
  strategySummaries: MacroToolkitStrategySummary[];
  strategySupplyState: string;
  fullRealStrategyCount: number;
  partialRealStrategyCount: number;
  degradedStrategyCount: number;
  sampleStrategyCount: number;
  shadowPortfolioReport: MacroToolkitShadowPortfolioReport | null;
}) {
  const shadowObservation = shadowPortfolioObservationText(shadowPortfolioReport);
  const bestStrategy = strategySummaries.find((strategy) => strategy.status === "complete") ?? strategySummaries[0] ?? null;
  return (
    <div className="macro-toolkit-strategy-observation" aria-label="策略证据摘要">
      <div className="macro-toolkit-strategy-observation__head">
        <div>
          <span>策略证据摘要</span>
          <strong>只保留观察结论，完整审计留在工具页</strong>
        </div>
        <Tag color="gold">非正式投资信号</Tag>
      </div>
      <div className="macro-toolkit-strategy-observation__grid">
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
          detailMaxLength={44}
        />
        <MetricTile
          icon={<SafetyCertificateOutlined />}
          label={shadowObservation.label}
          value={shadowObservation.value}
          detail={shadowObservation.detail}
          tone={shadowObservation.tone}
          detailMaxLength={44}
        />
        <MetricTile
          icon={<InfoCircleOutlined />}
          label="投研使用"
          value="观察"
          detail="不自动替换正式策略，不作为正式投资信号。"
          tone="neutral"
          detailMaxLength={44}
        />
      </div>
      <div className="macro-toolkit-strategy-observation__note">
        <span>{bestStrategy?.label ?? "策略摘要"}</span>
        <small>{strategyObservationNote(bestStrategy, strategySupplyState)}</small>
      </div>
    </div>
  );
}

export function ShadowPortfolioReportPanel({ report }: { report: MacroToolkitShadowPortfolioReport | null }) {
  if (!report) {
    return null;
  }
  if (report.status !== "complete") {
    return (
      <div className="macro-toolkit-shadow-report macro-toolkit-shadow-report--warning" aria-label="影子组合报告">
        <Alert
          type="warning"
          showIcon
          message="影子组合报告暂不可用"
          description={shadowPortfolioUnavailableDescription(report.warnings)}
        />
        {report.warnings.length ? (
          <div className="macro-toolkit-tag-row">
            {report.warnings.map((warning) => (
              <Tag color="gold" key={warning}>
                {warning}
              </Tag>
            ))}
          </div>
        ) : null}
      </div>
    );
  }
  return (
    <div className="macro-toolkit-shadow-report" aria-label="影子组合报告">
      <div className="macro-toolkit-shadow-report__head">
        <div>
          <span>只读影子组合</span>
          <strong>{report.as_of_date ?? "日期缺失"}</strong>
          <small>
            {report.completed_periods} 个完成调仓周期 / {report.benchmark?.label ?? "基准缺失"}
          </small>
        </div>
        <div className="macro-toolkit-tag-row">
          <Tag color="blue">{report.rule_version}</Tag>
          {report.warnings.map((warning) => (
            <Tag color="gold" key={warning}>
              {warning}
            </Tag>
          ))}
        </div>
      </div>
      <div className="macro-toolkit-shadow-report__grid">
        {report.portfolios.map((portfolio) => (
          <div className="macro-toolkit-shadow-card" key={portfolio.key}>
            <div className="macro-toolkit-capability-result-head">
              <span>{portfolio.role === "shadow_candidate" ? "影子观察" : "正式参照"}</span>
              <Tag color={portfolio.role === "shadow_candidate" ? "blue" : "default"}>{portfolio.label}</Tag>
            </div>
            <div className="macro-toolkit-shadow-card__metrics">
              <MetricTile label="总收益" value={formatSignedRatio(portfolio.total_return)} detail="不含生产替换" />
              <MetricTile label="超额" value={formatSignedRatio(portfolio.excess_return)} detail="相对因子池等权" />
              <MetricTile label="最大回撤" value={formatSignedRatio(portfolio.max_drawdown)} detail={`胜率 ${formatPlainRatio(portfolio.win_rate)}`} />
              <MetricTile label="估值" value={`PE ${formatNumberValue(portfolio.average_pe)}`} detail={`PB ${formatNumberValue(portfolio.average_pb)}`} />
            </div>
            <div className="macro-toolkit-strategy-trace">
              <span>
                <b>权重</b>
                {portfolioWeightsText(portfolio)}
              </span>
              <span>
                <b>约束</b>
                {portfolioConstraintText(portfolio)}
              </span>
              <span>
                <b>换手</b>
                {formatPlainRatio(portfolio.average_turnover)}
              </span>
              <span>
                <b>20bp</b>
                {costResultText(portfolio, 20)}
              </span>
              <span>
                <b>50bp</b>
                {costResultText(portfolio, 50)}
              </span>
            </div>
            {portfolio.latest_holdings.length ? (
              <div className="macro-toolkit-shadow-holdings">
                {portfolio.latest_holdings.slice(0, 5).map((holding) => (
                  <span key={`${portfolio.key}-${holding.stock_code}`}>
                    {holding.rank}. {holding.stock_code} · {holding.industry}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>
      <ShadowPortfolioReview report={report} />
      <ShadowPortfolioEvidencePack report={report} />
    </div>
  );
}

export function StrategySummaryCard({ strategy }: { strategy: MacroToolkitStrategySummary }) {
  const metric = strategy.primary_metric;
  const dataStatus = strategyDataStatus(strategy);
  const priceSource =
    typeof strategy.result.price_source === "string" && strategy.result.price_source.trim()
      ? strategy.result.price_source
      : "价格来源缺失";
  const factorSource =
    typeof strategy.result.factor_source === "string" && strategy.result.factor_source.trim()
      ? strategy.result.factor_source
      : "因子来源缺失";
  const warnings = strategy.warnings;
  const sourceVersions = strategyTraceList(strategy.result.source_versions);
  const vendorVersions = strategyTraceList(strategy.result.vendor_versions);
  const factorSourceVersions = strategyTraceList(strategy.result.factor_source_versions);
  const factorVendorVersions = strategyTraceList(strategy.result.factor_vendor_versions);
  const factorRuleVersions = strategyTraceList(strategy.result.factor_rule_versions);
  const factorRunIds = strategyTraceList(strategy.result.factor_run_ids);
  const missingFactorInputs = strategyTraceList(strategy.result.missing_factor_inputs, Number.POSITIVE_INFINITY);
  const asOfDate = strategyScalarText(strategy.result.as_of_date);
  const factorAsOfDate = strategyScalarText(strategy.result.factor_as_of_date);
  const factorDateStatus = strategyScalarText(strategy.result.factor_date_status);

  return (
    <div className={`macro-toolkit-strategy-card macro-toolkit-strategy-card--${strategy.tone}`}>
      <div className="macro-toolkit-capability-result-head">
        <span>{strategy.group}</span>
        <Tag color={statusColor(strategy.status)}>{statusLabel(strategy.status)}</Tag>
      </div>
      <strong>{strategy.label}</strong>
      <div className="macro-toolkit-strategy-metric">
        <span>{metric?.label ?? "状态"}</span>
        <b>{metric ? `${metric.value}${metric.unit}` : statusLabel(strategy.status)}</b>
      </div>
      <small>{strategy.evidence.slice(0, 2).join(" / ") || "暂无证据"}</small>
      <div className="macro-toolkit-strategy-trace" aria-label={`${strategy.label}策略追踪`}>
        <span>
          <b>数据状态</b>
          {statusLabel(dataStatus)} <em>{dataStatus}</em>
        </span>
        <span>
          <b>价格</b>
          {priceSource}
        </span>
        <span>
          <b>因子</b>
          {factorSource}
        </span>
        {asOfDate ? (
          <span>
            <b>行情日</b>
            {asOfDate}
          </span>
        ) : null}
        {factorAsOfDate ? (
          <span>
            <b>因子日</b>
            {factorAsOfDate}
            {factorDateStatus ? ` · ${statusLabel(factorDateStatus)}` : ""}
          </span>
        ) : null}
        {sourceVersions ? (
          <span>
            <b>价格版本</b>
            {sourceVersions}
          </span>
        ) : null}
        {vendorVersions ? (
          <span>
            <b>行情厂商</b>
            {vendorVersions}
          </span>
        ) : null}
        {factorSourceVersions ? (
          <span>
            <b>因子版本</b>
            {factorSourceVersions}
          </span>
        ) : null}
        {factorVendorVersions ? (
          <span>
            <b>因子厂商</b>
            {factorVendorVersions}
          </span>
        ) : null}
        {factorRuleVersions ? (
          <span>
            <b>因子规则</b>
            {factorRuleVersions}
          </span>
        ) : null}
        {factorRunIds ? (
          <span>
            <b>因子运行</b>
            {factorRunIds}
          </span>
        ) : null}
        {missingFactorInputs ? (
          <span>
            <b>缺失输入</b>
            {missingFactorInputs}
          </span>
        ) : null}
        {warnings.length ? (
          <div className="macro-toolkit-strategy-warnings">
            {warnings.map((warning) => (
              <Tag color="gold" key={warning}>
                {warning}
              </Tag>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function MacroToolkitStrategySection({
  showOperations,
  selectedEvidenceHref,
  strategyDescription,
  choiceStockRefresh,
  isRefreshingChoiceStock,
  isOperationActionBusy,
  refreshChoiceStock,
  stockRefreshResult,
  stockRefreshError,
  strategySupplyState,
  fullRealStrategyCount,
  partialRealStrategyCount,
  degradedStrategyCount,
  sampleStrategyCount,
  strategySummaries,
  shadowPortfolioReport,
  strategyQuery,
  macroEtfStrategy,
}: {
  showOperations: boolean;
  selectedEvidenceHref: string | null;
  strategyDescription: string;
  choiceStockRefresh: MacroToolkitChoiceStockRefreshStatus | null;
  isRefreshingChoiceStock: boolean;
  isOperationActionBusy: boolean;
  refreshChoiceStock: () => Promise<void>;
  stockRefreshResult: string | null;
  stockRefreshError: string | null;
  strategySupplyState: string;
  fullRealStrategyCount: number;
  partialRealStrategyCount: number;
  degradedStrategyCount: number;
  sampleStrategyCount: number;
  strategySummaries: MacroToolkitStrategySummary[];
  shadowPortfolioReport: MacroToolkitShadowPortfolioReport | null;
  strategyQuery: { isFetching: boolean; isError: boolean; error: unknown };
  macroEtfStrategy: MacroToolkitMacroEtfStrategySnapshot | null;
}) {
  return (
    <section
      id="macro-toolkit-strategy-detail"
      data-testid="macro-toolkit-strategy-detail"
      className={`macro-toolkit-section ${
        selectedEvidenceHref === "#macro-toolkit-strategy-detail" ? "macro-toolkit-section--audit-focus" : ""
      }`}
    >
      <PageSectionLead eyebrow="策略" title="策略展示" description={strategyDescription} />
      {showOperations ? (
        <div className="macro-toolkit-stock-refresh-panel">
          <div className="macro-toolkit-cffex-metrics">
            <MetricTile
              label="股票历史"
              value={choiceStockRefresh?.daily_observation?.stock_count ?? 0}
              detail={choiceStockTableDetail(choiceStockRefresh?.daily_observation, "latest_trade_date")}
            />
            <MetricTile
              label="完整因子"
              value={choiceStockRefresh?.factor_snapshot?.stock_count ?? 0}
              detail={choiceStockTableDetail(choiceStockRefresh?.factor_snapshot, "as_of_date")}
            />
            <MetricTile
              label="刷新状态"
              value={choiceStockRefreshValue(choiceStockRefresh?.refresh, choiceStockRefresh?.permission)}
              detail={choiceStockRefreshDetail(choiceStockRefresh?.refresh, choiceStockRefresh?.permission)}
            />
          </div>
          <div className="macro-toolkit-cffex-actions">
            <Button
              icon={<ReloadOutlined />}
              loading={isRefreshingChoiceStock}
              disabled={isOperationActionBusy && !isRefreshingChoiceStock}
              onClick={() => void refreshChoiceStock()}
              aria-label="刷新股票策略明细"
            >
              刷新股票策略明细
            </Button>
            {stockRefreshResult ? <Alert type="success" showIcon message={stockRefreshResult} /> : null}
            {stockRefreshError ? <Alert type="error" showIcon message={stockRefreshError} /> : null}
          </div>
        </div>
      ) : null}
      <div className="macro-toolkit-strategy-supply-strip" aria-label="策略供数闭环">
        <span className="macro-toolkit-strategy-supply-label">
          <DatabaseOutlined />
          策略供数闭环
        </span>
        {strategySupplyState === "loaded" ? (
          <>
            <span>
              <DatabaseOutlined />
              完整链路 {fullRealStrategyCount}/{strategySummaries.length}
            </span>
            <span>
              <SafetyCertificateOutlined />
              部分链路 {partialRealStrategyCount}
            </span>
            <span>
              <SafetyCertificateOutlined />
              降级 {degradedStrategyCount}
            </span>
            <span>
              <SafetyCertificateOutlined />
              样例 {sampleStrategyCount}
            </span>
          </>
        ) : (
          <span>
            <ClockCircleOutlined />
            策略供数 {statusLabel(strategySupplyState)}
          </span>
        )}
        <span>
          <ClockCircleOutlined />
          股票历史 {choiceStockTableSummary(choiceStockRefresh?.daily_observation, "latest_trade_date")}
        </span>
        <span>
          <ClockCircleOutlined />
          因子快照 {choiceStockTableSummary(choiceStockRefresh?.factor_snapshot, "as_of_date")}
        </span>
      </div>
      {!showOperations ? (
        <StrategyObservationSummary
          strategySummaries={strategySummaries}
          strategySupplyState={strategySupplyState}
          fullRealStrategyCount={fullRealStrategyCount}
          partialRealStrategyCount={partialRealStrategyCount}
          degradedStrategyCount={degradedStrategyCount}
          sampleStrategyCount={sampleStrategyCount}
          shadowPortfolioReport={shadowPortfolioReport}
        />
      ) : (
        <>
          <ShadowPortfolioReportPanel report={shadowPortfolioReport} />
          {strategySummaries.length ? (
            <div className="macro-toolkit-strategy-grid">
              {strategySummaries.map((strategy) => (
                <StrategySummaryCard strategy={strategy} key={strategy.key} />
              ))}
            </div>
          ) : strategyQuery.isFetching ? (
            <Alert
              type="info"
              showIcon
              message="策略展示正在生成"
              description="核心信号已先返回；市场踩踏风险需打开完整分析后显示。"
            />
          ) : strategyQuery.isError ? (
            <Alert type="warning" showIcon message="策略展示暂不可用" description={formatQueryError(strategyQuery.error)} />
          ) : (
            <div className="macro-toolkit-empty-output">暂无策略摘要。</div>
          )}
        </>
      )}
      {macroEtfStrategy ? <DualFrequencyRiskBudgetPanel snapshot={macroEtfStrategy} /> : null}
      {!showOperations && strategyQuery.isFetching && !strategySummaries.length ? (
        <Alert
          type="info"
          showIcon
          message="策略展示正在生成"
          description="核心信号已先返回；完整策略证据打开完整分析后确认。"
        />
      ) : strategyQuery.isFetching ? (
        null
      ) : strategyQuery.isError ? (
        !showOperations ? (
          <Alert type="warning" showIcon message="策略展示暂不可用" description={formatQueryError(strategyQuery.error)} />
        ) : null
      ) : !showOperations && !strategySummaries.length ? (
        <div className="macro-toolkit-empty-output">暂无策略摘要。</div>
      ) : null}
    </section>
  );
}
