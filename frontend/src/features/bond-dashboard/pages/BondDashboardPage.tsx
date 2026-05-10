import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { InfoCircleOutlined } from "@ant-design/icons";
import { Alert, Card, Col, Row, Select, Space, Tooltip, Typography, Table } from "antd";

import { useApiClient } from "../../../api/client";
import type { BondDashboardHeadlinePayload, RiskIndicatorsPayload } from "../../../api/contracts";
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

function buildDashboardConclusion(
  headline: BondDashboardHeadlinePayload | undefined,
  risk: RiskIndicatorsPayload | undefined,
) {
  if (!headline || !risk) {
    return {
      title: "当前结论",
      body: "债券驾驶舱结论待载入，先确认报告日与正式读链路状态。",
      detail: "首屏结论会基于持仓规模、久期和信用占比同步更新。",
    };
  }

  const totalMarketValue = nativeToNumber(headline.kpis.total_market_value);
  const creditRatio = nativeToNumber(risk.credit_ratio);
  const creditTone =
    creditRatio >= 0.5 ? "信用仓位偏高" : creditRatio >= 0.3 ? "信用仓位适中" : "利率债占比更高";

  return {
    title: "当前结论",
    body: `组合规模约 ${formatYi(headline.kpis.total_market_value)}，久期约 ${formatYears(headline.kpis.weighted_duration)}，${creditTone}。`,
    detail: `当前信用占比 ${formatRatePercent(risk.credit_ratio, 1)}，总市值${totalMarketValue > 0 ? "处于已投放状态" : "尚未形成有效持仓"}。`,
  };
}

export default function BondDashboardPage() {
  const client = useApiClient();
  const [reportDate, setReportDate] = useState<string | null>(null);
  const [assetGroupBy, setAssetGroupBy] = useState<AssetGroupBy>("bond_type");
  const [lowerPanelReadyDate, setLowerPanelReadyDate] = useState<string | null>(null);

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

  const riskQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "risk", rd],
    queryFn: () => client.getBondDashboardRiskIndicators(rd),
    enabled: Boolean(rd),
  });

  const firstScreenReady = Boolean(headlineQuery.data?.result && riskQuery.data?.result);
  const lowerPanelEnabled = Boolean(rd) && lowerPanelReadyDate === rd;

  useEffect(() => {
    if (!firstScreenReady || !rd) {
      return;
    }

    const idleWindow = window as typeof window & {
      requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
      cancelIdleCallback?: (handle: number) => void;
    };

    if (idleWindow.requestIdleCallback) {
      const idleHandle = idleWindow.requestIdleCallback(
        () => setLowerPanelReadyDate(rd),
        { timeout: 600 },
      );
      return () => idleWindow.cancelIdleCallback?.(idleHandle);
    }

    const timeoutHandle = window.setTimeout(() => setLowerPanelReadyDate(rd), 120);
    return () => window.clearTimeout(timeoutHandle);
  }, [firstScreenReady, rd]);

  const assetQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "asset", rd, assetGroupBy],
    queryFn: () => client.getBondDashboardAssetStructure(rd, assetGroupBy),
    enabled: lowerPanelEnabled,
  });

  const ratingQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "asset-rating", rd],
    queryFn: () => client.getBondDashboardAssetStructure(rd, "rating"),
    enabled: lowerPanelEnabled,
  });

  const tenorBarQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "tenor-bars", rd],
    queryFn: () => client.getBondDashboardAssetStructure(rd, "tenor_bucket"),
    enabled: lowerPanelEnabled,
  });

  const yieldQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "yield-dist", rd],
    queryFn: () => client.getBondDashboardYieldDistribution(rd),
    enabled: lowerPanelEnabled,
  });

  const portfolioQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "portfolio", rd],
    queryFn: () => client.getBondDashboardPortfolioComparison(rd),
    enabled: lowerPanelEnabled,
  });

  const spreadQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "spread", rd],
    queryFn: () => client.getBondDashboardSpreadAnalysis(rd),
    enabled: lowerPanelEnabled,
  });

  const maturityQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "maturity", rd],
    queryFn: () => client.getBondDashboardMaturityStructure(rd),
    enabled: lowerPanelEnabled,
  });

  const industryQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "industry", rd],
    queryFn: () => client.getBondDashboardIndustryDistribution(rd),
    enabled: lowerPanelEnabled,
  });

  const businessTypeMetricsQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "business-type-metrics", rd],
    queryFn: () => client.getBondBusinessTypeMetrics({ reportDate: rd }),
    enabled: lowerPanelEnabled,
    retry: false,
    staleTime: 60_000,
  });

  const dateOptions = datesQuery.data?.result.report_dates ?? [];
  const conclusion =
    headlineQuery.data?.result && riskQuery.data?.result
      ? buildDashboardConclusion(headlineQuery.data.result, riskQuery.data.result)
      : null;
  const datesEmpty = !datesQuery.isLoading && !datesQuery.isError && dateOptions.length === 0;

  return (
    <div data-testid="bond-dashboard-page" style={{ background: "#f5f7fa", minHeight: "100%", padding: 16 }}>
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
          <Space align="center" size={8}>
            <Typography.Title level={3} style={{ margin: 0 }}>
              债券总览
            </Typography.Title>
            {datesQuery.data?.data_source === "bond_analytics_facts" ? (
              <Tooltip title="数据来源：债券分析事实表（与余额分析页可能存在口径差异）">
                <InfoCircleOutlined
                  aria-label="债券驾驶舱数据来源说明"
                  style={{ color: "rgba(0,0,0,0.45)", fontSize: 16, cursor: "help" }}
                />
              </Tooltip>
            ) : null}
          </Space>
          <Space>
            <span style={{ color: "rgba(0,0,0,0.55)" }}>报告日</span>
            <Select
              aria-label="bond-dashboard-report-date"
              style={{ minWidth: 160 }}
              value={reportDate ?? undefined}
              loading={datesQuery.isLoading}
              disabled={datesQuery.isLoading || datesQuery.isError || dateOptions.length === 0}
              options={dateOptions.map((date) => ({ label: date, value: date }))}
              onChange={(value) => setReportDate(value)}
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
              <div style={{ fontSize: 20, fontWeight: 600, color: "#162033", lineHeight: 1.4 }}>{conclusion.body}</div>
              <div style={{ color: "#5c6b82", fontSize: 13, lineHeight: 1.7 }}>{conclusion.detail}</div>
            </Space>
          </Card>
        ) : null}

        <HeadlineKpis data={headlineQuery.data?.result} loading={headlineQuery.isLoading} />

        <Card
          data-testid="bond-dashboard-business-type-metrics"
          size="small"
          title="业务类型加权指标"
        >
          {businessTypeMetricsQuery.isLoading ? (
            <Typography.Text type="secondary">载入中…</Typography.Text>
          ) : businessTypeMetricsQuery.isError ? (
            <Typography.Text type="danger">指标暂不可用</Typography.Text>
          ) : !(businessTypeMetricsQuery.data?.result.items.length ?? 0) ? (
            <Typography.Text type="secondary">暂无数据</Typography.Text>
          ) : (
            <Table
              size="small"
              pagination={false}
              scroll={{ x: "max-content" }}
              dataSource={businessTypeMetricsQuery.data!.result.items.map((row) => ({
                key: row.name,
                ...row,
              }))}
              columns={[
                { title: "业务类型", dataIndex: "name", ellipsis: true },
                {
                  title: "市值（亿）",
                  dataIndex: "market_value",
                  align: "right",
                  render: (v: string) => formatYi(Number(v)),
                },
                {
                  title: "加权 YTM",
                  dataIndex: "weighted_avg_ytm_pct",
                  align: "right",
                  render: (v: string) => formatRatePercent(Number(v) / 100),
                },
                {
                  title: "加权久期",
                  dataIndex: "weighted_avg_duration",
                  align: "right",
                  render: (v: string) => formatYears(Number(v)),
                },
              ]}
            />
          )}
        </Card>

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
            <PortfolioTable
              data={portfolioQuery.data?.result}
              headline={headlineQuery.data?.result}
              loading={portfolioQuery.isLoading}
            />
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
