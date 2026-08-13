import { useEffect, useMemo, useState } from "react";
import { Alert, Card, Space, Spin, Statistic, Table } from "antd";
import { Link } from "react-router-dom";
import type { BondTopHoldingsPayload, Numeric } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import { buildBondTradingDeskPath } from "../../bond-trading-desk/lib/bondTradingDeskPageModel";
import { designTokens } from "../../../theme/designSystem";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import { EM_DASH } from "../../../utils/format";
import { formatPct, formatYi } from "../utils/formatters";

interface Props {
  reportDate: string;
}

const TOP_N_OPTIONS = [10, 20, 30, 50, 100] as const;

const buildColumns = (reportDate: string) => [
  { title: "代码", dataIndex: "instrument_code", key: "instrument_code" },
  { title: "名称", dataIndex: "instrument_name", key: "instrument_name" },
  { title: "发行人", dataIndex: "issuer_name", key: "issuer_name" },
  { title: "评级", dataIndex: "rating", key: "rating" },
  { title: "资产类别", dataIndex: "asset_class", key: "asset_class" },
  { title: "市值", dataIndex: "market_value", key: "market_value", render: formatYi },
  { title: "面值", dataIndex: "face_value", key: "face_value", render: formatYi },
  {
    title: "YTM",
    dataIndex: "ytm",
    key: "ytm",
    render: (v: Numeric) => formatPct(v),
  },
  {
    title: "修正久期",
    dataIndex: "modified_duration",
    key: "modified_duration",
    render: (v: Numeric) => v.display,
  },
  {
    title: "权重",
    dataIndex: "weight",
    key: "weight",
    render: (v: Numeric) => formatPct(v),
  },
  {
    title: "单券台",
    key: "trading_desk",
    render: (_: unknown, row: BondTopHoldingsPayload["items"][number]) => (
      <Link
        to={buildBondTradingDeskPath(row.instrument_code, reportDate)}
        data-testid={`bond-trading-desk-link-${row.instrument_code}`}
      >
        打开
      </Link>
    ),
  },
];

export function TopHoldingsView({ reportDate }: Props) {
  const client = useApiClient();
  const [topN, setTopN] = useState<number>(20);
  const [data, setData] = useState<BondTopHoldingsPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const envelope = await client.getBondAnalyticsTopHoldings(reportDate, topN);
        if (!cancelled) setData(envelope.result);
      } catch (e: unknown) {
        if (!cancelled) setError((e as Error).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    if (reportDate) void run();
    return () => {
      cancelled = true;
    };
  }, [client, reportDate, topN]);

  const columns = useMemo(() => buildColumns(reportDate), [reportDate]);

  const topWeightSum = useMemo(() => {
    if (!data?.items.length) return null;
    let sum = 0;
    for (const row of data.items) {
      const raw = bondNumericRaw(row.weight);
      if (raw === null) return null;
      sum += raw;
    }
    return sum;
  }, [data]);

  if (!reportDate) {
    return null;
  }

  return (
    <div
      data-testid="top-holdings-view"
      style={{ display: "flex", flexDirection: "column", gap: designTokens.space[3] }}
    >
      <Space align="center" wrap data-testid="bond-analytics-top-holdings-toolbar">
        <span style={{ color: "var(--dh-api-muted)" }}>展示条数</span>
        <select
          aria-label="bond-analytics-top-holdings-topn"
          data-testid="bond-analytics-top-holdings-topn"
          value={topN}
          onChange={(e) => setTopN(Number(e.target.value))}
          style={{
            minWidth: 88,
            height: 32,
            border: "1px solid var(--dh-api-line)",
            borderRadius: designTokens.radius.sm,
            background: "var(--dh-api-panel-2)",
            color: "var(--dh-api-ink)",
            fontSize: designTokens.fontSize[14],
          }}
        >
          {TOP_N_OPTIONS.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </Space>
      {error ? (
        <Alert type="error" message={error} showIcon />
      ) : loading && !data ? (
        <div data-testid="top-holdings-loading" style={{ padding: 24 }}>
          <Spin />
        </div>
      ) : !data ? null : (
        <>
          {data.warnings.length > 0 ? (
            <Alert type="warning" showIcon message={data.warnings.join(" ")} />
          ) : null}
          <Card size="small">
            <Statistic
              title={`Top ${data.top_n} 合计市值占比（相对组合总市值）`}
              value={
                topWeightSum === null
                  ? EM_DASH
                  : formatPct({
                      raw: topWeightSum,
                      unit: "ratio",
                      display: "",
                      precision: 4,
                      sign_aware: false,
                    })
              }
            />
          </Card>
          <Card size="small" title="持仓明细">
            <Table
              size="small"
              rowKey={(row) => row.instrument_code}
              columns={columns}
              dataSource={data.items}
              pagination={false}
              scroll={{ x: true }}
            />
          </Card>
        </>
      )}
    </div>
  );
}

export default TopHoldingsView;
