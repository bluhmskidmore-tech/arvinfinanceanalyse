import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Modal, Spin, Table, Tabs, Typography } from "antd";

import { useApiClient } from "../../../api/client";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { formatAmountWan, formatAmountYi, formatRatePercent } from "../utils/format";

/** A股配色：红涨绿跌 — 余额上行红色，下行绿色 */
const UP_COLOR = "#cf1322";
const DOWN_COLOR = "#389e0d";

type Props = {
  open: boolean;
  onClose: () => void;
  customerName: string | null;
  reportDate?: string | null;
};

export default function CustomerDetailModal({ open, onClose, customerName, reportDate }: Props) {
  const client = useApiClient();

  const detailsQuery = useQuery({
    queryKey: ["positions", "customer-details", client.mode, customerName, reportDate ?? ""],
    queryFn: async () => {
      if (!customerName) {
        throw new Error("no customer");
      }
      const envelope = await client.getPositionsCustomerDetails({
        customerName,
        reportDate: reportDate ?? null,
      });
      return envelope.result;
    },
    enabled: open && Boolean(customerName),
    retry: false,
  });

  const trendQuery = useQuery({
    queryKey: ["positions", "customer-trend", client.mode, customerName, reportDate ?? ""],
    queryFn: async () => {
      if (!customerName) {
        throw new Error("no customer");
      }
      const envelope = await client.getPositionsCustomerTrend({
        customerName,
        endDate: reportDate ?? null,
        days: 30,
      });
      return envelope.result;
    },
    enabled: open && Boolean(customerName),
    retry: false,
  });

  const details = detailsQuery.data;
  const trend = trendQuery.data;

  const chartOption = useMemo((): EChartsOption | null => {
    const items = trend?.items ?? [];
    if (!items.length) {
      return null;
    }
    const balances = items.map((it) => parseFloat(it.balance));
    const first = balances[0] ?? 0;
    const last = balances[balances.length - 1] ?? 0;
    const stroke = last >= first ? UP_COLOR : DOWN_COLOR;
    const fill = last >= first ? "rgba(207, 19, 34, 0.12)" : "rgba(56, 158, 13, 0.12)";

    const dates = items.map((it) => it.date.slice(5));
    const yi = items.map((it) => parseFloat(it.balance) / 1e8);

    return {
      grid: { left: 48, right: 16, top: 16, bottom: 28 },
      tooltip: {
        trigger: "axis",
        formatter: (params: unknown) => {
          const list = Array.isArray(params) ? params : [params];
          const p = list[0] as { axisValue?: string; data?: number; dataIndex?: number };
          const idx = p.dataIndex ?? 0;
          const full = items[idx]?.date ?? p.axisValue ?? "";
          const val = p.data;
          return `${full}<br/>余额：${typeof val === "number" ? val.toFixed(4) : val} 亿元`;
        },
      },
      xAxis: {
        type: "category",
        data: dates,
        axisLabel: { fontSize: 11 },
      },
      yAxis: {
        type: "value",
        axisLabel: { formatter: (v: number) => `${v.toFixed(1)}亿` },
        splitLine: { lineStyle: { color: "#eef2f7" } },
      },
      series: [
        {
          type: "line",
          data: yi,
          smooth: true,
          symbol: "circle",
          symbolSize: 6,
          lineStyle: { width: 2, color: stroke },
          areaStyle: { color: fill },
          itemStyle: { color: stroke },
        },
      ],
    };
  }, [trend?.items]);

  return (
    <Modal
      title={
        <div>
          <Typography.Title level={4} style={{ margin: 0 }}>
            {customerName ?? "客户明细"}
          </Typography.Title>
          <Typography.Text type="secondary">
            报告日：{details?.report_date || reportDate || "—"}
          </Typography.Text>
        </div>
      }
      open={open}
      onCancel={onClose}
      footer={null}
      width={920}
      destroyOnHidden
    >
      {details ? (
        <div style={{ marginBottom: 16, display: "flex", gap: 24, flexWrap: "wrap" }}>
          <div>
            <Typography.Text type="secondary">总市值</Typography.Text>
            <div style={{ fontSize: 20, fontWeight: 600 }}>{formatAmountYi(details.total_market_value)}</div>
          </div>
          <div>
            <Typography.Text type="secondary">债券数量</Typography.Text>
            <div style={{ fontSize: 20, fontWeight: 600 }}>{details.bond_count} 只</div>
          </div>
          <div>
            <Typography.Text type="secondary">趋势周期</Typography.Text>
            <div style={{ fontSize: 20, fontWeight: 600 }}>{trend?.days ?? 30} 天</div>
          </div>
        </div>
      ) : null}

      <Tabs
        items={[
          {
            key: "details",
            label: "持仓明细",
            children: detailsQuery.isLoading ? (
              <div style={{ textAlign: "center", padding: 32 }}>
                <Spin />
              </div>
            ) : details && details.items.length > 0 ? (
              <Table
                size="small"
                pagination={false}
                scroll={{ y: 320 }}
                dataSource={details.items.map((row) => ({ key: row.bond_code, ...row }))}
                columns={[
                  { title: "债券代码", dataIndex: "bond_code", fixed: "left" },
                  { title: "券种", dataIndex: "sub_type", render: (v: string | null) => v || "—" },
                  {
                    title: "评级",
                    dataIndex: "rating",
                    render: (r: string) => (
                      <Typography.Text
                        style={{
                          padding: "2px 8px",
                          borderRadius: 6,
                          background:
                            r === "AAA"
                              ? "#f6ffed"
                              : r.startsWith("AA")
                                ? "#fffbe6"
                                : r === "未评级"
                                  ? "#fafafa"
                                  : "#fff2e8",
                          color:
                            r === "AAA"
                              ? "#237804"
                              : r.startsWith("AA")
                                ? "#ad6800"
                                : r === "未评级"
                                  ? "#595959"
                                  : "#ad4e00",
                        }}
                      >
                        {r}
                      </Typography.Text>
                    ),
                  },
                  {
                    title: "行业",
                    dataIndex: "industry",
                    ellipsis: true,
                  },
                  {
                    title: "市值",
                    dataIndex: "market_value",
                    align: "right",
                    render: (v: string) => formatAmountWan(v),
                  },
                  {
                    title: "收益率",
                    dataIndex: "yield_rate",
                    align: "right",
                    render: (v: string | null) => formatRatePercent(v),
                  },
                  {
                    title: "到期日",
                    dataIndex: "maturity_date",
                    align: "right",
                    render: (v: string | null) => v || "—",
                  },
                ]}
              />
            ) : (
              <Typography.Text type="secondary">暂无持仓数据</Typography.Text>
            ),
          },
          {
            key: "trend",
            label: "余额趋势",
            children: trendQuery.isLoading ? (
              <div style={{ textAlign: "center", padding: 32 }}>
                <Spin />
              </div>
            ) : chartOption ? (
              <ReactECharts option={chartOption} style={{ height: 280 }} notMerge lazyUpdate />
            ) : (
              <Typography.Text type="secondary">暂无趋势数据</Typography.Text>
            ),
          },
        ]}
      />
    </Modal>
  );
}
