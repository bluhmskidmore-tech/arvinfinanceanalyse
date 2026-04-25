import { SectionCard } from "../../../components/SectionCard";
import { SummaryBlock } from "../../../components/SummaryBlock";

type BusinessConclusionProps = {
  reportDate?: string;
  detailRowCount?: number;
  summaryRowCount?: number;
  marketValueAmount?: string;
  amortizedCostAmount?: string;
  accruedInterestAmount?: string;
  /** `position_scope=all` 时：资产端/负债端分列（亿元数值串），与 `total_*` 代数和一致 */
  assetMarketValueAmount?: string;
  liabilityMarketValueAmount?: string;
  assetAmortizedCostAmount?: string;
  liabilityAmortizedCostAmount?: string;
  assetAccruedInterestAmount?: string;
  liabilityAccruedInterestAmount?: string;
  missingFxCount?: number;
};

export function BusinessConclusion({
  reportDate,
  detailRowCount,
  summaryRowCount,
  marketValueAmount,
  amortizedCostAmount,
  accruedInterestAmount,
  assetMarketValueAmount,
  liabilityMarketValueAmount,
  assetAmortizedCostAmount,
  liabilityAmortizedCostAmount,
  assetAccruedInterestAmount,
  liabilityAccruedInterestAmount,
  missingFxCount = 0,
}: BusinessConclusionProps) {
  const hasSplit =
    assetMarketValueAmount !== undefined &&
    liabilityMarketValueAmount !== undefined;
  const hasGovernedValues =
    Boolean(reportDate) ||
    detailRowCount !== undefined ||
    summaryRowCount !== undefined ||
    Boolean(marketValueAmount) ||
    hasSplit;

  const content = hasGovernedValues
    ? hasSplit
      ? `当前经营页首屏已切回正式余额读链路。报告日 ${reportDate ?? "待确认"}，明细 ${detailRowCount ?? 0} 行、汇总 ${summaryRowCount ?? 0} 行。市值按侧拆分：资产端 ${assetMarketValueAmount ?? "—"} 亿元、负债端 ${liabilityMarketValueAmount ?? "—"} 亿元（代数和 ${marketValueAmount ?? "—"}）；摊余成本 资产端 ${assetAmortizedCostAmount ?? "—"} 亿元、负债端 ${liabilityAmortizedCostAmount ?? "—"} 亿元（代数和 ${amortizedCostAmount ?? "—"}）；应计利息 资产端 ${assetAccruedInterestAmount ?? "—"} 亿元、负债端 ${liabilityAccruedInterestAmount ?? "—"} 亿元（代数和 ${accruedInterestAmount ?? "—"}）。未接入正式经营口径的指标不再在首屏硬写结论。`
      : `当前经营页首屏已切回正式余额读链路。报告日 ${reportDate ?? "待确认"}，明细 ${detailRowCount ?? 0} 行、汇总 ${summaryRowCount ?? 0} 行；当前可直接阅读市场价值 ${marketValueAmount ?? "—"}、摊余成本 ${amortizedCostAmount ?? "—"}、应计利息 ${accruedInterestAmount ?? "—"}。未接入正式经营口径的指标不再在首屏硬写结论。`
    : "当前经营页首屏只保留正式读链路和专题分流，不再把 staged 经营结论写成正式判断。待正式经营口径到位后，再恢复更强的业务结论表达。";

  const tags = hasGovernedValues
    ? [
        { label: "正式读链路: 已切回", color: "green" },
        {
          label: `FX覆盖: ${missingFxCount > 0 ? `缺 ${missingFxCount} 对` : "可用"}`,
          color: missingFxCount > 0 ? "gold" : "green",
        },
        { label: "经营口径: 部分待接入", color: "orange" },
      ]
    : [
        { label: "正式读链路: 待确认", color: "gold" },
        { label: "经营口径: 待接入", color: "orange" },
      ];

  return (
    <SectionCard title="本期经营结论">
      <SummaryBlock title="" content={content} tags={tags} />
    </SectionCard>
  );
}
