import { SectionCard } from "../../../components/SectionCard";
import { SummaryBlock } from "../../../components/SummaryBlock";

export function BusinessConclusion() {
  return (
    <SectionCard title="本期经营结论">
      <SummaryBlock
        title=""
        content="从当前两张台账口径看，经营结果仍由债券资产配置与票息收入主导；负债端对发行类工具依赖偏高，短端滚续与缺口管理仍是当期经营约束。下列判断为读面摘要，具体以正式工作簿与风控阈值为准。"
        tags={[
          { label: "收益质量:稳定", color: "green" },
          { label: "负债结构:偏短", color: "gold" },
          { label: "短端滚续:压力", color: "orange" },
          { label: "预警", color: "red" },
        ]}
      />
    </SectionCard>
  );
}
