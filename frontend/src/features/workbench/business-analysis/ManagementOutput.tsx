import { SectionCard } from "../../../components/SectionCard";

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
      body:
        recommendationTitle ??
        "先以正式余额读链路为准，再决定是否进入专题页继续下钻。",
    },
    {
      title: "当前限制",
      body:
        missingFxCount > 0
          ? `Formal FX 仍缺 ${missingFxCount} 对，跨资产相关判断需继续复核。`
          : "当前没有首屏层面的 FX 缺口提示。",
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
    <SectionCard title="管理输出">
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {items.map((item) => (
          <div key={item.title}>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#162033", marginBottom: 6 }}>
              {item.title}
            </div>
            <p style={{ margin: 0, fontSize: 14, color: "#31425b", lineHeight: 1.75 }}>
              {item.body}
            </p>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
