import { Button, Card } from "antd";

import type { AssetStructurePayload } from "../../../api/contracts";
import { ibChartTheme } from "../../../components/charts/chartTheme";
import { ibTokens } from "../../../theme/designSystem";
import styles from "../bondDashboard.module.css";
import { formatRatePercent, formatYi, nativeToNumber } from "../utils/format";

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

const IB_CHART_PALETTE = ibChartTheme.categoricalPalette;
const IB_CHART_NEGATIVE = ibTokens.color.down;

const RATING_COLORS: Record<string, string> = {
  AAA: IB_CHART_PALETTE[0],
  "AA+": IB_CHART_PALETTE[1],
  AA: IB_CHART_PALETTE[2],
  "AA-": IB_CHART_PALETTE[3],
  "A+": IB_CHART_PALETTE[4],
  A: IB_CHART_PALETTE[5],
  "A-": IB_CHART_PALETTE[5],
};

function ratingRank(name: string): number {
  const i = RATING_ORDER.indexOf(name.trim().toUpperCase());
  return i >= 0 ? i : 500;
}

function ratingColor(category: string, index: number): string {
  const key = category.trim().toUpperCase();
  if (RATING_COLORS[key]) {
    return RATING_COLORS[key];
  }
  if (category.includes("A")) {
    return IB_CHART_NEGATIVE;
  }
  return IB_CHART_PALETTE[index % IB_CHART_PALETTE.length];
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
  const total =
    items.reduce((s, i) => {
      const raw = nativeToNumber(i.total_market_value);
      return raw === null ? s : s + raw;
    }, 0) || 1;

  return (
    <Card
      loading={loading}
      title="信用等级分布"
      extra={<Button type="link">更多</Button>}
      rootClassName={styles.card}
      styles={{ body: { padding: 16 } }}
    >
      <div className={styles.ratingStrip}>
        {items.length === 0 ? (
          <div className={styles.ratingEmpty}>—</div>
        ) : (
          items.map((it, index) => {
            const rawMarketValue = nativeToNumber(it.total_market_value);
            const w = rawMarketValue === null ? 6 : (rawMarketValue / total) * 100;
            const percentage = formatRatePercent(it.percentage);
            const bg = ratingColor(it.category, index);
            return (
              <div
                key={it.category}
                className={styles.ratingBlock}
                style={{
                  flex: `${Math.max(w, 6)} 1 0`,
                  background: bg,
                }}
              >
                <div className={styles.ratingBlockCategory}>{it.category || "—"}</div>
                <div className={styles.ratingBlockAmount}>{formatYi(it.total_market_value)} 亿</div>
                <div className={styles.ratingBlockPct}>
                  {percentage === "—" ? "—" : `${percentage}%`}
                </div>
              </div>
            );
          })
        )}
      </div>
    </Card>
  );
}
