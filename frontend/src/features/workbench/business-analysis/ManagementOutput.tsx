import { SectionCard } from "../../../components/SectionCard";

const ITEMS: { title: string; body: string }[] = [
  {
    title: "经营判断",
    body: "收益仍由债券票息主导，利差不厚但相对稳定。",
  },
  {
    title: "核心矛盾",
    body: "负债对发行类工具依赖度高，短端滚续压力偏大。",
  },
  {
    title: "当前优先级",
    body: "先管缺口和滚续，再谋进一步提升收益。",
  },
  {
    title: "下钻方向",
    body: "资产负债分析看缺口，债券分析看利差，市场数据看盘中变化。",
  },
];

export function ManagementOutput() {
  return (
    <SectionCard title="管理输出">
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {ITEMS.map((it) => (
          <div key={it.title}>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#162033", marginBottom: 6 }}>
              {it.title}
            </div>
            <p style={{ margin: 0, fontSize: 14, color: "#31425b", lineHeight: 1.75 }}>{it.body}</p>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
