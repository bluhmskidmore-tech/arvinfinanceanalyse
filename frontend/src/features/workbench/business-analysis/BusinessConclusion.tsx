import { SectionCard } from "../../../components/SectionCard";
import { SummaryBlock } from "../../../components/SummaryBlock";

type BusinessConclusionProps = {
  reportDate?: string;
  detailRowCount?: number;
  summaryRowCount?: number;
  marketValueAmount?: string;
  amortizedCostAmount?: string;
  accruedInterestAmount?: string;
  missingFxCount?: number;
};

export function BusinessConclusion({
  reportDate,
  detailRowCount,
  summaryRowCount,
  marketValueAmount,
  amortizedCostAmount,
  accruedInterestAmount,
  missingFxCount = 0,
}: BusinessConclusionProps) {
  const hasGovernedValues =
    Boolean(reportDate) ||
    detailRowCount !== undefined ||
    summaryRowCount !== undefined ||
    Boolean(marketValueAmount);

  const content = hasGovernedValues
    ? `当前经营页首屏已切回正式余额读链路。报告日 ${reportDate ?? "待确认"}，明细 ${detailRowCount ?? 0} 行、汇总 ${summaryRowCount ?? 0} 行；当前可直接阅读市场价值 ${marketValueAmount ?? "—"}、摊余成本 ${amortizedCostAmount ?? "—"}、应计利息 ${accruedInterestAmount ?? "—"}。未接入正式经营口径的指标不再在首屏硬写结论。`
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
