import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Col, Row, Select, Space, Typography } from "antd";

import { useApiClient } from "../../../api/client";
import { AssetStructurePie, type AssetGroupBy } from "../components/AssetStructurePie";
import { CreditRatingBlocks } from "../components/CreditRatingBlocks";
import { HeadlineKpis } from "../components/HeadlineKpis";
import { IndustryTable } from "../components/IndustryTable";
import { MaturityStructureChart } from "../components/MaturityStructureChart";
import { PortfolioTable } from "../components/PortfolioTable";
import { RiskIndicatorsPanel } from "../components/RiskIndicatorsPanel";
import { SpreadTable } from "../components/SpreadTable";
import { YieldDistributionBar } from "../components/YieldDistributionBar";

export default function BondDashboardPage() {
  const client = useApiClient();
  const [reportDate, setReportDate] = useState<string | null>(null);
  const [assetGroupBy, setAssetGroupBy] = useState<AssetGroupBy>("bond_type");

  const datesQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "dates"],
    queryFn: () => client.getBondDashboardDates(),
  });

  useEffect(() => {
    const dates = datesQuery.data?.result.report_dates;
    if (reportDate === null && dates && dates.length > 0) {
      setReportDate(dates[0]);
    }
  }, [datesQuery.data, reportDate]);

  const rd = reportDate ?? "";

  const headlineQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "headline", rd],
    queryFn: () => client.getBondDashboardHeadlineKpis(rd),
    enabled: Boolean(rd),
  });

  const assetQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "asset", rd, assetGroupBy],
    queryFn: () => client.getBondDashboardAssetStructure(rd, assetGroupBy),
    enabled: Boolean(rd),
  });

  const ratingQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "asset-rating", rd],
    queryFn: () => client.getBondDashboardAssetStructure(rd, "rating"),
    enabled: Boolean(rd),
  });

  const tenorBarQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "tenor-bars", rd],
    queryFn: () => client.getBondDashboardAssetStructure(rd, "tenor_bucket"),
    enabled: Boolean(rd),
  });

  const yieldQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "yield-dist", rd],
    queryFn: () => client.getBondDashboardYieldDistribution(rd),
    enabled: Boolean(rd),
  });

  const portfolioQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "portfolio", rd],
    queryFn: () => client.getBondDashboardPortfolioComparison(rd),
    enabled: Boolean(rd),
  });

  const spreadQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "spread", rd],
    queryFn: () => client.getBondDashboardSpreadAnalysis(rd),
    enabled: Boolean(rd),
  });

  const maturityQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "maturity", rd],
    queryFn: () => client.getBondDashboardMaturityStructure(rd),
    enabled: Boolean(rd),
  });

  const industryQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "industry", rd],
    queryFn: () => client.getBondDashboardIndustryDistribution(rd),
    enabled: Boolean(rd),
  });

  const riskQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "risk", rd],
    queryFn: () => client.getBondDashboardRiskIndicators(rd),
    enabled: Boolean(rd),
  });

  const dateOptions = datesQuery.data?.result.report_dates ?? [];

  return (
    <div
      data-testid="bond-dashboard-page"
      style={{ background: "#f5f7fa", minHeight: "100%", padding: 16 }}
    >
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
          <Typography.Title level={3} style={{ margin: 0 }}>
            债券总览
          </Typography.Title>
          <Space>
            <span style={{ color: "rgba(0,0,0,0.55)" }}>报告日</span>
            <Select
              aria-label="bond-dashboard-report-date"
              style={{ minWidth: 160 }}
              value={reportDate ?? undefined}
              loading={datesQuery.isLoading}
              options={dateOptions.map((d) => ({ label: d, value: d }))}
              onChange={(v) => setReportDate(v)}
              placeholder="选择日期"
            />
          </Space>
        </div>

        <HeadlineKpis data={headlineQuery.data?.result} loading={headlineQuery.isLoading} />

        <Row gutter={[16, 16]}>
          <Col xs={24} lg={8}>
            <AssetStructurePie
              data={assetQuery.data?.result}
              loading={assetQuery.isLoading}
              groupBy={assetGroupBy}
              onGroupByChange={setAssetGroupBy}
            />
          </Col>
          <Col xs={24} lg={8}>
            <YieldDistributionBar
              yieldData={yieldQuery.data?.result}
              tenorData={tenorBarQuery.data?.result}
              loadingYield={yieldQuery.isLoading}
              loadingTenor={tenorBarQuery.isLoading}
            />
          </Col>
          <Col xs={24} lg={8}>
            <CreditRatingBlocks data={ratingQuery.data?.result} loading={ratingQuery.isLoading} />
          </Col>
        </Row>

        <Row gutter={[16, 16]}>
          <Col xs={24} lg={8}>
            <PortfolioTable data={portfolioQuery.data?.result} loading={portfolioQuery.isLoading} />
          </Col>
          <Col xs={24} lg={8}>
            <SpreadTable data={spreadQuery.data?.result} loading={spreadQuery.isLoading} />
          </Col>
          <Col xs={24} lg={8}>
            <RiskIndicatorsPanel data={riskQuery.data?.result} loading={riskQuery.isLoading} />
          </Col>
        </Row>

        <Row gutter={[16, 16]}>
          <Col xs={24} lg={12}>
            <MaturityStructureChart data={maturityQuery.data?.result} loading={maturityQuery.isLoading} />
          </Col>
          <Col xs={24} lg={12}>
            <IndustryTable data={industryQuery.data?.result} loading={industryQuery.isLoading} />
          </Col>
        </Row>
      </Space>
    </div>
  );
}
