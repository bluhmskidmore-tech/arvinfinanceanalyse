import { EvidencePanel } from "../../../components/page/PagePrimitives";
import styles from "./ManagementOutput.module.css";

type ManagementOutputProps = {
  recommendationTitle?: string;
  recommendationDetail?: string;
  recommendationActionLabel?: string;
  missingFxCount?: number;
};

export function ManagementOutput({
  recommendationTitle,
  recommendationDetail,
  recommendationActionLabel,
  missingFxCount = 0,
}: ManagementOutputProps) {
  const items: Array<{ title: string; body: string }> = [
    {
      title: "经营判断",
      body: recommendationTitle
        ? recommendationTitle
        : "请先核验本期数据，再查看经营明细。",
    },
    {
      title: "当前限制",
      body:
        missingFxCount > 0
          ? `正式外汇仍缺 ${missingFxCount} 对，跨资产相关判断需继续复核。`
          : "当前没有外汇缺口提示，涉及外币时仍需核验汇率覆盖。",
    },
    {
      title: "管理动作",
      body:
        recommendationActionLabel ??
        "进入专题页核验数据完整性。",
    },
    {
      title: "说明",
      body:
        recommendationDetail ??
        "可在产品分类损益页查看明细，在资产负债分析页查看余额结构。",
    },
  ];

  return (
    <EvidencePanel heading="管理输出">
      <div className={styles.list}>
        {items.map((item) => (
          <div key={item.title}>
            <div className={styles.itemTitle}>{item.title}</div>
            <p className={styles.itemBody}>{item.body}</p>
          </div>
        ))}
      </div>
    </EvidencePanel>
  );
}
