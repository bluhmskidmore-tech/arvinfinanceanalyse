import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Col, Row, Statistic, Table } from "antd";
import type { BondPortfolioHeadlinesPayload, Numeric } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import { apiQueryKeys } from "../../../api/queryKeys";
import { EM_DASH } from "../../../utils/format";
import { formatDv01Wan, formatPct, formatYi } from "../utils/formatters";
import {
  DetailEmptyNote,
  DetailPanelSkeleton,
  withNumericColumns,
} from "./BondAnalyticsDetailPrimitives";
import detailStyles from "./BondAnalyticsDetailPrimitives.module.css";

interface Props {
  reportDate: string;
}

const assetClassColumns = withNumericColumns(
  [
    { title: "资产类别", dataIndex: "asset_class", key: "asset_class" },
    { title: "市值", dataIndex: "market_value", key: "market_value", render: formatYi },
    {
      title: "久期",
      dataIndex: "duration",
      key: "duration",
      render: (v: Numeric) => v.display,
    },
    {
      title: "DV01（万元/bp）",
      dataIndex: "dv01",
      key: "dv01",
      render: (v: Numeric) => formatDv01Wan(v),
    },
    {
      title: "权重",
      dataIndex: "weight",
      key: "weight",
      render: (v: Numeric) => v.display,
    },
  ],
  ["market_value", "duration", "dv01", "weight"],
);

function formatHhi(value: import("../../../api/contracts").Numeric | string): string {
  const n = typeof value === "string" ? Number.parseFloat(value) : (value.raw ?? Number.NaN);
  if (Number.isNaN(n)) return EM_DASH;
  return n.toFixed(4);
}

export function PortfolioHeadlinesView({ reportDate }: Props) {
  const client = useApiClient();
  const query = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsPortfolioHeadlines(client.mode, reportDate),
    queryFn: () => client.getBondAnalyticsPortfolioHeadlines(reportDate),
    enabled: Boolean(reportDate),
    retry: false,
  });
  const data: BondPortfolioHeadlinesPayload | null = query.data?.result ?? null;

  if (query.isLoading && !data) {
    return <DetailPanelSkeleton testId="portfolio-headlines-loading" />;
  }

  if (query.isError) {
    return <Alert type="error" message={(query.error as Error).message} showIcon />;
  }

  if (!data) {
    return null;
  }

  return (
    <div data-testid="portfolio-headlines-view" className={detailStyles.view}>
      {data.warnings.length > 0 ? (
        <Alert type="warning" showIcon message={data.warnings.join(" ")} />
      ) : null}
      <Row gutter={[12, 12]} className={detailStyles.kpiGrid}>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="总市值（亿元）" value={formatYi(data.total_market_value)} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="加权收益率（%）" value={data.weighted_ytm.display} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="加权修正久期（年）" value={data.weighted_duration.display} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="组合 DV01（万元/bp）" value={formatDv01Wan(data.total_dv01)} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="加权票息（%）" value={data.weighted_coupon.display} />
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
            <Statistic title="发行人前五权重" value={formatPct(data.issuer_top5_weight)} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="债券只数" value={data.bond_count} />
          </Card>
        </Col>
      </Row>
      <Card size="small" title="资产类别分布">
        {data.by_asset_class.length > 0 ? (
          <Table
            size="small"
            rowKey={(row) => row.asset_class}
            columns={assetClassColumns}
            dataSource={data.by_asset_class}
            pagination={false}
          />
        ) : (
          <DetailEmptyNote testId="portfolio-headlines-asset-class-empty">
            暂无资产类别分布
          </DetailEmptyNote>
        )}
      </Card>
    </div>
  );
}

export default PortfolioHeadlinesView;
