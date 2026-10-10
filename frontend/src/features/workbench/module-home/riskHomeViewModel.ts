import type {
  ModuleHomeDetailSection,
  ModuleHomeDetailRow,
  ModuleHomeTone,
} from "./moduleHomeDetailTypes";
import type { UseQueryResult } from "@tanstack/react-query";
import type {
  ApiEnvelope,
  RiskTensorDatesPayload,
} from "../../../api/contracts";
import type {
  ModuleHomeStatus,
  ModuleHomeSourceQueries,
  ModuleHomeView,
} from "./moduleHomeModel";
import {
  queryStatus,
  metaIsFormalDecisionSource,
  hasLoading,
  baseDataNote,
} from "./moduleHomeSourceState";
import { EM_DASH } from "../../../utils/format";
import {
  hasRiskTensorValue,
  buildRiskTensorDetailSections,
  buildCashflowDetailSections,
  riskTensorYiWithUnit,
  riskTensorPendingOrWan,
  riskTensorValueTone,
  riskTensorWanWithUnit,
  riskTensorDisplay,
  riskTensorRatioPercent,
} from "./riskHomeDetailModel";
import {
  riskSourceBasisLabel,
  riskDecisionGateLabel,
  buildRiskSourceUseStatus,
  buildRiskKrdChart,
} from "./riskHomeAdapter";
import { buildDetailPanel } from "./moduleHomePresentation";
import { bondNumericDisplay } from "../../bond-analytics/adapters/bondAnalyticsAdapter";

function flattenDetailSections(sections: ModuleHomeDetailSection[]): ModuleHomeDetailRow[] {
  return sections.flatMap((section) => section.rows);
}

function riskSourceMeta(source: string, reportDate: string): string {
  return `来源 ${source} · ${reportDate}`;
}

function riskDatesStatus(
  query: UseQueryResult<ApiEnvelope<RiskTensorDatesPayload>> | undefined,
  availableCount: number,
  blockedCount: number,
): ModuleHomeStatus {
  const base = queryStatus("dates", "风险报告日", query, "风险日期列表已返回。");
  if (base.tone !== "ok" || blockedCount === 0) {
    return base;
  }
  return {
    ...base,
    value: availableCount > 0 ? "部分拦截" : "全部拦截",
    detail: `${blockedCount} 个报告日因规则版本过期被拦截，需重新物化。`,
    tone: "watch",
  };
}

export function riskView(
  queries: ModuleHomeSourceQueries,
): Omit<ModuleHomeView, "kind" | "title" | "question" | "summary" | "sourceScope"> {
  const dates = queries.riskDates?.data?.result.report_dates ?? [];
  const blockedDates = queries.riskDates?.data?.result.blocked_report_dates ?? [];
  const blockedCount = blockedDates.length;
  const latestBlockedReportDate =
    blockedCount > 0
      ? [...blockedDates].sort((a, b) => b.report_date.localeCompare(a.report_date))[0]
          ?.report_date
      : undefined;
  const tensor = queries.riskTensor?.data?.result;
  const cashflow = queries.cashflow?.data?.result;
  const tensorMeta = queries.riskTensor?.data?.result_meta;
  const cashflowMeta = queries.cashflow?.data?.result_meta;
  const tensorFormal = metaIsFormalDecisionSource(tensorMeta);
  const cashflowFormal = metaIsFormalDecisionSource(cashflowMeta);
  const reportDate = tensor?.report_date ?? cashflow?.report_date ?? dates[0] ?? EM_DASH;
  const cashflowReportDate = cashflow?.report_date ?? reportDate;
  const tensorWarnings = tensor?.warnings ?? [];
  const hasRiskPartialError = Boolean(queries.riskDates?.isError || queries.riskTensor?.isError || queries.cashflow?.isError);
  const hasRiskPrimaryError = Boolean(queries.riskDates?.isError || queries.riskTensor?.isError);
  const riskStateLabel = hasRiskPrimaryError
    ? "读取失败"
    : hasRiskPartialError
      ? "部分失败"
      : hasLoading(queries)
        ? "读取中"
        : "已接入";
  const decisionTone: ModuleHomeTone = hasRiskPrimaryError
    ? "error"
    : hasLoading(queries)
      ? "muted"
      : hasRiskPartialError ||
          !tensor ||
          !tensorFormal ||
          (Boolean(cashflow) && !cashflowFormal) ||
          tensorWarnings.length > 0 ||
          !hasRiskTensorValue(tensor.regulatory_dv01)
        ? "watch"
        : "ok";
  const decisionConclusion = hasRiskPrimaryError
    ? "风险读链路失败，当前不能形成处置判断。"
    : hasLoading(queries)
      ? "风险链路读取中，等待正式接口返回。"
      : !tensor
        ? blockedCount > 0
          ? `风险张量 ${blockedCount} 个报告日被规则版本拦截，重新物化前不能形成处置判断。`
          : "风险张量未返回，先补齐主链数据。"
        : hasRiskPartialError
          ? "风险张量已返回，现金流等辅助链路需单独复核。"
        : !tensorFormal
          ? `风险张量来源为${riskSourceBasisLabel(tensorMeta)}，${riskDecisionGateLabel(
              tensorMeta,
            )}，仅供复核。`
        : cashflow && !cashflowFormal
          ? `现金流预测为${riskSourceBasisLabel(cashflowMeta)}，${riskDecisionGateLabel(
              cashflowMeta,
            )}，不纳入正式风险评级。`
        : tensorWarnings.length > 0
          ? `存在 ${tensorWarnings.length} 条风险数据提示，优先核对张量质量。`
          : !hasRiskTensorValue(tensor.regulatory_dv01)
            ? "监管 DV01 待接入，不能判定限额状态。"
            : "主链已返回，按后端字段做截面风险复核。";
  const decisionDetail =
    "下方保留字段级证据；正式处置进入风险张量、集中度等正式读面，现金流页面仅作分析复核。";

  const riskTensorSections = tensor
    ? buildRiskTensorDetailSections(tensor)
    : [];
  const riskTensorRows = flattenDetailSections(riskTensorSections);
  const riskTensorStatus = buildRiskSourceUseStatus(
    queryStatus(
      "risk-tensor-detail",
      "风险张量明细",
      queries.riskTensor,
      riskTensorRows.length > 0
        ? `风险张量已返回 ${riskTensorRows.length} 条明细。`
        : "风险张量明细为空。",
    ),
    tensorMeta,
  );
  const riskTensorPanel = buildDetailPanel({
    key: "risk-tensor-detail",
    title: "风险张量明细",
    meta: riskSourceMeta("risk-tensor", reportDate),
    status: riskTensorStatus,
    rows: riskTensorRows,
    sections: riskTensorSections,
    chart: tensor ? buildRiskKrdChart(tensor) : undefined,
    showRowsWhenWarning: true,
  });

  const cashflowSections = cashflow ? buildCashflowDetailSections(cashflow) : [];
  const cashflowRows = flattenDetailSections(cashflowSections);
  const cashflowStatus = buildRiskSourceUseStatus(
    queryStatus(
      "cashflow-projection-detail",
      "现金流与缺口",
      queries.cashflow,
      cashflowRows.length > 0
        ? `现金流预测已返回 ${cashflowRows.length} 条明细。`
        : "现金流预测明细为空。",
    ),
    cashflowMeta,
  );
  const cashflowPanel = buildDetailPanel({
    key: "cashflow-projection-detail",
    title: "现金流与缺口",
    meta: riskSourceMeta("cashflow-projection", cashflowReportDate),
    status: cashflowStatus,
    rows: cashflowRows,
    sections: cashflowSections,
    showRowsWhenWarning: true,
  });

  const durationGapKpi = cashflow
    ? {
        label: "久期缺口（分析口径）",
        value: bondNumericDisplay(cashflow.duration_gap),
        detail: "分析口径：来自现金流预测 duration_gap，仅供复核。",
      }
    : {
        label: "30日缺口",
        value: riskTensorYiWithUnit(tensor?.liquidity_gap_30d),
        detail: "正式风险张量 liquidity_gap_30d。",
      };

  return {
    stateLabel: riskStateLabel,
    stateDetail: hasRiskPrimaryError
      ? "风险主链路失败，不使用前端补数。"
      : hasRiskPartialError
        ? `风险报告日 ${reportDate}，主链已返回；辅助链路存在失败。`
      : `风险报告日 ${reportDate}，可用日期 ${dates.length} 个${blockedCount > 0 ? `，规则版本拦截 ${blockedCount} 个` : ""}。`,
    kpis: [
      {
        key: "regulatory-dv01",
        label: "监管 DV01",
        value: tensor ? riskTensorPendingOrWan(tensor.regulatory_dv01) : EM_DASH,
        detail: "来自 regulatory_dv01；缺失时不使用组合 DV01 替代。",
        tone: tensor ? riskTensorValueTone(tensor.regulatory_dv01) : "watch",
      },
      {
        key: "portfolio-dv01",
        label: "组合 DV01",
        value: tensor ? riskTensorWanWithUnit(tensor.portfolio_dv01) : EM_DASH,
        detail: "portfolio_dv01，面值基数线性敏感度读数。",
        tone: tensor ? "ok" : "watch",
      },
      {
        key: "modified-duration",
        label: "修正久期",
        value: tensor ? riskTensorDisplay(tensor.portfolio_modified_duration) : EM_DASH,
        detail: "portfolio_modified_duration。",
        tone: tensor ? "ok" : "watch",
      },
      {
        key: "liquidity-gap",
        label: durationGapKpi.label,
        value: cashflow || tensor ? durationGapKpi.value : EM_DASH,
        detail: durationGapKpi.detail,
        tone: cashflow ? (cashflowFormal ? "ok" : "watch") : tensor ? "ok" : "watch",
      },
    ],
    statuses: [
      riskDatesStatus(queries.riskDates, dates.length, blockedCount),
      buildRiskSourceUseStatus(
        queryStatus("tensor", "风险张量", queries.riskTensor, "风险张量已返回。"),
        tensorMeta,
      ),
      buildRiskSourceUseStatus(
        queryStatus("cashflow", "现金流预测", queries.cashflow, "现金流预测已返回。"),
        cashflowMeta,
      ),
      {
        key: "concentration",
        label: "集中度",
        value: "下钻页",
        detail: "集中度监控入口保留到 /concentration-monitor。",
        tone: "muted",
      },
    ],
    decision: {
      title: "风险处置判断",
      conclusion: decisionConclusion,
      detail: decisionDetail,
      tone: decisionTone,
      facts: [
        { label: "报告日", value: reportDate, tone: reportDate === EM_DASH ? "watch" : "ok" },
        {
          label: "质量标记",
          value: tensor?.quality_flag ?? EM_DASH,
          tone: tensor?.quality_flag === "ok" ? "ok" : tensor ? "watch" : "muted",
        },
        {
          label: "数据提示",
          value: `${tensorWarnings.length} 条`,
          tone: tensorWarnings.length > 0 ? "watch" : "ok",
        },
        ...(cashflow
          ? [
              {
                label: "现金流口径",
                value: `${riskSourceBasisLabel(cashflowMeta)} · ${
                  cashflowFormal ? "正式决策门禁通过" : "仅供复核"
                }`,
                tone: cashflowFormal ? ("ok" as ModuleHomeTone) : ("watch" as ModuleHomeTone),
              },
            ]
          : []),
        ...(blockedCount > 0
          ? [
              {
                label: "拦截日期",
                value: latestBlockedReportDate
                  ? `${blockedCount} 个 · 最新 ${latestBlockedReportDate}`
                  : `${blockedCount} 个`,
                tone: "watch" as ModuleHomeTone,
              },
            ]
          : []),
      ],
    },
    briefings: [
      {
        title: "久期与 DV01",
        conclusion: tensor
          ? `DV01 ${riskTensorWanWithUnit(tensor.portfolio_dv01)}，修正久期 ${riskTensorDisplay(tensor.portfolio_modified_duration)}。`
          : "风险张量暂未返回。",
        evidence: "面值基数线性敏感度读数，直接展示 risk tensor 字段；不表示按市价完整重估的损益。",
        tone: tensor ? "ok" : "watch",
      },
      {
        title: "信用与集中度",
        conclusion: tensor
          ? `CS01 ${riskTensorWanWithUnit(tensor.cs01)}，前五大权重 ${riskTensorRatioPercent(tensor.issuer_top5_weight)}。`
          : "集中度需要进入下钻页核验。",
        evidence: "CS01 是信用债 DV01 代理；首页只提供字段摘要，不在前端重算。",
        tone: tensor ? "ok" : "muted",
      },
      {
        title: "现金流压力",
        conclusion: cashflow
          ? `久期缺口 ${bondNumericDisplay(cashflow.duration_gap)}，12M 再投资风险 ${bondNumericDisplay(
              cashflow.reinvestment_risk_12m,
            )}。`
          : "现金流预测未返回或待接入。",
        evidence: cashflow
          ? `久期缺口与 12M 再投资风险来自现金流预测；${riskSourceBasisLabel(
              cashflowMeta,
            )}，仅供复核，不纳入正式风险评级。30D / 90D 缺口另由风险张量正式字段展示。`
          : "现金流预测待接入。",
        tone: cashflow && cashflowFormal ? "ok" : "watch",
      },
    ],
    detailPanels: [riskTensorPanel, cashflowPanel],
    dataNote: baseDataNote("risk", queries),
  };
}
