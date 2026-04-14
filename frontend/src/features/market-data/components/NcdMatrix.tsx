import { useMemo } from "react";
import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

const TENORS = ["1M", "3M", "6M", "9M", "1Y"] as const;

type RatingRow = {
  key: string;
  rating: string;
} & Record<(typeof TENORS)[number], number>;

const ROWS: RatingRow[] = [
  { key: "aaa", rating: "AAA", "1M": 1.95, "3M": 2.05, "6M": 2.1, "9M": 2.1, "1Y": 2.15 },
  { key: "aap", rating: "AA+", "1M": 1.95, "3M": 2.15, "6M": 2.2, "9M": 2.2, "1Y": 2.3 },
  { key: "aa", rating: "AA", "1M": 2.3, "3M": 2.45, "6M": 2.6, "9M": 2.7, "1Y": 2.55 },
];

function matrixMinMax(rows: RatingRow[]) {
  let min = Infinity;
  let max = -Infinity;
  for (const row of rows) {
    for (const t of TENORS) {
      const v = row[t];
      min = Math.min(min, v);
      max = Math.max(max, v);
    }
  }
  if (!Number.isFinite(min) || min === max) {
    return { min: min || 0, max: (max || 1) + 0.01 };
  }
  return { min, max };
}

/** 低利率浅绿、高利率浅红 */
function cellBackground(value: number, min: number, max: number) {
  const t = (value - min) / (max - min);
  const r = Math.round(237 + (255 - 237) * t);
  const g = Math.round(248 + (236 - 248) * t);
  const b = Math.round(242 + (234 - 242) * t);
  return `rgb(${r}, ${g}, ${b})`;
}

export function NcdMatrix() {
  const { min, max } = useMemo(() => matrixMinMax(ROWS), []);

  const columns: ColumnsType<RatingRow> = useMemo(
    () => [
      { title: "评级/期限", dataIndex: "rating", key: "rating", fixed: "left", width: 72 },
      ...TENORS.map((t) => ({
        title: t,
        dataIndex: t,
        key: t,
        align: "right" as const,
        width: 72,
        render: (v: number) => (
          <span
            style={{
              display: "block",
              margin: "-8px -12px",
              padding: "8px 12px",
              background: cellBackground(v, min, max),
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {v.toFixed(2)}
          </span>
        ),
      })),
    ],
    [min, max],
  );

  return (
    <section data-testid="market-data-ncd-matrix" style={marketDataPanelStyle}>
      <h2 style={marketDataBlockTitleStyle}>同业存单矩阵（%）</h2>
      <p style={{ margin: "0 0 12px", color: "#5c6b82", fontSize: 12, lineHeight: 1.5 }}>
        演示数据：颜色越深表示利率越高（绿浅红深）。
      </p>
      <Table<RatingRow>
        size="small"
        pagination={false}
        columns={columns}
        dataSource={ROWS}
        rowKey="key"
        scroll={{ x: true }}
      />
    </section>
  );
}
