import { useMemo } from "react";
import { Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { MacroBondLinkageTopCorrelation } from "../../../api/contracts";

import { tabularNumsStyle } from "../../../theme/designSystem";
import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

export type SpreadTenorSlot = {
  tenor: string;
  point: MacroBondLinkageTopCorrelation | null;
};

type Row = {
  key: string;
  tenor: string;
  seriesName: string;
  corr1y: string;
  leadLag: string;
  direction: string;
};

function formatCorrelation(value: number | null | undefined) {
  if (value == null) {
    return "不可用";
  }
  return value.toFixed(2);
}

export function LinkageSpreadTenorTable({
  slots,
  loading,
}: {
  slots: SpreadTenorSlot[];
  loading?: boolean;
}) {
  const dataSource: Row[] = useMemo(
    () =>
      slots.map((s) => ({
        key: s.tenor,
        tenor: s.tenor,
        seriesName: s.point?.series_name ?? "—",
        corr1y: s.point ? formatCorrelation(s.point.correlation_1y) : "—",
        leadLag: s.point ? `${s.point.lead_lag_days} 天` : "—",
        direction: s.point?.direction ?? "—",
      })),
    [slots],
  );

  const columns: ColumnsType<Row> = useMemo(
    () => [
      { title: "期限", dataIndex: "tenor", key: "tenor", width: 56 },
      { title: "代表序列", dataIndex: "seriesName", key: "seriesName", ellipsis: true },
      {
        title: "corr 1Y",
        dataIndex: "corr1y",
        key: "corr1y",
        align: "right",
        width: 72,
        render: (v: string) => <span style={tabularNumsStyle}>{v}</span>,
      },
      { title: "lead/lag", dataIndex: "leadLag", key: "leadLag", align: "right", width: 88 },
      { title: "方向", dataIndex: "direction", key: "direction", width: 88 },
    ],
    [],
  );

  return (
    <section data-testid="market-data-linkage-spread-table" style={marketDataPanelStyle}>
      <h2 style={marketDataBlockTitleStyle}>信用利差</h2>
      <Typography.Paragraph type="secondary">
        来自宏观-债市联动的 credit_spread 结构化维度；无数据时表格为空。
      </Typography.Paragraph>
      <Table<Row>
        size="small"
        pagination={false}
        loading={loading}
        columns={columns}
        dataSource={dataSource}
        rowKey="key"
        locale={{ emptyText: "当前报告日下未返回利差相关性。" }}
      />
    </section>
  );
}
