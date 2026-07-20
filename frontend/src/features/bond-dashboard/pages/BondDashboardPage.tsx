import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { InfoCircleOutlined } from "@ant-design/icons";
import { Alert, Card, Col, Row, Select, Space, Tooltip, Typography, Table } from "antd";
import type { TableColumnsType } from "antd";

import { useApiClient } from "../../../api/client";
import type {
  BondBusinessTypeMetricItem,
  BondDashboardHeadlinePayload,
  Numeric,
  ResultMeta,
  RiskIndicatorsPayload,
} from "../../../api/contracts";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import {
  BOND_DASHBOARD_PAGE_BUNDLE_SECTIONS,
  bondDashboardAssetSectionForGroup,
  selectBondDashboardBundleSection,
} from "../bondDashboardBundleModel";
import { AssetStructurePie, type AssetGroupBy } from "../components/AssetStructurePie";
import { CreditRatingBlocks } from "../components/CreditRatingBlocks";
import { HeadlineKpis } from "../components/HeadlineKpis";
import { IndustryTable } from "../components/IndustryTable";
import { MaturityStructureChart } from "../components/MaturityStructureChart";
import { PortfolioTable } from "../components/PortfolioTable";
import { RiskIndicatorsPanel } from "../components/RiskIndicatorsPanel";
import { SpreadTable } from "../components/SpreadTable";
import { YieldDistributionBar } from "../components/YieldDistributionBar";
import { useBondDashboardBundleQuery } from "../hooks/useBondDashboardBundleQuery";
import { formatRatePercent, formatYi, formatYears } from "../utils/format";
import "./BondDashboardPage.css";

type BusinessTypeMetricRow = BondBusinessTypeMetricItem & { key: string };

const BUSINESS_TYPE_METRIC_COLUMNS: TableColumnsType<BusinessTypeMetricRow> = [
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
    render: (v: string) => `${formatRatePercent(Number(v) / 100)}%`,
  },
  {
    title: "加权久期",
    dataIndex: "weighted_avg_duration",
    align: "right",
    render: (v: string) => formatYears(Number(v)),
  },
];

function numericRawOrNull(value: Numeric | null | undefined): number | null {
  return value?.raw === null || value?.raw === undefined || !Number.isFinite(value.raw)
    ? null
    : value.raw;
}

function formatYiOrNoData(value: Numeric | null | undefined): string {
  return numericRawOrNull(value) === null ? "—" : formatYi(value);
}

function formatYearsOrNoData(value: Numeric | null | undefined): string {
  return numericRawOrNull(value) === null ? "—" : formatYears(value);
}

function formatCreditRatioDetail(value: Numeric | null | undefined): string {
  return numericRawOrNull(value) === null
    ? "当前信用占比 —"
    : `当前信用占比 ${formatRatePercent(value, 1)}%`;
}

/**
 * 首屏 stale/fallback 警示：quality_flag 非 ok、fallback_date 非空、
 * 或 resolved_report_date 与请求日不一致时，返回该信封的降级说明；否则返回 null。
 */
function describeFirstScreenMetaFallback(
  label: string,
  meta: ResultMeta | undefined,
  pageRequestedReportDate: string | null,
): string | null {
  if (!meta) return null;
  const requestedDate = meta.requested_report_date?.trim() || pageRequestedReportDate?.trim() || "";
  const resolvedDate = meta.resolved_report_date?.trim() ?? "";
  const fallbackDate = meta.fallback_date?.trim() ?? "";
  const qualityDegraded = meta.quality_flag !== "ok";
  const dateFallback = Boolean(requestedDate && resolvedDate && resolvedDate !== requestedDate);
  if (!qualityDegraded && !fallbackDate && !dateFallback) return null;

  const parts: string[] = [];
  if (qualityDegraded) parts.push(`供数质量 ${meta.quality_flag}`);
  if (dateFallback) parts.push(`请求日 ${requestedDate} 回退至 ${resolvedDate}`);
  if (fallbackDate) parts.push(`回退日期 ${fallbackDate}`);
  const actualDate = resolvedDate || meta.as_of_date?.trim() || "";
  if (actualDate && !dateFallback) parts.push(`实际数据日期 ${actualDate}`);
  return `${label}：${parts.join("；")}`;
}

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

  const totalMarketValue = numericRawOrNull(headline.kpis.total_market_value);
  const creditRatio = numericRawOrNull(risk.credit_ratio);
  const creditTone =
    creditRatio === null
      ? "信用仓位 —"
      : creditRatio >= 0.5
        ? "信用仓位偏高"
        : creditRatio >= 0.3
          ? "信用仓位适中"
          : "利率债占比更高";
  const investmentState =
    totalMarketValue === null
      ? "不形成投放状态结论"
      : totalMarketValue > 0
        ? "处于已投放状态"
        : "尚未形成有效持仓";

  return {
    title: "当前结论",
    body: `组合规模约 ${formatYiOrNoData(headline.kpis.total_market_value)}，久期约 ${formatYearsOrNoData(headline.kpis.weighted_duration)}，${creditTone}。`,
    detail: `${formatCreditRatioDetail(risk.credit_ratio)}，总市值${investmentState}。`,
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

  const bundleQuery = useBondDashboardBundleQuery(client, rd || null, BOND_DASHBOARD_PAGE_BUNDLE_SECTIONS, {
    enabled: Boolean(rd),
    industryTopN: 10,
  });
  const bundleLoading = bundleQuery.isLoading;
  const bundleError = bundleQuery.isError;
  const headlineQuery = {
    data: selectBondDashboardBundleSection(bundleQuery.data, "headline-kpis"),
    isLoading: bundleLoading,
  };
  const riskQuery = {
    data: selectBondDashboardBundleSection(bundleQuery.data, "risk-indicators"),
    isLoading: bundleLoading,
  };
  const assetQuery = {
    data: selectBondDashboardBundleSection(
      bundleQuery.data,
      bondDashboardAssetSectionForGroup(assetGroupBy),
    ),
    isLoading: bundleLoading,
  };
  const ratingQuery = {
    data: selectBondDashboardBundleSection(bundleQuery.data, "asset-structure-rating"),
    isLoading: bundleLoading,
  };
  const tenorBarQuery = {
    data: selectBondDashboardBundleSection(bundleQuery.data, "asset-structure-tenor-bucket"),
    isLoading: bundleLoading,
  };
  const yieldQuery = {
    data: selectBondDashboardBundleSection(bundleQuery.data, "yield-distribution"),
    isLoading: bundleLoading,
  };
  const portfolioQuery = {
    data: selectBondDashboardBundleSection(bundleQuery.data, "portfolio-comparison"),
    isLoading: bundleLoading,
  };
  const spreadQuery = {
    data: selectBondDashboardBundleSection(bundleQuery.data, "spread-analysis"),
    isLoading: bundleLoading,
  };
  const maturityQuery = {
    data: selectBondDashboardBundleSection(bundleQuery.data, "maturity-structure"),
    isLoading: bundleLoading,
  };
  const industryQuery = {
    data: selectBondDashboardBundleSection(bundleQuery.data, "industry-distribution"),
    isLoading: bundleLoading,
  };
  const businessTypeMetricsQuery = {
    data: selectBondDashboardBundleSection(bundleQuery.data, "business-type-metrics"),
    isLoading: bundleLoading,
    isError: bundleError,
  };

  const businessTypeMetricItems = businessTypeMetricsQuery.data?.result.items;
  const businessTypeMetricRows = useMemo<BusinessTypeMetricRow[]>(
    () =>
      (businessTypeMetricItems ?? []).map((row) => ({
        key: row.name,
        ...row,
      })),
    [businessTypeMetricItems],
  );

  const dateOptions = datesQuery.data?.result.report_dates ?? [];
  const hasFirstScreenMeta = Boolean(headlineQuery.data?.result_meta || riskQuery.data?.result_meta);
  const firstScreenFallbackNotices = [
    describeFirstScreenMetaFallback("首屏指标", headlineQuery.data?.result_meta, rd || null),
    describeFirstScreenMetaFallback("风险指标", riskQuery.data?.result_meta, rd || null),
  ].filter((notice): notice is string => notice !== null);
  const conclusion =
    headlineQuery.data?.result && riskQuery.data?.result
      ? buildDashboardConclusion(headlineQuery.data.result, riskQuery.data.result)
      : null;
  const datesEmpty = !datesQuery.isLoading && !datesQuery.isError && dateOptions.length === 0;

  return (
    <div data-testid="bond-dashboard-page" className="bond-dashboard-page">
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <div className="bond-dashboard-page__toolbar">
          <div className="bond-dashboard-page__title-row">
            <Typography.Title level={3} style={{ margin: 0 }}>
              债券总览
            </Typography.Title>
            {datesQuery.data?.data_source === "bond_analytics_facts" ? (
              <Tooltip title="数据来源：债券分析事实表（与余额分析页可能存在口径差异）">
                <InfoCircleOutlined
                  aria-label="债券驾驶舱数据来源说明"
                  className="bond-dashboard-page__title-icon"
                />
              </Tooltip>
            ) : null}
          </div>
          <Space>
            <span className="bond-dashboard-page__report-label">报告日</span>
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

        {bundleError ? (
          <Alert
            data-testid="bond-dashboard-bundle-state"
            type="error"
            showIcon
            message="债券总览数据加载失败"
            description="当前无法获取债券总览聚合数据，请稍后重试。"
          />
        ) : null}

        {firstScreenFallbackNotices.length > 0 ? (
          <Alert
            data-testid="bond-dashboard-stale-banner"
            role="status"
            type="warning"
            showIcon
            message="首屏数据为回退/降级口径"
            description={`${firstScreenFallbackNotices.join("。")}。下方 KPI 与结论基于上述回退数据，请以实际数据日期为准。`}
          />
        ) : null}

        {!datesEmpty && conclusion ? (
          <Card data-testid="bond-dashboard-conclusion" className="bond-dashboard-page__conclusion">
            <Space direction="vertical" size={6} style={{ width: "100%" }}>
              <span className="bond-dashboard-page__conclusion-kicker">{conclusion.title}</span>
              <div className="bond-dashboard-page__conclusion-body">{conclusion.body}</div>
              <div className="bond-dashboard-page__conclusion-detail">{conclusion.detail}</div>
            </Space>
          </Card>
        ) : null}

        <HeadlineKpis data={headlineQuery.data?.result} loading={headlineQuery.isLoading} />

        {hasFirstScreenMeta ? (
          <FormalResultMetaPanel
            testId="bond-dashboard-first-screen-result-meta"
            title="债券首页首屏证据"
            sections={[
              {
                key: "headline",
                title: "首屏指标",
                meta: headlineQuery.data?.result_meta,
              },
              {
                key: "risk",
                title: "风险指标",
                meta: riskQuery.data?.result_meta,
              },
            ]}
          />
        ) : null}

        {!datesEmpty ? (
          <details className="bond-dashboard-page__governance-notes">
            <summary>口径与指标边界（证据层）</summary>
            <p data-testid="bond-dashboard-headline-candidate-boundary">
              MTR-BOND-001~004 仍为 candidate，pending_confirmation=true；GS-BOND-HEADLINE-A 是页面样本，非字典级批准。
            </p>
            <p data-testid="bond-dashboard-risk-source-boundary">
              GAP-BOND-DASH-RISK 尚未冻结 MTR-RSK-* 同源关系；风险指标面板不自动继承 GS-RISK-A。
            </p>
          </details>
        ) : null}

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
              dataSource={businessTypeMetricRows}
              columns={BUSINESS_TYPE_METRIC_COLUMNS}
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
