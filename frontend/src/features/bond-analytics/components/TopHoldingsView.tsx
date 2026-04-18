import { useEffect, useMemo, useState } from "react";
import { Alert, Card, Select, Space, Spin, Statistic, Table } from "antd";
import type { BondTopHoldingsPayload, Numeric } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import { formatPct, formatWan } from "../utils/formatters";

interface Props {
  reportDate: string;
}

const TOP_N_OPTIONS = [10, 20, 30, 50, 100] as const;

const columns = [
  { title: "代码", dataIndex: "instrument_code", key: "instrument_code" },
  { title: "名称", dataIndex: "instrument_name", key: "instrument_name" },
  { title: "发行人", dataIndex: "issuer_name", key: "issuer_name" },
  { title: "评级", dataIndex: "rating", key: "rating" },
  { title: "资产类别", dataIndex: "asset_class", key: "asset_class" },
  { title: "市值", dataIndex: "market_value", key: "market_value", render: formatWan },
  { title: "面值", dataIndex: "face_value", key: "face_value", render: formatWan },
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

  const topWeightSum = useMemo(() => {
    if (!data?.items.length) return 0;
    return data.items.reduce((acc, row) => acc + bondNumericRaw(row.weight), 0);
  }, [data]);

  if (loading && !data) {
    return (
      <div data-testid="top-holdings-loading" style={{ padding: 24 }}>
        <Spin />
      </div>
    );
  }

  if (error) {
    return <Alert type="error" message={error} showIcon />;
  }

  if (!data) {
    return null;
  }

  return (
    <div data-testid="top-holdings-view" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <Space align="center" wrap data-testid="bond-analytics-top-holdings-toolbar">
        <span style={{ color: "rgba(0,0,0,0.55)" }}>展示条数</span>
        <Select
          aria-label="bond-analytics-top-holdings-topn"
          data-testid="bond-analytics-top-holdings-topn"
          value={topN}
          options={TOP_N_OPTIONS.map((n) => ({ value: n, label: String(n) }))}
          onChange={(v) => setTopN(v)}
          style={{ minWidth: 88 }}
        />
      </Space>
      {data.warnings.length > 0 ? (
        <Alert type="warning" showIcon message={data.warnings.join(" ")} />
      ) : null}
      <Card size="small">
        <Statistic
          title={`Top ${data.top_n} 合计市值占比（相对组合总市值）`}
          value={formatPct({
            raw: topWeightSum,
            unit: "ratio",
            display: "",
            precision: 4,
            sign_aware: false,
          })}
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
    </div>
  );
}

export default TopHoldingsView;
