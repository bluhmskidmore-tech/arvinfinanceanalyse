import { SectionCard } from "../../../components/SectionCard";
import { SummaryBlock } from "../../../components/SummaryBlock";

type BusinessConclusionProps = {
  reportDate?: string;
  view?: string;
  rowCount?: number;
  assetBusinessNetIncome?: string;
  liabilityBusinessNetIncome?: string;
  grandBusinessNetIncome?: string;
  missingFxCount?: number;
};

export function BusinessConclusion({
  reportDate,
  view,
  rowCount,
  assetBusinessNetIncome,
  liabilityBusinessNetIncome,
  grandBusinessNetIncome,
  missingFxCount = 0,
}: BusinessConclusionProps) {
  const hasGovernedValues =
    Boolean(reportDate) ||
    rowCount !== undefined ||
    Boolean(grandBusinessNetIncome);

  const content = hasGovernedValues
    ? `当前经营页首屏已切回产品分类损益正式读模型。报告日 ${reportDate ?? "待确认"}，视图 ${view ?? "月度"}，产品分类行 ${rowCount ?? 0} 行；资产净收入 ${assetBusinessNetIncome ?? "—"}、负债净收入 ${liabilityBusinessNetIncome ?? "—"}、经营净收入 ${grandBusinessNetIncome ?? "—"}。资产负债余额读面降为专题入口，不作为首屏经营口径。`
    : "当前经营页首屏只保留产品分类损益正式读模型和专题分流，不再把资产负债余额读面写成经营判断。";

  const tags = hasGovernedValues
    ? [
        { label: "经营口径: 产品分类损益", color: "green" },
        {
          label: `外汇覆盖: ${missingFxCount > 0 ? `缺 ${missingFxCount} 对` : "可用"}`,
          color: missingFxCount > 0 ? "gold" : "green",
        },
        { label: "余额读面: 专题入口", color: "blue" },
      ]
    : [
        { label: "正式读链路: 待确认", color: "gold" },
        { label: "经营口径: 产品分类损益", color: "orange" },
      ];

  return (
    <SectionCard title="本期经营结论">
      <SummaryBlock title="" content={content} tags={tags} />
    </SectionCard>
  );
}
