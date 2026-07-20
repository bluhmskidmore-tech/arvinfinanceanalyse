import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Modal, Spin, Table, Tabs, Typography } from "antd";
import type { TableColumnsType } from "antd";
import { Link } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import type { CustomerBondDetailItem } from "../../../api/contracts";
import { buildBondTradingDeskPath } from "../../bond-trading-desk/lib/bondTradingDeskPageModel";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { ibTokens } from "../../../theme/designSystem";
import { formatAmountYi, formatRatePercent } from "../utils/format";
import "./CustomerDetailModal.css";

type CustomerBondDetailRow = CustomerBondDetailItem & { key: string };

type Props = {
  open: boolean;
  onClose: () => void;
  customerName: string | null;
  reportDate?: string | null;
};

type CnEquityColors = { up: string; down: string };

function ratingToneClass(rating: string): string {
  if (rating === "AAA") {
    return "positions-customer-detail__rating--aaa";
  }
  if (rating.startsWith("AA")) {
    return "positions-customer-detail__rating--aa";
  }
  if (rating === "未评级") {
    return "positions-customer-detail__rating--unrated";
  }
  return "positions-customer-detail__rating--other";
}

function readCssVar(host: Element | null, name: string): string {
  if (!host) {
    return "";
  }
  return getComputedStyle(host).getPropertyValue(name).trim();
}

export default function CustomerDetailModal({ open, onClose, customerName, reportDate }: Props) {
  const client = useApiClient();
  const hostRef = useRef<HTMLDivElement>(null);
  const [cnEquityColors, setCnEquityColors] = useState<CnEquityColors>({ up: "", down: "" });

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

  useLayoutEffect(() => {
    if (!open) {
      return;
    }
    const host = hostRef.current;
    setCnEquityColors({
      up: readCssVar(host, "--cn-equity-up"),
      down: readCssVar(host, "--cn-equity-down"),
    });
  }, [open, trend?.items]);

  const detailRows = useMemo<CustomerBondDetailRow[]>(
    () => (details?.items ?? []).map((row) => ({ key: row.bond_code, ...row })),
    [details?.items],
  );

  const detailColumns = useMemo<TableColumnsType<CustomerBondDetailRow>>(
    () => [
      {
        title: "债券代码",
        dataIndex: "bond_code",
        fixed: "left",
        render: (bondCode: string) =>
          bondCode && reportDate ? (
            <Link
              to={buildBondTradingDeskPath(bondCode, reportDate)}
              data-testid={`customer-detail-trading-desk-link-${bondCode}`}
            >
              {bondCode}
            </Link>
          ) : (
            bondCode || "—"
          ),
      },
      { title: "券种", dataIndex: "sub_type", render: (v: string | null) => v || "—" },
      {
        title: "评级",
        dataIndex: "rating",
        render: (r: string) => (
          <Typography.Text className={`positions-customer-detail__rating ${ratingToneClass(r)}`}>
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
        title: "市值(亿元)",
        dataIndex: "market_value",
        align: "right",
        render: (v: string) => formatAmountYi(v),
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
    ],
    [reportDate],
  );

  const chartOption = useMemo((): EChartsOption | null => {
    const items = trend?.items ?? [];
    if (!items.length) {
      return null;
    }
    const balances = items.map((it) => parseFloat(it.balance));
    const first = balances[0] ?? 0;
    const last = balances[balances.length - 1] ?? 0;
    // Page-local --cn-equity-* (A-share 红涨绿跌). Do NOT use --ib-up/--ib-down.
    const stroke = last >= first ? cnEquityColors.up : cnEquityColors.down;

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
        splitLine: { lineStyle: { color: ibTokens.color.hairline } },
      },
      series: [
        {
          type: "line",
          data: yi,
          smooth: true,
          symbol: "circle",
          symbolSize: 6,
          lineStyle: { width: 2, color: stroke },
          areaStyle: { color: stroke, opacity: 0.12 },
          itemStyle: { color: stroke },
        },
      ],
    };
  }, [trend?.items, cnEquityColors.up, cnEquityColors.down]);

  return (
    <Modal
      rootClassName="positions-customer-detail"
      title={
        <div>
          <Typography.Title level={4} className="positions-customer-detail__title">
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
      <div ref={hostRef} className="positions-customer-detail">
        {details ? (
          <div className="positions-customer-detail__kpi-row">
            <div>
              <Typography.Text type="secondary">总市值</Typography.Text>
              <div className="positions-customer-detail__kpi-value">
                {formatAmountYi(details.total_market_value)}
              </div>
            </div>
            <div>
              <Typography.Text type="secondary">债券数量</Typography.Text>
              <div className="positions-customer-detail__kpi-value">{details.bond_count} 只</div>
            </div>
            <div>
              <Typography.Text type="secondary">趋势周期</Typography.Text>
              <div className="positions-customer-detail__kpi-value">{trend?.days ?? 30} 天</div>
            </div>
          </div>
        ) : null}

        <Tabs
          items={[
            {
              key: "details",
              label: "持仓明细",
              children: detailsQuery.isLoading ? (
                <div className="positions-customer-detail__loading">
                  <Spin />
                </div>
              ) : details && details.items.length > 0 ? (
                <Table
                  size="small"
                  pagination={false}
                  scroll={{ y: 320 }}
                  dataSource={detailRows}
                  columns={detailColumns}
                />
              ) : (
                <Typography.Text type="secondary">暂无持仓数据</Typography.Text>
              ),
            },
            {
              key: "trend",
              label: "余额趋势",
              children: trendQuery.isLoading ? (
                <div className="positions-customer-detail__loading">
                  <Spin />
                </div>
              ) : chartOption ? (
                <ReactECharts
                  option={chartOption}
                  className="positions-customer-detail__chart"
                  notMerge
                  lazyUpdate
                />
              ) : (
                <Typography.Text type="secondary">暂无趋势数据</Typography.Text>
              ),
            },
          ]}
        />
      </div>
    </Modal>
  );
}
