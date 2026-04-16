import { Button, Card, Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { PortfolioComparisonItem, PortfolioComparisonPayload } from "../../../api/contracts";
import { formatDv01Wan, formatRatePercent, formatYi, nativeToNumber } from "../utils/format";

export function PortfolioTable({
  data,
  loading,
}: {
  data: PortfolioComparisonPayload | undefined;
  loading: boolean;
}) {
  const rows = data?.items ?? [];
  const totalMv = rows.reduce((s, r) => s + nativeToNumber(r.total_market_value), 0);
  const totalDv01 = rows.reduce((s, r) => s + nativeToNumber(r.total_dv01), 0);
  const totalBonds = rows.reduce((s, r) => s + r.bond_count, 0);

  let wYtm = 0;
  let wDur = 0;
  if (totalMv > 0) {
    for (const r of rows) {
      const w = nativeToNumber(r.total_market_value) / totalMv;
      wYtm += w * nativeToNumber(r.weighted_ytm);
      wDur += w * nativeToNumber(r.weighted_duration);
    }
  }

  const columns: ColumnsType<PortfolioComparisonItem> = [
    { title: "组合名称", dataIndex: "portfolio_name", key: "portfolio_name" },
    {
      title: "规模(亿)",
      dataIndex: "total_market_value",
      key: "mv",
      align: "right",
      render: (v: string) => formatYi(v),
    },
    {
      title: "收益率(%)",
      dataIndex: "weighted_ytm",
      key: "ytm",
      align: "right",
      render: (v: string) => formatRatePercent(v),
    },
    {
      title: "久期(年)",
      dataIndex: "weighted_duration",
      key: "dur",
      align: "right",
      render: (v: string) => nativeToNumber(v).toFixed(2),
    },
    {
      title: "DV01(万元)",
      dataIndex: "total_dv01",
      key: "dv01",
      align: "right",
      render: (v: string) => formatDv01Wan(v),
    },
    { title: "数量", dataIndex: "bond_count", key: "n", align: "right" },
  ];

  const footerRow: PortfolioComparisonItem = {
    portfolio_name: "合计 / 加权",
    total_market_value: String(totalMv),
    weighted_ytm: String(wYtm),
    weighted_duration: String(wDur),
    total_dv01: String(totalDv01),
    bond_count: totalBonds,
  };

  return (
    <Card
      loading={loading}
      title="组合表现"
      extra={<Button type="link">更多</Button>}
      style={{ borderRadius: 8 }}
      styles={{ body: { padding: 0 } }}
    >
      <Table<PortfolioComparisonItem>
        size="small"
        pagination={false}
        rowKey={(r) => r.portfolio_name}
        columns={columns}
        dataSource={rows}
        summary={() => (
          <Table.Summary fixed>
            <Table.Summary.Row>
              <Table.Summary.Cell index={0}>
                <strong>{footerRow.portfolio_name}</strong>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={1} align="right">
                <strong>{formatYi(footerRow.total_market_value)}</strong>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={2} align="right">
                <strong>{formatRatePercent(String(wYtm))}</strong>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={3} align="right">
                <strong>{nativeToNumber(footerRow.weighted_duration).toFixed(2)}</strong>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={4} align="right">
                <strong>{formatDv01Wan(footerRow.total_dv01)}</strong>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={5} align="right">
                <strong>{footerRow.bond_count}</strong>
              </Table.Summary.Cell>
            </Table.Summary.Row>
          </Table.Summary>
        )}
      />
    </Card>
  );
}
