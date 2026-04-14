import { SectionCard } from "../../../components/SectionCard";

type GapRow = { tenor: string; netGap: string; note: string };

const GAP_ROWS: GapRow[] = [
  { tenor: "1年内净缺口", netGap: "-373.0", note: "短端滚续敏感" },
  { tenor: "1-3年净缺口", netGap: "-128.5", note: "中期再定价" },
  { tenor: "3年以上净缺口", netGap: "+96.2", note: "长久期缓冲" },
];

export function TenorConcentrationPanel() {
  return (
    <SectionCard title="期限与集中度（示意）">
      <p style={{ margin: "0 0 12px", fontSize: 13, color: "#5c6b82", lineHeight: 1.6 }}>
        下列缺口与期限为经营管理示意读数，正式阈值与口径以资产负债分析页及风控规则为准。
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {GAP_ROWS.map((row) => (
          <div
            key={row.tenor}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              padding: "12px 14px",
              borderRadius: 12,
              border: "1px solid #e4ebf5",
              background: row.netGap.startsWith("-") ? "#fff7f0" : "#f6ffed",
            }}
          >
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#162033" }}>{row.tenor}</div>
              <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>{row.note}</div>
            </div>
            <div
              style={{
                fontSize: 15,
                fontWeight: 700,
                fontVariantNumeric: "tabular-nums",
                color: row.netGap.startsWith("-") ? "#c2410c" : "#15803d",
              }}
            >
              {row.netGap} 亿
            </div>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
