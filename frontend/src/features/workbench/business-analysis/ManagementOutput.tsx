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
        ? `当前首页建议为：${recommendationTitle}`
        : "先以正式余额读链路为准，再决定是否进入专题页继续下钻。",
    },
    {
      title: "当前限制",
      body:
        missingFxCount > 0
          ? `正式外汇仍缺 ${missingFxCount} 对，跨资产相关判断需继续复核。`
          : "当前没有首屏层面的外汇缺口提示。",
    },
    {
      title: "管理动作",
      body:
        recommendationActionLabel ??
        "先打开正式专题页，再根据证据完整度决定是否继续扩展分析。",
    },
    {
      title: "说明",
      body:
        recommendationDetail ??
        "经营页首屏不再硬写未接入的经营口径，专题页和受治理面板继续承担细项核实。",
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
