import { Button, Card } from "antd";

import type { AssetStructurePayload } from "../../../api/contracts";
import { formatYi, nativeToNumber } from "../utils/format";

const RATING_ORDER = [
  "AAA",
  "AA+",
  "AA",
  "AA-",
  "A+",
  "A",
  "A-",
  "BBB+",
  "BBB",
  "BBB-",
  "BB+",
  "BB",
  "B",
  "C",
  "D",
];

const RATING_COLORS: Record<string, string> = {
  AAA: "#1677ff",
  "AA+": "#52c41a",
  AA: "#fa8c16",
  "AA-": "#ff7a45",
};

function ratingRank(name: string): number {
  const i = RATING_ORDER.indexOf(name.trim().toUpperCase());
  return i >= 0 ? i : 500;
}

export function CreditRatingBlocks({
  data,
  loading,
}: {
  data: AssetStructurePayload | undefined;
  loading: boolean;
}) {
  const items = [...(data?.items ?? [])].sort(
    (a, b) => ratingRank(a.category) - ratingRank(b.category),
  );
  const total = items.reduce((s, i) => s + nativeToNumber(i.total_market_value), 0) || 1;

  return (
    <Card
      loading={loading}
      title="信用等级分布"
      extra={<Button type="link">更多</Button>}
      style={{ borderRadius: 8 }}
      styles={{ body: { padding: 16 } }}
    >
      <div style={{ display: "flex", width: "100%", gap: 4, minHeight: 120, alignItems: "stretch" }}>
        {items.length === 0 ? (
          <div style={{ color: "rgba(0,0,0,0.35)", padding: 16 }}>暂无数据</div>
        ) : (
          items.map((it) => {
            const w = (nativeToNumber(it.total_market_value) / total) * 100;
            const percentage = nativeToNumber(it.percentage);
            const bg =
              RATING_COLORS[it.category.trim().toUpperCase()] ??
              (it.category.includes("A") ? "#ff4d4f" : "#8c8c8c");
            return (
              <div
                key={it.category}
                style={{
                  flex: `${Math.max(w, 6)} 1 0`,
                  minWidth: 72,
                  background: bg,
                  borderRadius: 6,
                  padding: "12px 8px",
                  color: "#fff",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "center",
                  boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.15)",
                }}
              >
                <div style={{ fontWeight: 700, fontSize: 14 }}>{it.category || "—"}</div>
                <div style={{ fontSize: 13, marginTop: 6 }}>{formatYi(it.total_market_value)} 亿</div>
                <div style={{ fontSize: 12, opacity: 0.9, marginTop: 4 }}>{percentage.toFixed(2)}%</div>
              </div>
            );
          })
        )}
      </div>
    </Card>
  );
}
