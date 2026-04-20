import { useMemo } from "react";
import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import { designTokens } from "../../../theme/designSystem";
import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

const TENORS = ["1M", "3M", "6M", "9M", "1Y"] as const;

type MatrixRow = Record<"rating" | (typeof TENORS)[number], string | number> & { key: string };

export function NcdMatrix() {
  const columns: ColumnsType<MatrixRow> = useMemo(
    () => [
      { title: "评级/期限", dataIndex: "rating", key: "rating", fixed: "left", width: 72 },
      ...TENORS.map((t) => ({
        title: t,
        dataIndex: t,
        key: t,
        align: "right" as const,
        width: 72,
      })),
    ],
    [],
  );

  return (
    <section data-testid="market-data-ncd-matrix" style={marketDataPanelStyle}>
      <h2 style={marketDataBlockTitleStyle}>同业存单</h2>
      <p
        style={{
          margin: `0 0 ${designTokens.space[3]}px`,
          color: designTokens.color.neutral[600],
          fontSize: designTokens.fontSize[12],
          lineHeight: designTokens.lineHeight.normal,
        }}
      >
        评级×期限矩阵需接入行情侧矩阵接口；有数据后将按利率高低做单元格热力着色（绿浅红深）。
      </p>
      <Table<MatrixRow>
        size="small"
        pagination={false}
        columns={columns}
        dataSource={[]}
        rowKey="key"
        scroll={{ x: true }}
        locale={{
          emptyText: "当前未返回同业存单矩阵数据。",
        }}
      />
    </section>
  );
}
