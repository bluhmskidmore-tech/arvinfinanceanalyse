import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Modal, Spin, Table, Tabs, Typography } from "antd";
import type { TableColumnsType } from "antd";
import { Link } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import type { CustomerBondDetailItem } from "../../../api/contracts";
import { buildBondTradingDeskPath } from "../../bond-trading-desk/lib/bondTradingDeskPageModel";
import { type EChartsOption } from "../../../lib/echarts";
import { BaseChart } from "../../../components/charts/BaseChart";
import { nocturneTokens } from "../../../theme/designSystem";
import { POSITIONS_QUERY_STALE_TIME_MS } from "../model/positionsPageModel";
import { formatAmountYi, formatAmountYiNumber, formatRatePercent } from "../utils/format";
import { EM_DASH } from "../../../utils/format";
import "./CustomerDetailModal.css";

type CustomerBondDetailRow = CustomerBondDetailItem & { key: string };

type Props = {
  open: boolean;
  onClose: () => void;
  customerName: string | null;
  reportDate?: string | null;
};

/*
 * 客户余额是持仓规模方向而非行情涨跌，不适用 A 股红涨绿跌行情惯例；
 * 对齐全站绿涨红跌语义（DESIGN.md §2.2/§4）。canvas 不能消费 CSS 变量，
 * 取色走 nocturneTokens 常量（数值源 = tokens.css Nocturne scope 的去饱和
 * 红/绿），与 CustomerDetailModal.css 的 --balance-trend-* 语义锚点同源。
 */
const BALANCE_TREND_UP = nocturneTokens.color.green;
const BALANCE_TREND_DOWN = nocturneTokens.color.red;

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
    staleTime: POSITIONS_QUERY_STALE_TIME_MS,
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
    staleTime: POSITIONS_QUERY_STALE_TIME_MS,
    retry: false,
  });

  const details = detailsQuery.data;
  const trend = trendQuery.data;

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
            bondCode || EM_DASH
          ),
      },
      { title: "券种", dataIndex: "sub_type", render: (v: string | null) => v || EM_DASH },
      {
        // 后端已返回未用字段补展示：枚举值属证据引用，原样透出。
        title: "资产分类",
        dataIndex: "asset_class",
        render: (v: string | null) => v || EM_DASH,
      },
      {
        title: "评级",
        dataIndex: "rating",
        /* 真实数据大量 rating 为空串：空白评级渲染 EM_DASH 纯文本，不出空胶囊。 */
        render: (r: string | null) =>
          r?.trim() ? (
            <Typography.Text
              className={`positions-customer-detail__rating ${ratingToneClass(r)}`}
            >
              {r}
            </Typography.Text>
          ) : (
            EM_DASH
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
        className: "positions-customer-detail__num-cell",
        render: (v: string) => formatAmountYiNumber(v),
      },
      {
        title: "收益率",
        dataIndex: "yield_rate",
        align: "right",
        className: "positions-customer-detail__num-cell",
        render: (v: string | null) => formatRatePercent(v),
      },
      {
        title: "到期日",
        dataIndex: "maturity_date",
        align: "right",
        className: "positions-customer-detail__num-cell",
        render: (v: string | null) => v || EM_DASH,
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
    const stroke = last >= first ? BALANCE_TREND_UP : BALANCE_TREND_DOWN;

    const dates = items.map((it) => it.date.slice(5));
    const yi = items.map((it) => parseFloat(it.balance) / 1e8);

    return {
      grid: { left: 48, right: 16, top: 16, bottom: 28 },
      tooltip: {
        trigger: "axis",
        backgroundColor: nocturneTokens.color.panel2,
        borderColor: nocturneTokens.color.line,
        textStyle: { color: nocturneTokens.color.ink, fontSize: 12 },
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
        axisLine: { lineStyle: { color: nocturneTokens.color.lineSoft } },
        axisLabel: { fontSize: 11, color: nocturneTokens.color.inkMuted },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          formatter: (v: number) => `${v.toFixed(1)}亿`,
          fontSize: 11,
          color: nocturneTokens.color.inkMuted,
        },
        splitLine: { lineStyle: { color: nocturneTokens.color.lineSoft } },
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
  }, [trend?.items]);

  return (
    <Modal
      rootClassName="positions-customer-detail"
      /*
       * antd Modal 挂 body，不继承页根 scope（portal 主题逃逸）。照
       * ledger-pnl 抽屉补 scope 的先例，用 modalRender 在 .ant-modal-content
       * 外包一层 Nocturne scope 容器（覆盖 header/body 全部弹窗内容），
       * 弹窗内 --dh-api-* 才解析为 Nocturne 值。
       */
      modalRender={(node) => (
        <div
          className="theme-dh-api positions-customer-detail__scope"
          data-moss-theme-scope="positions"
          data-testid="positions-customer-detail-scope"
        >
          {node}
        </div>
      )}
      title={
        <div>
          <Typography.Title level={4} className="positions-customer-detail__title">
            {customerName ?? "客户明细"}
          </Typography.Title>
          <Typography.Text type="secondary">
            报告日：{details?.report_date || reportDate || EM_DASH}
          </Typography.Text>
        </div>
      }
      open={open}
      onCancel={onClose}
      footer={null}
      width={920}
      destroyOnHidden
    >
      <div className="positions-customer-detail">
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
              ) : (
                <>
                  {trend?.start_date && trend?.end_date ? (
                    <div className="positions-customer-detail__trend-head">
                      {/* 后端返回的真实窗口原样透出（mock 语义缺陷不在前端修饰）。 */}
                      <span className="positions-customer-detail__trend-window">
                        {`窗口 ${trend.start_date} ~ ${trend.end_date}`}
                      </span>
                    </div>
                  ) : null}
                  {chartOption ? (
                    <BaseChart option={chartOption} height={280} />
                  ) : (
                    <Typography.Text type="secondary">暂无趋势数据</Typography.Text>
                  )}
                </>
              ),
            },
          ]}
        />
      </div>
    </Modal>
  );
}
