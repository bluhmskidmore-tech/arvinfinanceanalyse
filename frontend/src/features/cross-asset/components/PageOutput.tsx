import { SectionCard } from "../../../components/SectionCard";

const ITEMS: { label: string; body: string }[] = [
  { label: "环境标签", body: "资金偏松 / 外部约束增强 / 长端偏贵" },
  { label: "方向判断", body: "中段优于长端，信用以票息为主" },
  { label: "主要风险", body: "美债继续上行，油价持续抬升" },
  { label: "关注窗口", body: "1Y AAA 存单, 5Y 国开" },
];

export function PageOutput() {
  return (
    <SectionCard title="页面输出">
      <dl style={{ margin: 0, fontSize: 13, color: "#475569", lineHeight: 1.65 }}>
        {ITEMS.map((item) => (
          <div key={item.label} style={{ marginBottom: item.label === "关注窗口" ? 0 : 14 }}>
            <dt style={{ fontWeight: 700, color: "#334155", margin: 0 }}>{item.label}</dt>
            <dd style={{ margin: "6px 0 0" }}>{item.body}</dd>
          </div>
        ))}
      </dl>
    </SectionCard>
  );
}
