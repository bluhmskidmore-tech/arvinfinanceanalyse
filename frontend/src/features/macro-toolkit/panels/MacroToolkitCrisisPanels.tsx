import { useCallback, useState } from "react";
import {
  ArrowUpOutlined,
  CopyOutlined,
  DatabaseOutlined,
  InfoCircleOutlined,
  LineChartOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  ToolOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Button, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { EChartsOption } from "echarts";
import type { ResultMeta } from "../../../api/contracts";
import type {
  MacroToolkitCapabilityResult,
  MacroToolkitCommodityFuturesRefreshRun,
  MacroToolkitDataHealth,
} from "../../../api/macroToolkitClient";
import { BaseChart } from "../../../components/charts/BaseChart";
import { PageSectionLead } from "../../../components/page/PagePrimitives";
import { dhApiTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import { MetricTile } from "../lib/MacroToolkitStatusPrimitives";
import * as crisisSupport from "../lib/macroToolkitCrisisSupport";

type MacroToolkitRepairItem = NonNullable<MacroToolkitDataHealth["repair_items"]>[number];
type CommodityShortfallChange = crisisSupport.CommodityShortfallChange;
type CommodityShortfallEstimate = crisisSupport.CommodityShortfallEstimate;
type CommodityRefreshEvidenceChain = crisisSupport.CommodityRefreshEvidenceChain;
type CrisisGapRepairFeedback = crisisSupport.CrisisGapRepairFeedback;
type CrisisGapGroup = crisisSupport.CrisisGapGroup;
type CommodityRefreshProductRow = crisisSupport.CommodityRefreshProductRow;
type CrisisCommodityCoverage = crisisSupport.CrisisCommodityCoverage;
type CrisisCommodityAdmission = crisisSupport.CrisisCommodityAdmission;
type CrisisCommodityApprovalPack = crisisSupport.CrisisCommodityApprovalPack;
type MacroToolkitInputEvidenceItem = crisisSupport.MacroToolkitInputEvidenceItem;
type CrisisCommodityShadowImpact = crisisSupport.CrisisCommodityShadowImpact;
type CrisisCommodityCoverageItem = crisisSupport.CrisisCommodityCoverageItem;
type CommodityPromotionRuleItem = crisisSupport.CommodityPromotionRuleItem;
type CrisisCommodityCandidateSummary = crisisSupport.CrisisCommodityCandidateSummary;

const {
  buildCommodityPromotionAuditPackCopyText,
  buildCrisisGapGroups,
  crisisScoreHistoryFromResult,
  commodityAdmissionDecisionColor,
  commodityPromotionRuleCheckStatusLabel,
  commodityPromotionRuleItem,
  commodityPromotionRuleStatusLabel,
  commodityRefreshCoverageText,
  commodityRefreshIdentifierText,
  commodityRefreshLatestDateText,
  commodityRefreshNanhuaText,
  commodityRefreshRowDeltaText,
  commodityRefreshSourceText,
  commodityRefreshStatusColor,
  commodityRefreshStatusText,
  commodityReviewConclusionColor,
  commodityReviewConclusionLabel,
  commodityShadowImpactDirectionLabel,
  commodityShadowStatusColor,
  findCrisisGapRepairItem,
  formatCommodityActionQueueLabels,
  formatCommodityActionQueueNextStep,
  formatCommodityAdmissionMetrics,
  formatCommodityAdmissionNextStep,
  formatCommodityApprovalPackFields,
  formatCommodityCandidateSummaryDetail,
  formatCommodityCoverageDateStatus,
  formatCommodityCoverageIdentifiers,
  formatCommodityProductsInline,
  formatCommodityRefreshResult,
  formatCommodityShadowContributionDetail,
  formatCommodityShadowDecisionMetrics,
  formatCommodityShadowDetail,
  formatCommodityShadowImpactDirectionDetail,
  formatCommodityShadowImpactDriverDetail,
  formatCommodityShadowImpactWarnings,
  formatCommodityShadowRefreshHint,
  formatCommodityShadowShortfallList,
  formatCommodityShadowSummary,
  formatCommodityReviewConclusionMetrics,
  formatCommodityReviewConclusionNextStep,
  formatCommodityShortfallEstimateList,
  formatCrisisGapSummaryDetail,
  formatCrisisInputDetail,
  formatCrisisInputIdentifiers,
  formatCrisisRowCount,
  formatCrisisWeight,
  formatNumberValue,
  formatSignedDelta,
  formatSignedDeltaFromPack,
  formatValue,
  isCommodityShadowHistoryShort,
  isCommodityShadowReviewReady,
  isCrisisComponent,
  isNanhuaCrisisInput,
  isRecord,
  normalizeCommodityAdmission,
  normalizeCommodityApprovalPack,
  normalizeCommodityCoverage,
  normalizeCommodityRefreshRows,
  normalizeCommodityShadowImpact,
  normalizeInputEvidence,
  normalizeMacroSourceBackfillAlias,
  commodityShadowRefreshProducts,
  toDisplayNumber,
  uniqueDisplayParts,
  MACRO_COMMODITY_SHADOW_MIN_CORRELATION,
  MACRO_COMMODITY_SHADOW_MIN_CRISIS_SAMPLES,
  MACRO_COMMODITY_SHADOW_MIN_SAMPLES,
  MACRO_COMMODITY_SHADOW_RULE_VERSION,
} = crisisSupport;

const CRISIS_SCOPE_LABELS: Record<string, string> = {
  supplemental_observation: "旁证观察",
  commodity_candidates: "商品候选",
  shadow_only: "仅影子评估",
};

function crisisScopeLabel(value: string) {
  return CRISIS_SCOPE_LABELS[value] ?? value;
}

function buildCrisisScoreHistoryOption(points: crisisSupport.CrisisScoreHistoryPoint[]): EChartsOption {
  return {
    grid: { left: 48, right: 16, top: 18, bottom: 28 },
    tooltip: {
      trigger: "axis",
      formatter: (params: unknown) => {
        const first = Array.isArray(params) ? (params[0] as { dataIndex?: number } | undefined) : undefined;
        const point = points[first?.dataIndex ?? -1];
        if (!point) {
          return "";
        }
        const percentile = point.percentile === null ? EM_DASH : `${point.percentile.toFixed(1)}%`;
        return `${point.date}<br/>Crisis Score ${point.crisis_score.toFixed(4)}<br/>历史分位 ${percentile}`;
      },
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: points.map((point) => point.date),
      axisLabel: { color: dhApiTokens.color.inkMuted, fontSize: 11 },
      axisLine: { lineStyle: { color: dhApiTokens.color.lineSoft } },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: { color: dhApiTokens.color.inkMuted, fontSize: 11 },
      splitLine: { lineStyle: { color: dhApiTokens.color.lineSoft } },
    },
    series: [
      {
        name: "Crisis Score",
        type: "line",
        data: points.map((point) => point.crisis_score),
        showSymbol: false,
        lineStyle: { color: dhApiTokens.color.blue, width: 1.6 },
        itemStyle: { color: dhApiTokens.color.blue },
        areaStyle: { color: dhApiTokens.color.blueSoft },
      },
    ],
  };
}

function CrisisGapAction({
  group,
  repairItems,
  commodityRefreshProducts,
  refreshingSourceAlias,
  commodityRefreshResult,
  commodityShortfallEstimates,
  sourceBackfillResult,
  sourceBackfillError,
  onRefreshCommodityProducts,
  onPreviewCommodityRefreshProducts,
  onRepairSourceBackfill,
}: {
  group: CrisisGapGroup;
  repairItems: MacroToolkitRepairItem[];
  commodityRefreshProducts: string[];
  refreshingSourceAlias: string | null;
  commodityRefreshResult: string | null;
  commodityShortfallEstimates: CommodityShortfallEstimate[];
  sourceBackfillResult: string | null;
  sourceBackfillError: string | null;
  onRefreshCommodityProducts?: (products: string[]) => void;
  onPreviewCommodityRefreshProducts?: (products: string[]) => void;
  onRepairSourceBackfill?: (item: MacroToolkitRepairItem, group: CrisisGapGroup) => void;
}) {
  const canRefreshSuggestedCommodities =
    group.key === "commodity" &&
    commodityRefreshProducts.length > 0 &&
    commodityShortfallEstimates.length > 0 &&
    commodityShortfallEstimates.every((item) => item.canFill) &&
    Boolean(onRefreshCommodityProducts);
  if (group.key === "commodity" && commodityRefreshProducts.length && onPreviewCommodityRefreshProducts) {
    return (
      <div className="macro-toolkit-crisis-gap-action">
        <Button
          size="small"
          type="primary"
          icon={<InfoCircleOutlined />}
          aria-label="按建议预估"
          onClick={() => onPreviewCommodityRefreshProducts(commodityRefreshProducts)}
        >
          按建议预估
        </Button>
        {commodityRefreshResult ? <small>{commodityRefreshResult}</small> : null}
        {commodityShortfallEstimates.length ? (
          <small>{formatCommodityShortfallEstimateList(commodityShortfallEstimates)}</small>
        ) : null}
        {canRefreshSuggestedCommodities ? (
          <Button
            size="small"
            icon={<ReloadOutlined />}
            aria-label="按建议刷新并重读"
            onClick={() => onRefreshCommodityProducts?.(commodityRefreshProducts)}
          >
            按建议刷新并重读
          </Button>
        ) : null}
      </div>
    );
  }

  const repairItem = findCrisisGapRepairItem(group, repairItems);
  if (!repairItem || !onRepairSourceBackfill) {
    return null;
  }
  const alias = normalizeMacroSourceBackfillAlias(repairItem.alias);
  return (
    <div className="macro-toolkit-crisis-gap-action">
      <Button
        size="small"
        icon={<ReloadOutlined />}
        loading={refreshingSourceAlias === alias}
        aria-label={repairItem.action?.label ?? "需要补齐来源数据"}
        onClick={() => onRepairSourceBackfill(repairItem, group)}
      >
        {repairItem.action?.label ?? "需要补齐来源数据"}
      </Button>
      {sourceBackfillResult ? <small>{sourceBackfillResult}</small> : null}
      {sourceBackfillError ? <small>{sourceBackfillError}</small> : null}
    </div>
  );
}

function CrisisGapRepairFeedback({ feedback }: { feedback: CrisisGapRepairFeedback }) {
  return (
    <div
      className={`macro-toolkit-crisis-gap-feedback macro-toolkit-crisis-gap-feedback--${feedback.status}`}
      data-testid="crisis-gap-repair-feedback"
    >
      <span>{feedback.groupLabel}</span>
      <strong>{feedback.message}</strong>
      <small>{feedback.detail}</small>
    </div>
  );
}

function CrisisCommodityClosurePanel({
  changes,
  evidenceChain,
}: {
  changes: CommodityShortfallChange[];
  evidenceChain: CommodityRefreshEvidenceChain | null;
}) {
  const resolvedCount = changes.filter((item) => item.resolved).length;
  return (
    <div className="macro-toolkit-crisis-commodity-closure" aria-label="Crisis Score 样本刷新闭环">
      <div>
        <span>样本缺口刷新闭环</span>
        <strong>
          已补齐 {resolvedCount}/{changes.length}
        </strong>
      </div>
      {evidenceChain ? (
        <div className="macro-toolkit-crisis-commodity-closure__chain">
          <small>建议品种 {formatCommodityProductsInline(evidenceChain.suggestedProducts)}</small>
          <small>实际刷新 {formatCommodityProductsInline(evidenceChain.refreshedProducts)}</small>
          <small>{evidenceChain.fullReloaded ? "完整分析已重读" : "完整分析重读待确认"}</small>
        </div>
      ) : null}
      <div className="macro-toolkit-crisis-commodity-closure__grid">
        {changes.map((item) => (
          <small key={item.field}>
            {item.label} · 刷新前 {item.before} · 刷新后 {item.after} · 剩余缺口 {item.remainingGap}
          </small>
        ))}
      </div>
    </div>
  );
}

function CrisisCommodityShadowDecisionPanel({
  coverage,
  admission,
  approvalPack,
  commodityInput = null,
  analysisMeta,
  analysisAsOfDate = null,
}: {
  coverage: CrisisCommodityCoverage;
  admission: CrisisCommodityAdmission | null;
  approvalPack: CrisisCommodityApprovalPack | null;
  commodityInput?: MacroToolkitInputEvidenceItem | null;
  analysisMeta?: ResultMeta | null;
  analysisAsOfDate?: string | null;
}) {
  const promotionItems = coverage.items.map(commodityPromotionRuleItem);
  const manualCount = promotionItems.filter((item) => item.status === "manual_review").length;
  const rejectedCount = promotionItems.filter((item) => item.status === "not_recommended").length;
  const reviewQueueItems = coverage.items.filter(isCommodityShadowReviewReady);
  const shortQueueItems = coverage.items.filter(isCommodityShadowHistoryShort);
  const auditPackCopyText = buildCommodityPromotionAuditPackCopyText(promotionItems, {
    manualCount,
    rejectedCount,
    analysisMeta,
    analysisAsOfDate,
    reviewQueueItems,
    shortQueueItems,
    coverageItems: coverage.items,
    commodityInput,
    summary: coverage.candidate_summary,
  });
  const [auditPackCopyStatus, setAuditPackCopyStatus] = useState<"idle" | "success" | "error">("idle");
  const handleCopyAuditPack = useCallback(async () => {
    const clipboard =
      (typeof navigator === "undefined" ? undefined : navigator.clipboard) ??
      (typeof window === "undefined" ? undefined : window.navigator.clipboard);
    const writeText = clipboard?.writeText;
    if (typeof writeText !== "function") {
      setAuditPackCopyStatus("error");
      return;
    }
    try {
      await writeText(auditPackCopyText);
      setAuditPackCopyStatus("success");
    } catch {
      setAuditPackCopyStatus("error");
    }
  }, [auditPackCopyText]);
  const summary = coverage.candidate_summary;
  if (!summary) {
    return null;
  }
  const reviewableCount = summary.shadow_evaluation_ready_count;
  const shortCount = summary.shadow_evaluation_short_count;
  const totalCount = coverage.tracked_count || coverage.items.length;
  const formalCommodityInputText = commodityInput
    ? `${commodityInput.label || commodityInput.field} · ${formatCrisisInputIdentifiers(commodityInput)}`
    : "南华商品输入缺失";
  const shadowCandidateText = formatCommodityActionQueueLabels(reviewQueueItems);
  return (
    <div className="macro-toolkit-crisis-shadow-decision" aria-label="候选商品影子评估决策面板">
      <div className="macro-toolkit-crisis-shadow-decision__head">
        <div>
          <span>候选商品影子评估</span>
          <strong>
            可复核 {reviewableCount}/{totalCount}
          </strong>
        </div>
        <div className="macro-toolkit-tag-row">
          <Tag color="default">当前未计入 Crisis Score</Tag>
          <Tag color={summary.approval_required ? "gold" : "green"}>
            {summary.approval_required ? "转正前需审批" : "暂无审批要求"}
          </Tag>
          <Tag color={shortCount ? "orange" : "green"}>样本不足 {shortCount}</Tag>
        </div>
      </div>
      <CommodityShadowActionQueue
        reviewItems={reviewQueueItems}
        shortItems={shortQueueItems}
        summary={summary}
      />
      <CommodityCandidateReviewConclusion
        admission={admission}
        items={coverage.items}
        promotionItems={promotionItems}
      />
      <CommodityCandidateApprovalPackPanel approvalPack={approvalPack} />
      <div className="macro-toolkit-crisis-shadow-decision__grid">
        {coverage.items.map((item) => (
          <div className="macro-toolkit-crisis-shadow-decision__item" key={item.field}>
            <div className="macro-toolkit-capability-result-head">
              <span>{item.label || item.field}</span>
              <Tag color={commodityShadowStatusColor(item.shadow_evaluation?.status)}>
                {item.shadow_evaluation?.label ?? "影子评估待确认"}
              </Tag>
            </div>
            <strong>{formatCommodityCoverageIdentifiers(item)}</strong>
            <small>
              {item.source ?? "来源缺失"} · {item.series_id ?? "序列缺失"}
              {item.used_in_formula ? " · 已纳入公式" : ""}
            </small>
            {item.shadow_evaluation ? (
              <>
                <small>{formatCommodityShadowDecisionMetrics(item.shadow_evaluation)}</small>
                <small>{item.shadow_evaluation.next_step}</small>
              </>
            ) : item.candidate_decision ? (
              <small>{item.candidate_decision.next_step}</small>
            ) : null}
          </div>
        ))}
      </div>
      <div className="macro-toolkit-crisis-promotion-rule-pack" aria-label="候选商品转正规则包">
        <div className="macro-toolkit-crisis-promotion-rule-pack__head">
          <div>
            <span>候选商品转正规则包</span>
            <strong>
              待人工判断 {manualCount} · 不建议进入公式 {rejectedCount}
            </strong>
          </div>
          <small>规则只用于审批前复核，不改变 Crisis Score 公式</small>
          <small>规则版本 {MACRO_COMMODITY_SHADOW_RULE_VERSION}</small>
          <small>样本阈值 &gt;={MACRO_COMMODITY_SHADOW_MIN_SAMPLES} 个重叠样本</small>
          <small>
            危机样本阈值 &gt;={MACRO_COMMODITY_SHADOW_MIN_CRISIS_SAMPLES} 个高 Crisis Score 样本
          </small>
          <small>
            相关性阈值 |corr|&gt;={MACRO_COMMODITY_SHADOW_MIN_CORRELATION.toFixed(2)} 才可直接通过
          </small>
          <div className="macro-toolkit-crisis-promotion-rule-pack__actions">
            <Button
              aria-label="复制审计包"
              icon={<CopyOutlined aria-hidden="true" />}
              size="small"
              type="default"
              onClick={() => void handleCopyAuditPack()}
            >
              {auditPackCopyStatus === "success"
                ? "已复制"
                : auditPackCopyStatus === "error"
                  ? "复制失败"
                  : "复制审计包"}
            </Button>
            {auditPackCopyStatus !== "idle" ? (
              <span
                aria-atomic="true"
                aria-label="审计包复制状态"
                aria-live="polite"
                className={`macro-toolkit-crisis-promotion-rule-pack__copy-status macro-toolkit-crisis-promotion-rule-pack__copy-status--${auditPackCopyStatus}`}
                role="status"
              >
                {auditPackCopyStatus === "success" ? "审计包已复制" : "复制失败，请手动选择审计包文本"}
              </span>
            ) : null}
          </div>
        </div>
        <div className="macro-toolkit-crisis-promotion-rule-pack__audit" aria-label="shadow_rule_v1 审计注记">
          <strong>{MACRO_COMMODITY_SHADOW_RULE_VERSION} 审计注记</strong>
          <small>用途：商品候选进入公式前的影子复核</small>
          <small>边界：不写入 Crisis Score，不改变权重</small>
          <small>审批：历史回测、相关性检验、权重审批、版本记录齐备后再提交</small>
        </div>
        <div
          className="macro-toolkit-crisis-promotion-rule-pack__formula-boundary"
          aria-label="Crisis Score 商品公式输入边界"
        >
          <div className="macro-toolkit-crisis-promotion-rule-pack__formula-boundary-item">
            <span>正式输入</span>
            <strong>{formalCommodityInputText}</strong>
            <small>
              {commodityInput ? "已纳入 Crisis Score 公式" : "已纳入 Crisis Score 公式的南华输入未命中"}
            </small>
          </div>
          <div className="macro-toolkit-crisis-promotion-rule-pack__formula-boundary-item">
            <span>影子候选</span>
            <strong>{shadowCandidateText}</strong>
            <small>当前未计入 Crisis Score</small>
          </div>
        </div>
        <div className="macro-toolkit-crisis-promotion-rule-pack__grid">
          {promotionItems.map((item) => (
            <div className="macro-toolkit-crisis-promotion-rule-pack__item" key={item.field}>
              <small>
                {item.label} · {commodityPromotionRuleStatusLabel(item.status)}
              </small>
              <small>{item.reason}</small>
              {item.checks.map((check) => (
                <small key={`${item.field}-${check.name}`}>
                  {item.label} · {check.name} {commodityPromotionRuleCheckStatusLabel(check.status)} {check.value}
                </small>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function CrisisCommodityShadowImpactPanel({
  currentScore,
  coverage,
  shadowImpact,
}: {
  currentScore: number | null;
  coverage: CrisisCommodityCoverage;
  shadowImpact: CrisisCommodityShadowImpact | null;
}) {
  const promotionItems = coverage.items.map(commodityPromotionRuleItem);
  const driverItems = promotionItems.filter((item) => item.status !== "not_recommended");
  const driverFields = new Set(driverItems.map((item) => item.field));
  const driverCoverageItems = coverage.items.filter((item) => driverFields.has(item.field));
  const readyCount = promotionItems.filter((item) => item.status === "ready_for_review").length;
  const manualCount = promotionItems.filter((item) => item.status === "manual_review").length;
  const hasShadowScore = shadowImpact?.shadow_score != null;
  const impactDrivers = shadowImpact?.candidate_contributions.length
    ? shadowImpact.candidate_contributions
    : null;
  return (
    <div className="macro-toolkit-crisis-shadow-impact" aria-label="Crisis Score v2 影子影响评估">
      <div className="macro-toolkit-crisis-shadow-impact__head">
        <div>
          <span>Crisis Score v2 影子影响评估</span>
          <strong>{hasShadowScore ? "影子分数只读试算" : "影子分数待公式确认"}</strong>
        </div>
        <small>
          {shadowImpact?.formula_version ?? "商品候选当前只做影子影响判断"}；不改变正式 Crisis Score。
        </small>
      </div>
      <div className="macro-toolkit-crisis-shadow-impact__metrics">
        <MetricTile
          icon={<SafetyCertificateOutlined />}
          label="正式 Crisis Score"
          value={shadowImpact?.current_score ?? currentScore ?? EM_DASH}
          detail="不改变正式 Crisis Score"
          tone={(shadowImpact?.current_score ?? currentScore) == null ? "missing" : "neutral"}
        />
        <MetricTile
          icon={<LineChartOutlined />}
          label="v2 影子分数"
          value={shadowImpact?.shadow_score ?? "影子分数待公式确认"}
          detail={shadowImpact ? `差值 ${formatSignedDelta(shadowImpact.delta)}` : "不能直接换算为分数"}
          detailTitle={
            shadowImpact
              ? `差值 ${formatSignedDelta(shadowImpact.delta)} · ${shadowImpact.formula_version}`
              : undefined
          }
          tone="neutral"
        />
        <MetricTile
          icon={<ArrowUpOutlined />}
          label="影响方向"
          value={shadowImpact ? commodityShadowImpactDirectionLabel(shadowImpact.direction) : "待公式/权重确认"}
          detail={
            shadowImpact
              ? `${crisisScopeLabel(shadowImpact.scope)} · ${formatCommodityShadowImpactWarnings(shadowImpact)}`
              : formatCommodityShadowImpactDirectionDetail(driverCoverageItems)
          }
          tone="neutral"
        />
        <MetricTile
          icon={<ToolOutlined />}
          label="候选驱动"
          value={`${shadowImpact?.candidate_count ?? driverItems.length} 个待复核`}
          detail={
            shadowImpact
              ? `可进入公式前审批 ${shadowImpact.approval_required ? "是" : "否"}`
              : `可进入人工复核 ${readyCount} / 继续观察 ${manualCount}`
          }
          tone="neutral"
        />
      </div>
      {shadowImpact?.warnings.length ? (
        <div className="macro-toolkit-tag-row" aria-label="影子影响警示">
          {shadowImpact.warnings.map((warning) => (
            <Tag color="gold" key={warning}>
              {warning}
            </Tag>
          ))}
        </div>
      ) : null}
      <div className="macro-toolkit-crisis-shadow-impact__grid">
        {impactDrivers
          ? impactDrivers.map((item) => (
              <div className="macro-toolkit-crisis-shadow-impact__item" key={item.field}>
                <div className="macro-toolkit-capability-result-head">
                  <span>{item.label || item.field}</span>
                  <Tag color="blue">{item.status}</Tag>
                </div>
                <small>{formatCommodityShadowContributionDetail(item)}</small>
                {item.used_in_official_score ? <small>已纳入正式分数</small> : null}
              </div>
            ))
          : driverCoverageItems.map((item) => {
          const promotionItem = promotionItems.find((candidate) => candidate.field === item.field);
          return (
            <div className="macro-toolkit-crisis-shadow-impact__item" key={item.field}>
              <div className="macro-toolkit-capability-result-head">
                <span>{item.label || item.field}</span>
                <Tag color={commodityReviewConclusionColor(promotionItem?.status ?? "not_recommended")}>
                  {commodityReviewConclusionLabel(promotionItem?.status ?? "not_recommended")}
                </Tag>
              </div>
              <small>{formatCommodityShadowImpactDriverDetail(item)}</small>
            </div>
          );
        })}
      </div>
      {shadowImpact?.warnings.length ? (
        <small className="macro-toolkit-crisis-shadow-impact__note">
          {shadowImpact.warnings.join(" / ")}
        </small>
      ) : null}
      <small className="macro-toolkit-crisis-shadow-impact__note">
        {shadowImpact?.next_step ?? "审批建议：先复核候选相关性，再确认 v2 权重"}
      </small>
    </div>
  );
}

function CommodityCandidateReviewConclusion({
  admission,
  items,
  promotionItems,
}: {
  admission: CrisisCommodityAdmission | null;
  items: CrisisCommodityCoverageItem[];
  promotionItems: CommodityPromotionRuleItem[];
}) {
  if (admission) {
    return (
      <div className="macro-toolkit-crisis-review-conclusion" aria-label="商品候选复核结论">
        <div className="macro-toolkit-crisis-review-conclusion__head">
          <div>
            <span>商品候选复核结论</span>
            <strong>
              商品候选准入评估：建议纳入 {admission.decision_counts.recommend_include} · 继续观察{" "}
              {admission.decision_counts.watch} · 暂不纳入 {admission.decision_counts.do_not_include}
            </strong>
          </div>
          <small>{admission.rule_version} · {crisisScopeLabel(admission.scope)}</small>
          <small>审批前不改变正式 Crisis Score</small>
        </div>
        {admission.warnings.length ? (
          <div className="macro-toolkit-tag-row" aria-label="商品候选准入警告">
            {admission.warnings.map((warning) => (
              <Tag color="gold" key={warning}>
                {warning}
              </Tag>
            ))}
          </div>
        ) : null}
        <div className="macro-toolkit-crisis-review-conclusion__grid">
          {admission.items.map((item) => (
            <div className="macro-toolkit-crisis-review-conclusion__item" key={item.field}>
              <div className="macro-toolkit-capability-result-head">
                <span>{item.label || item.field}</span>
                <Tag color={commodityAdmissionDecisionColor(item.decision)}>{item.decision_label}</Tag>
              </div>
              <strong>{item.reason}</strong>
              <small>{formatCommodityAdmissionMetrics(item)}</small>
              <small>下一步：{formatCommodityAdmissionNextStep(item)}</small>
            </div>
          ))}
        </div>
        <small className="macro-toolkit-crisis-shadow-impact__note">{admission.next_step}</small>
      </div>
    );
  }
  const promotionByField = new Map(promotionItems.map((item) => [item.field, item]));
  const readyCount = promotionItems.filter((item) => item.status === "ready_for_review").length;
  const manualCount = promotionItems.filter((item) => item.status === "manual_review").length;
  const rejectedCount = promotionItems.filter((item) => item.status === "not_recommended").length;
  return (
    <div className="macro-toolkit-crisis-review-conclusion" aria-label="商品候选复核结论">
      <div className="macro-toolkit-crisis-review-conclusion__head">
        <div>
          <span>商品候选复核结论</span>
          <strong>
            可进入人工复核 {readyCount} · 继续观察 {manualCount} · 不建议纳入 {rejectedCount}
          </strong>
        </div>
        <small>复用 shadow_rule_v1 判断，只做展示，不改变 Crisis Score 公式或权重</small>
      </div>
      <div className="macro-toolkit-crisis-review-conclusion__grid">
        {items.map((item) => {
          const promotionItem = promotionByField.get(item.field) ?? commodityPromotionRuleItem(item);
          return (
            <div className="macro-toolkit-crisis-review-conclusion__item" key={item.field}>
              <div className="macro-toolkit-capability-result-head">
                <span>{item.label || item.field}</span>
                <Tag color={commodityReviewConclusionColor(promotionItem.status)}>
                  {commodityReviewConclusionLabel(promotionItem.status)}
                </Tag>
              </div>
              <strong>{promotionItem.reason}</strong>
              <small>{formatCommodityReviewConclusionMetrics(item)}</small>
              <small>{formatCommodityReviewConclusionNextStep(promotionItem.status, item)}</small>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CommodityCandidateApprovalPackPanel({
  approvalPack,
}: {
  approvalPack: CrisisCommodityApprovalPack | null;
}) {
  const [copyStatus, setCopyStatus] = useState<"idle" | "success" | "error">("idle");
  const handleCopyApprovalPack = useCallback(async () => {
    const clipboard =
      (typeof navigator === "undefined" ? undefined : navigator.clipboard) ??
      (typeof window === "undefined" ? undefined : window.navigator.clipboard);
    const writeText = clipboard?.writeText;
    if (!approvalPack || typeof writeText !== "function") {
      setCopyStatus("error");
      return;
    }
    try {
      await writeText(approvalPack.copy_text);
      setCopyStatus("success");
    } catch {
      setCopyStatus("error");
    }
  }, [approvalPack]);

  if (!approvalPack) {
    return null;
  }

  return (
    <div className="macro-toolkit-crisis-review-conclusion" aria-label="商品候选审批材料">
      <div className="macro-toolkit-crisis-review-conclusion__head">
        <div>
          <span>商品候选审批材料</span>
          <strong>{approvalPack.summary}</strong>
        </div>
        <small>{approvalPack.pack_version} · {crisisScopeLabel(approvalPack.scope)}</small>
        <small>影子差值 {formatSignedDeltaFromPack(approvalPack.copy_text)}</small>
      </div>
      <div className="macro-toolkit-tag-row" aria-label="商品候选审批材料警告">
        {approvalPack.warnings.map((warning) => (
          <Tag color="gold" key={warning}>
            {warning}
          </Tag>
        ))}
      </div>
      <div className="macro-toolkit-crisis-review-conclusion__grid">
        <div className="macro-toolkit-crisis-review-conclusion__item">
          <span>建议纳入</span>
          <strong>{approvalPack.decision_counts.recommend_include}</strong>
          <small>{formatCommodityApprovalPackFields(approvalPack.recommended_fields)}</small>
        </div>
        <div className="macro-toolkit-crisis-review-conclusion__item">
          <span>继续观察</span>
          <strong>{approvalPack.decision_counts.watch}</strong>
          <small>{formatCommodityApprovalPackFields(approvalPack.watch_fields)}</small>
        </div>
        <div className="macro-toolkit-crisis-review-conclusion__item">
          <span>暂不纳入</span>
          <strong>{approvalPack.decision_counts.do_not_include}</strong>
          <small>{formatCommodityApprovalPackFields(approvalPack.rejected_fields)}</small>
        </div>
      </div>
      <div className="macro-toolkit-crisis-promotion-rule-pack__actions">
        <Button
          aria-label="复制审批材料"
          icon={<CopyOutlined aria-hidden="true" />}
          size="small"
          type="default"
          onClick={() => void handleCopyApprovalPack()}
        >
          {copyStatus === "success" ? "已复制" : copyStatus === "error" ? "复制失败" : "复制审批材料"}
        </Button>
        {copyStatus !== "idle" ? (
          <small
            aria-label="审批材料复制状态"
            className={`macro-toolkit-crisis-promotion-rule-pack__copy-status macro-toolkit-crisis-promotion-rule-pack__copy-status--${copyStatus}`}
          >
            {copyStatus === "success" ? "审批材料已复制" : "复制失败，请手动选择审批材料文本"}
          </small>
        ) : null}
      </div>
    </div>
  );
}

function CommodityShadowActionQueue({
  reviewItems,
  shortItems,
  summary,
}: {
  reviewItems: CrisisCommodityCoverageItem[];
  shortItems: CrisisCommodityCoverageItem[];
  summary: CrisisCommodityCandidateSummary;
}) {
  return (
    <div className="macro-toolkit-crisis-shadow-action-queue" aria-label="商品候选下一动作队列">
      <div className="macro-toolkit-crisis-shadow-action-queue__item">
        <span>人工复核队列</span>
        <strong>{formatCommodityActionQueueLabels(reviewItems)}</strong>
        <small>相关性与命中率可读，但进入公式前仍需审批确认</small>
      </div>
      <div className="macro-toolkit-crisis-shadow-action-queue__item">
        <span>补历史样本队列</span>
        <strong>{formatCommodityActionQueueLabels(shortItems)}</strong>
        <small>当前未计入 Crisis Score；先补齐重叠样本和危机期样本</small>
      </div>
      <div className="macro-toolkit-crisis-shadow-action-queue__next">
        <span>处理顺序</span>
        <strong>{formatCommodityActionQueueNextStep(reviewItems, shortItems, summary)}</strong>
      </div>
    </div>
  );
}

export function CommodityRefreshResultPanel({ refresh }: { refresh: MacroToolkitCommodityFuturesRefreshRun }) {
  const rows = normalizeCommodityRefreshRows(refresh);
  const isDryRun = refresh.status === "dry_run" || refresh.dry_run === true;
  const nanhuaRow = rows.find((row) => row.isNanhua);
  const summary = refresh.summary;
  const nanhuaMessage =
    nanhuaRow && !isDryRun && nanhuaRow.status === "written"
      ? "Crisis Score 南华输入已更新"
      : nanhuaRow
        ? "NHCI / NH0100.NHF 已纳入本次检查"
        : "NHCI / NH0100.NHF 未选择";
  const columns: ColumnsType<CommodityRefreshProductRow> = [
    {
      title: "品种",
      dataIndex: "productName",
      key: "productName",
      render: (_, row) => (
        <div className="macro-toolkit-commodity-refresh-product">
          <span>{row.productName}</span>
          <small>{commodityRefreshIdentifierText(row)}</small>
        </div>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 110,
      render: (_, row) => <Tag color={commodityRefreshStatusColor(row.status)}>{commodityRefreshStatusText(row.status)}</Tag>,
    },
    {
      title: "行数",
      dataIndex: "rowCountLabel",
      key: "rowCountLabel",
      width: 110,
    },
    {
      title: "最新值日期 / 值",
      dataIndex: "latestDate",
      key: "latestDate",
      render: (_, row) => (
        <span>
          {row.latestDate}
          {row.latestValue == null ? "" : ` / ${formatNumberValue(row.latestValue, 2)}`}
        </span>
      ),
    },
    {
      title: "来源",
      dataIndex: "vendor",
      key: "vendor",
      width: 120,
    },
    {
      title: "写入表",
      dataIndex: "table",
      key: "table",
      render: (table: string) => <span className="macro-toolkit-nowrap-soft">{table}</span>,
    },
  ];

  return (
    <div className="macro-toolkit-commodity-refresh-result" aria-label="商品期货刷新结果">
      <div className="macro-toolkit-commodity-refresh-summary">
        <span>{isDryRun ? "预估结果" : "刷新结果"}</span>
        <strong>{formatCommodityRefreshResult(refresh)}</strong>
        <Tag color={nanhuaRow && !isDryRun && nanhuaRow.status === "written" ? "green" : "blue"}>{nanhuaMessage}</Tag>
      </div>
      {summary ? <CommodityRefreshSummaryStrip summary={summary} isDryRun={isDryRun} /> : null}
      <Table
        className="macro-toolkit-table--wide"
        rowKey="key"
        size="small"
        columns={columns}
        dataSource={rows}
        pagination={false}
        scroll={{ x: 760 }}
      />
    </div>
  );
}

function CommodityRefreshSummaryStrip({
  summary,
  isDryRun,
}: {
  summary: NonNullable<MacroToolkitCommodityFuturesRefreshRun["summary"]>;
  isDryRun: boolean;
}) {
  return (
    <div className="macro-toolkit-commodity-refresh-closure" aria-label="商品期货刷新后闭环">
      <span>{isDryRun ? "预估基线" : "刷新后闭环"}</span>
      <strong>{commodityRefreshRowDeltaText(summary)}</strong>
      <strong>{commodityRefreshLatestDateText(summary)}</strong>
      <strong>{commodityRefreshCoverageText(summary)}</strong>
      <strong>{commodityRefreshNanhuaText(summary)}</strong>
      <strong>{commodityRefreshSourceText(summary)}</strong>
    </div>
  );
}

export function CrisisScoreEvidencePanel({
  result,
  analysisMeta = null,
  analysisAsOfDate = null,
  repairItems = [],
  refreshingSourceAlias = null,
  commodityRefreshResult = null,
  commodityRefreshEvidenceChain = null,
  commodityShortfallChanges = [],
  commodityShortfallEstimates = [],
  repairFeedback = null,
  sourceBackfillResult = null,
  sourceBackfillError = null,
  onRepairSourceBackfill,
  onApplyCommodityRefreshProducts,
  onPreviewCommodityRefreshProducts,
  onRefreshCommodityProducts,
}: {
  result: MacroToolkitCapabilityResult;
  analysisMeta?: ResultMeta | null;
  analysisAsOfDate?: string | null;
  repairItems?: MacroToolkitRepairItem[];
  refreshingSourceAlias?: string | null;
  commodityRefreshResult?: string | null;
  commodityRefreshEvidenceChain?: CommodityRefreshEvidenceChain | null;
  commodityShortfallChanges?: CommodityShortfallChange[];
  commodityShortfallEstimates?: CommodityShortfallEstimate[];
  repairFeedback?: CrisisGapRepairFeedback | null;
  sourceBackfillResult?: string | null;
  sourceBackfillError?: string | null;
  onRepairSourceBackfill?: (item: MacroToolkitRepairItem, group: CrisisGapGroup) => void;
  onApplyCommodityRefreshProducts?: (products: string[]) => void;
  onPreviewCommodityRefreshProducts?: (products: string[]) => void;
  onRefreshCommodityProducts?: (products: string[]) => void;
}) {
  const [shadowEvidenceExpanded, setShadowEvidenceExpanded] = useState(false);
  const normalizedEvidence = normalizeInputEvidence(result);
  const inputEvidence = normalizedEvidence?.inputs ?? [];
  const rawResult = result.result;
  const availableComponentCount = toDisplayNumber(rawResult.available_component_count);
  const componentCount = toDisplayNumber(rawResult.component_count);
  const components = Array.isArray(rawResult.components)
    ? rawResult.components.filter(isCrisisComponent)
    : [];
  const weights = isRecord(rawResult.weights) ? rawResult.weights : {};
  const commodityInput = inputEvidence.find(isNanhuaCrisisInput);
  const commodityCoverage = normalizeCommodityCoverage(rawResult.commodity_coverage);
  const commodityShadowImpact = normalizeCommodityShadowImpact(rawResult.shadow_impact);
  const commodityAdmission = normalizeCommodityAdmission(rawResult.commodity_candidate_admission);
  const commodityApprovalPack = normalizeCommodityApprovalPack(rawResult.commodity_candidate_approval_pack);
  const commodityShortRefreshProducts = commodityCoverage?.candidate_summary
    ? commodityShadowRefreshProducts(commodityCoverage.candidate_summary)
    : [];
  const commodityShortRefreshHint = formatCommodityShadowRefreshHint(commodityShortRefreshProducts);
  const warnings = uniqueDisplayParts([...result.warnings, ...(normalizedEvidence?.missingInputs ?? [])]);
  const crisisGapGroups = buildCrisisGapGroups(inputEvidence, warnings, commodityCoverage);
  const crisisGapCount = crisisGapGroups.reduce((total, group) => total + group.items.length, 0);
  const crisisGapDetail = formatCrisisGapSummaryDetail(crisisGapGroups);
  const scoreHistory = crisisScoreHistoryFromResult(rawResult);
  const latestHistoryPoint = scoreHistory[scoreHistory.length - 1] ?? null;

  return (
    <section
      id="macro-toolkit-crisis-detail"
      className="macro-toolkit-section macro-toolkit-crisis-evidence"
      aria-label="Crisis Score 数据来源"
    >
      <PageSectionLead
        eyebrow="危机证据"
        title="Crisis Score 数据来源"
        description="完整分析返回后展示每个输入、组件权重和缺口；缺失输入保持缺失，不折算为 0。"
      />

      <div className="macro-toolkit-crisis-evidence__summary">
        <MetricTile
          icon={<SafetyCertificateOutlined />}
          label="分数组件覆盖"
          value={`${availableComponentCount}/${componentCount}`}
          detail={components.map((component) => component.key).join(" / ") || "组件缺失"}
          tone={result.status === "complete" ? "positive" : "neutral"}
        />
        <MetricTile
          icon={<DatabaseOutlined />}
          label="商品期货输入"
          value={commodityInput?.available ? "已命中" : "缺失"}
          detail={formatCrisisInputDetail(commodityInput)}
          tone={commodityInput?.available ? "positive" : "missing"}
          detailMaxLength={72}
        />
        <MetricTile
          icon={<WarningOutlined />}
          label="缺口提示"
          value={crisisGapCount}
          detail={crisisGapDetail}
          tone={crisisGapCount ? "neutral" : "positive"}
        />
      </div>

      {latestHistoryPoint && scoreHistory.length >= 2 ? (
        <div className="macro-toolkit-crisis-history" aria-label="Crisis Score 走势">
          <div className="macro-toolkit-crisis-history__head">
            <span>Crisis Score 走势 · 近 {scoreHistory.length} 期</span>
            <strong>
              最新 {formatNumberValue(latestHistoryPoint.crisis_score)} · 历史分位{" "}
              {latestHistoryPoint.percentile === null ? EM_DASH : `${latestHistoryPoint.percentile.toFixed(1)}%`}
            </strong>
          </div>
          <BaseChart option={buildCrisisScoreHistoryOption(scoreHistory)} height={200} />
        </div>
      ) : (
        <small className="macro-toolkit-crisis-coverage-note">
          Crisis Score 走势需完整分析返回的历史分数；当前历史点不足，先运行完整分析。
        </small>
      )}

      {commodityShortfallChanges.length ? (
        <CrisisCommodityClosurePanel
          changes={commodityShortfallChanges}
          evidenceChain={commodityRefreshEvidenceChain}
        />
      ) : null}

      {crisisGapGroups.length ? (
        <div className="macro-toolkit-crisis-gap-list" aria-label="Crisis Score 缺口清单">
          <div className="macro-toolkit-crisis-gap-list__head">
            <strong>Crisis Score 缺口清单</strong>
            <small>缺失不按 0 处理；补齐后重新运行完整分析确认分数。</small>
          </div>
          {repairFeedback ? <CrisisGapRepairFeedback feedback={repairFeedback} /> : null}
          <div className="macro-toolkit-crisis-gap-list__grid">
            {crisisGapGroups.map((group) => (
              <div className="macro-toolkit-crisis-gap-group" key={group.key}>
                <span>{group.label}</span>
                {group.items.map((item) => (
                  <small key={`${item.label}-${item.warning}`}>
                    {item.label} · {item.warning}
                    <br />
                    {item.detail}
                  </small>
                ))}
                <CrisisGapAction
                  group={group}
                  repairItems={repairItems}
                  commodityRefreshProducts={commodityShortRefreshProducts}
                  refreshingSourceAlias={refreshingSourceAlias}
                  commodityRefreshResult={commodityRefreshResult}
                  commodityShortfallEstimates={commodityShortfallEstimates}
                  sourceBackfillResult={sourceBackfillResult}
                  sourceBackfillError={sourceBackfillError}
                  onRefreshCommodityProducts={onRefreshCommodityProducts}
                  onPreviewCommodityRefreshProducts={onPreviewCommodityRefreshProducts}
                  onRepairSourceBackfill={onRepairSourceBackfill}
                />
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="macro-toolkit-crisis-evidence__components">
        {components.map((component) => (
          <div className="macro-toolkit-crisis-component" key={component.key}>
            <span>{component.label}</span>
            <strong>{formatValue(component.z_score, "")}</strong>
            <small>
              {component.key} · 权重 {formatCrisisWeight(component.key, weights)} · 原始值{" "}
              {formatValue(component.raw_value, "")}
            </small>
          </div>
        ))}
      </div>

      {commodityCoverage ? (
        <div className="macro-toolkit-crisis-commodity-coverage">
          <MetricTile
            icon={<DatabaseOutlined />}
            label="商品旁证覆盖"
            value={`${commodityCoverage.available_count}/${commodityCoverage.tracked_count}`}
            detail={`${commodityCoverage.role} · 非公式输入`}
            tone="neutral"
          />
          <small className="macro-toolkit-crisis-coverage-note">
            Crisis Score 公式仍仅使用 {commodityCoverage.used_in_crisis_score.join(" / ") || "nanhua"}；本区块为{" "}
            {crisisScopeLabel(commodityCoverage.role)}
          </small>
          <small className="macro-toolkit-crisis-coverage-note">
            候选商品仅做影子评估，当前未计入 Crisis Score 分数。
          </small>
          {commodityCoverage.candidate_summary ? (
            <>
              <div className="macro-toolkit-crisis-evidence__summary">
                <MetricTile
                  icon={<SafetyCertificateOutlined />}
                  label="商品扩展候选"
                  value={`${commodityCoverage.candidate_summary.shadow_review_ready_count} 个就绪`}
                  detail={formatCommodityCandidateSummaryDetail(commodityCoverage.candidate_summary)}
                  tone="neutral"
                />
                <MetricTile
                  icon={<WarningOutlined />}
                  label="公式变更需审批"
                  value={commodityCoverage.candidate_summary.approval_required ? "是" : "否"}
                  detail={
                    commodityCoverage.candidate_summary.formula_change_required
                      ? "从旁证进入 Crisis Score 公式需要版本化审批"
                      : "当前无公式变更"
                  }
                  tone="neutral"
                />
                <MetricTile
                  icon={<ToolOutlined />}
                  label="下一步"
                  value="影子评估"
                  detail={commodityCoverage.candidate_summary.next_step || "下一步待确认"}
                  tone="neutral"
                />
                <MetricTile
                  icon={<LineChartOutlined />}
                  label="影子评估结果"
                  value={`${commodityCoverage.candidate_summary.shadow_evaluation_ready_count} 个可读`}
                  detail={formatCommodityShadowSummary(commodityCoverage)}
                  tone="neutral"
                />
              </div>
              <div className="macro-toolkit-crisis-shadow-toggle">
                <Button
                  size="small"
                  icon={shadowEvidenceExpanded ? <ArrowUpOutlined /> : <ToolOutlined />}
                  aria-expanded={shadowEvidenceExpanded}
                  aria-label={shadowEvidenceExpanded ? "收起影子评估证据" : "展开影子评估证据"}
                  onClick={() => setShadowEvidenceExpanded((expanded) => !expanded)}
                >
                  {shadowEvidenceExpanded ? "收起影子评估证据" : "展开影子评估证据"}
                </Button>
                <small>审批复核时再展开。</small>
              </div>
              {shadowEvidenceExpanded ? (
                <>
                  <CrisisCommodityShadowImpactPanel
                    currentScore={result.score}
                    coverage={commodityCoverage}
                    shadowImpact={commodityShadowImpact}
                  />
                  <CrisisCommodityShadowDecisionPanel
                    admission={commodityAdmission}
                    approvalPack={commodityApprovalPack}
                    coverage={commodityCoverage}
                    commodityInput={commodityInput ?? null}
                    analysisMeta={analysisMeta}
                    analysisAsOfDate={analysisAsOfDate}
                  />
                </>
              ) : null}
              <small className="macro-toolkit-crisis-coverage-note">
                {commodityCoverage.candidate_summary.next_step || "商品扩展候选下一步待确认"}
              </small>
              {commodityCoverage.candidate_summary.shadow_evaluation_next_step ? (
                <small className="macro-toolkit-crisis-coverage-note">
                  {commodityCoverage.candidate_summary.shadow_evaluation_next_step}
                </small>
              ) : null}
              {commodityCoverage.candidate_summary.shadow_evaluation_short_items.length ? (
                <small className="macro-toolkit-crisis-coverage-note">
                  {formatCommodityShadowShortfallList(commodityCoverage.candidate_summary)}
                </small>
              ) : null}
              {commodityShortRefreshHint ? (
                <div className="macro-toolkit-crisis-coverage-action">
                  <small className="macro-toolkit-crisis-coverage-note">{commodityShortRefreshHint}</small>
                  {onApplyCommodityRefreshProducts ? (
                    <Button
                      size="small"
                      icon={<ToolOutlined />}
                      aria-label="按建议选择"
                      onClick={() => onApplyCommodityRefreshProducts(commodityShortRefreshProducts)}
                    >
                      按建议选择
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </>
          ) : null}
          {shadowEvidenceExpanded ? (
            <div className="macro-toolkit-crisis-input-grid">
              {commodityCoverage.items.map((item) => (
                <div
                  className={[
                    "macro-toolkit-crisis-input",
                    item.available ? "macro-toolkit-crisis-input--available" : "macro-toolkit-crisis-input--missing",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                  key={item.field}
                >
                  <div className="macro-toolkit-capability-result-head">
                    <span>{item.label || item.field}</span>
                    <Tag color={item.available ? "green" : "red"}>{item.available ? "命中" : "缺失"}</Tag>
                  </div>
                  <strong>{formatCommodityCoverageIdentifiers(item)}</strong>
                  <small title={`${item.field} · ${item.source ?? "来源缺失"} · ${item.series_id ?? "序列缺失"}`}>
                    {formatCrisisRowCount(item.row_count)} · {item.latest_date ?? EM_DASH}
                  </small>
                  <small>
                    {formatCommodityCoverageDateStatus(item.date_alignment_status)} · matched{" "}
                    {item.matched_alias ?? "别名缺失"}
                  </small>
                  <small>{item.used_in_formula ? "纳入公式" : "未纳入公式"}</small>
                  {item.candidate_decision ? (
                    <small title={item.candidate_decision.reason}>
                      {item.candidate_decision.label} · {item.candidate_decision.next_step}
                    </small>
                  ) : null}
                  {item.shadow_evaluation ? (
                    <small
                      title={`${item.shadow_evaluation.summary} · ${formatCommodityShadowDetail(item.shadow_evaluation)}`}
                    >
                      {item.shadow_evaluation.label} · {item.shadow_evaluation.next_step}
                    </small>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      <small className="macro-toolkit-crisis-coverage-note">
        源序列命中明细已并入指标矩阵，
        <a href="#macro-toolkit-indicator-matrix">查看指标矩阵</a>。
      </small>
    </section>
  );
}
