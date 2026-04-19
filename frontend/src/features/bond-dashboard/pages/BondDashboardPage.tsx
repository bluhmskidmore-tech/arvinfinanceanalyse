import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Col, Row, Select, Space, Typography } from "antd";

import { useApiClient } from "../../../api/client";
import type { Numeric } from "../../../api/contracts";
import { AssetStructurePie, type AssetGroupBy } from "../components/AssetStructurePie";
import { CreditRatingBlocks } from "../components/CreditRatingBlocks";
import { HeadlineKpis } from "../components/HeadlineKpis";
import { IndustryTable } from "../components/IndustryTable";
import { MaturityStructureChart } from "../components/MaturityStructureChart";
import { PortfolioTable } from "../components/PortfolioTable";
import { RiskIndicatorsPanel } from "../components/RiskIndicatorsPanel";
import { SpreadTable } from "../components/SpreadTable";
import { YieldDistributionBar } from "../components/YieldDistributionBar";
import { formatRatePercent, formatYi, formatYears, nativeToNumber } from "../utils/format";

function readNumericLike(value: string | number | Numeric | undefined | null): number {
  if (value && typeof value === "object" && "raw" in value) {
    return typeof value.raw === "number" ? value.raw : 0;
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : 0;
  }
  if (typeof value === "string") {
    return nativeToNumber(value);
  }
  return 0;
}

function formatYiLike(value: string | number | Numeric | undefined | null) {
  if (value && typeof value === "object" && "display" in value) {
    return value.display;
  }
  if (typeof value === "number") {
    return formatYi(String(value));
  }
  return formatYi(typeof value === "string" ? value : "0");
}

function formatYearsLike(value: string | number | Numeric | undefined | null) {
  if (value && typeof value === "object" && "display" in value) {
    return value.display;
  }
  if (typeof value === "number") {
    return formatYears(String(value));
  }
  return formatYears(typeof value === "string" ? value : "0");
}

function formatPercentLike(value: string | number | Numeric | undefined | null, digits = 1) {
  if (value && typeof value === "object" && "display" in value) {
    return value.display;
  }
  if (typeof value === "number") {
    return formatRatePercent(String(value), digits);
  }
  return formatRatePercent(typeof value === "string" ? value : "0", digits);
}

function buildDashboardConclusion(
  headline: {
    kpis: {
      total_market_value: string | Numeric;
      weighted_duration: string | Numeric;
    };
  } | undefined,
  risk: {
    credit_ratio: string | Numeric;
  } | undefined,
) {
  if (!headline || !risk) {
    return {
      title: "当前结论",
      body: "债券驾驶舱结论待载入，先确认报告日与正式读链路状态。",
      detail: "首屏结论会基于持仓规模、久期和信用占比同步更新。",
    };
  }

  const totalMarketValue = readNumericLike(headline.kpis.total_market_value);
  const creditRatio = readNumericLike(risk.credit_ratio);

  const creditTone =
    creditRatio >= 0.5 ? "信用仓位偏高" : creditRatio >= 0.3 ? "信用仓位适中" : "利率债占比更高";

    return {
      title: "当前结论",
      body: `组合规模约 ${formatYiLike(headline.kpis.total_market_value)}，久期约 ${formatYearsLike(headline.kpis.weighted_duration)}，${creditTone}。`,
      detail: `当前信用占比 ${formatPercentLike(risk.credit_ratio, 1)}，总市值 ${totalMarketValue > 0 ? "处于已投放状态" : "尚未形成有效持仓"}。`,
    };
}

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
  const conclusion =
    headlineQuery.data?.result && riskQuery.data?.result
      ? buildDashboardConclusion(headlineQuery.data.result, riskQuery.data.result)
      : null;
  const datesEmpty = !datesQuery.isLoading && !datesQuery.isError && dateOptions.length === 0;

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
              disabled={datesQuery.isLoading || datesQuery.isError || dateOptions.length === 0}
              options={dateOptions.map((d) => ({ label: d, value: d }))}
              onChange={(v) => setReportDate(v)}
              placeholder="选择日期"
            />
          </Space>
        </div>

        {datesQuery.isError ? (
          <Alert
            data-testid="bond-dashboard-page-state"
            type="error"
            showIcon
            message="报告日加载失败"
            description="当前无法获取债券驾驶舱可用报告日，请稍后重试。"
          />
        ) : null}

        {datesEmpty ? (
          <Alert
            data-testid="bond-dashboard-page-state"
            type="info"
            showIcon
            message="暂无可用报告日"
            description="债券驾驶舱当前没有可读的正式报告日，因此首屏模块不展示业务结论。"
          />
        ) : null}

        {!datesEmpty && conclusion ? (
          <Card
            data-testid="bond-dashboard-conclusion"
            style={{
              borderRadius: 16,
              border: "1px solid #dbe7f5",
              background: "#f7fbff",
              boxShadow: "0 10px 24px rgba(31, 94, 255, 0.06)",
            }}
          >
            <Space direction="vertical" size={6} style={{ width: "100%" }}>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  color: "#6b7f99",
                }}
              >
                {conclusion.title}
              </span>
              <div style={{ fontSize: 20, fontWeight: 600, color: "#162033", lineHeight: 1.4 }}>
                {conclusion.body}
              </div>
              <div style={{ color: "#5c6b82", fontSize: 13, lineHeight: 1.7 }}>{conclusion.detail}</div>
            </Space>
          </Card>
        ) : null}

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
