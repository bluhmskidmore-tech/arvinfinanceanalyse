import { useEffect, useState } from "react";
import { Alert, Card, Col, Row, Spin, Statistic, Table } from "antd";
import type { BondPortfolioHeadlinesPayload } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import { formatPct, formatWan } from "../utils/formatters";

interface Props {
  reportDate: string;
}

const assetClassColumns = [
  { title: "资产类别", dataIndex: "asset_class", key: "asset_class" },
  { title: "市值", dataIndex: "market_value", key: "market_value", render: formatWan },
  { title: "久期", dataIndex: "duration", key: "duration" },
  { title: "DV01", dataIndex: "dv01", key: "dv01", render: formatWan },
  { title: "权重", dataIndex: "weight", key: "weight" },
];

function formatHhi(value: string): string {
  const n = parseFloat(value);
  if (Number.isNaN(n)) return "-";
  return n.toFixed(4);
}

export function PortfolioHeadlinesView({ reportDate }: Props) {
  const client = useApiClient();
  const [data, setData] = useState<BondPortfolioHeadlinesPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const envelope = await client.getBondAnalyticsPortfolioHeadlines(reportDate);
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
  }, [client, reportDate]);

  if (loading && !data) {
    return (
      <div data-testid="portfolio-headlines-loading" style={{ padding: 24 }}>
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
    <div data-testid="portfolio-headlines-view" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {data.warnings.length > 0 ? (
        <Alert type="warning" showIcon message={data.warnings.join(" ")} />
      ) : null}
      <Row gutter={[12, 12]}>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="总市值（元）" value={formatWan(data.total_market_value)} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="加权收益率（%）" value={data.weighted_ytm} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="加权修正久期（年）" value={data.weighted_duration} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="组合 DV01" value={formatWan(data.total_dv01)} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="加权票息（%）" value={data.weighted_coupon} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="信用市值占比" value={formatPct(data.credit_weight)} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="发行人 HHI" value={formatHhi(data.issuer_hhi)} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="发行人 Top5 权重" value={formatPct(data.issuer_top5_weight)} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="债券只数" value={data.bond_count} />
          </Card>
        </Col>
      </Row>
      <Card size="small" title="资产类别分布">
        <Table
          size="small"
          rowKey={(row) => row.asset_class}
          columns={assetClassColumns}
          dataSource={data.by_asset_class}
          pagination={false}
        />
      </Card>
    </div>
  );
}

export default PortfolioHeadlinesView;
