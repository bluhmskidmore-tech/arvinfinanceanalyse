import { EvidencePanel } from "../../../components/page/PagePrimitives";
import { SummaryBlock } from "../../../components/SummaryBlock";

import { EM_DASH } from "../../../utils/format";
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
    ? `报告日 ${reportDate ?? "待确认"}，${view === "monthly" || !view ? "月度" : view}产品分类损益，产品分类行 ${rowCount ?? 0} 行。资产净收入 ${assetBusinessNetIncome ?? EM_DASH} 亿元、负债净收入 ${liabilityBusinessNetIncome ?? EM_DASH} 亿元、经营净收入 ${grandBusinessNetIncome ?? EM_DASH} 亿元。可在下方明细中比较各类产品的经营贡献。`
    : "暂无可用的产品分类损益，补齐本期数据后再判断经营表现。";

  const tags = hasGovernedValues
    ? [
        { label: "经营口径: 产品分类损益", color: "green" },
        {
          label: `外汇覆盖: ${missingFxCount > 0 ? `缺 ${missingFxCount} 对` : "暂无缺口提示"}`,
          color: missingFxCount > 0 ? "gold" : "default",
        },
      ]
    : [
        { label: "经营数据: 待确认", color: "gold" },
        { label: "经营口径: 产品分类损益", color: "orange" },
      ];

  return (
    <EvidencePanel heading="本期经营结论">
      <SummaryBlock title="" content={content} tags={tags} />
    </EvidencePanel>
  );
}
