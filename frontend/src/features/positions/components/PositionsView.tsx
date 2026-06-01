import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  Col,
  Input,
  Modal,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Typography,
} from "antd";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { designTokens } from "../../../theme/designSystem";
import { displayTokens } from "../../../theme/displayTokens";
import { FilterBar } from "../../../components/FilterBar";
import type {
  CounterpartyStatsResponse,
  IndustryStatsResponse,
  PositionDirection,
  RateCoverage,
  RatingStatsResponse,
  ResultMeta,
} from "../../../api/contracts";
import {
  DataStatusStrip,
  KpiBand,
  KpiBandMetric,
  PageDecisionHero,
  PageFilterTray,
} from "../../../components/page/PagePrimitives";
import CustomerDetailModal from "./CustomerDetailModal";
import IndustryDistributionCard from "./IndustryDistributionCard";
import RatingDistributionCard from "./RatingDistributionCard";
import { formatAmountYi, formatRatePercent } from "../utils/format";
import "./PositionsView.css";

const PAGE_SIZE = 20;
const ALL_BOND_SUBTYPE = "__all_bond_subtypes__";
const ALL_INTERBANK_PRODUCT = "__all_interbank_products__";

type TabKey = "bonds" | "interbank";
type InterbankDirectionFilter = PositionDirection | "ALL";

function formatCoverageSummary(coverage: RateCoverage | null | undefined): string {
  if (!coverage) {
    return "—";
  }
  const missing =
    coverage.missing_count > 0
      ? `，缺 ${coverage.missing_count} 笔 / ${formatAmountYi(coverage.missing_amount)}`
      : "";
  return `${coverage.coverage_ratio}%${missing}`;
}

function rateCoveragePolicyLabel(policy: string | null | undefined): string {
  if (policy === "exclude_missing_rate_from_denominator") {
    return "缺失利率剔除分母";
  }
  return policy || "—";
}

function compactVersion(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  return value.length > 18 ? `${value.slice(0, 15)}…` : value;
}

function metaSummary(meta: ResultMeta | null | undefined): string {
  if (!meta) {
    return "—";
  }
  return `${meta.quality_flag} · ${compactVersion(meta.source_version)} · ${compactVersion(meta.rule_version)}`;
}

function topRatingItem(items: RatingStatsResponse["items"] | undefined) {
  if (!items?.length) {
    return null;
  }
  return items.reduce((best, item) =>
    Number(item.percentage) > Number(best.percentage) ? item : best,
  );
}

function SummaryTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "asset" | "liability";
}) {
  return (
    <div className={tone ? `positions-view__summary-tile positions-view__summary-tile--${tone}` : "positions-view__summary-tile"}>
      <span className="positions-view__summary-label">{label}</span>
      <strong className="positions-view__summary-value">{value}</strong>
    </div>
  );
}

function BondsPortfolioSnapshotCard({
  stats,
  loading,
}: {
  stats: CounterpartyStatsResponse | undefined;
  loading: boolean;
}) {
  return (
    <Card
      size="small"
      title="组合读数"
      extra={<Typography.Text type="secondary">{stats?.num_days ?? "—"} 天</Typography.Text>}
    >
      {loading ? (
        <div className="positions-view__loading">
          <Spin />
        </div>
      ) : (
        <div className="positions-view__summary-grid">
          <SummaryTile label="区间累计" value={formatAmountYi(stats?.total_amount)} />
          <SummaryTile label="日均合计" value={formatAmountYi(stats?.total_avg_daily)} />
          <SummaryTile
            label="加权收益率"
            value={stats?.total_weighted_rate ? formatRatePercent(stats.total_weighted_rate) : "—"}
          />
          <SummaryTile
            label="加权付息率"
            value={
              stats?.total_weighted_coupon_rate
                ? formatRatePercent(stats.total_weighted_coupon_rate)
                : "—"
            }
          />
          <SummaryTile label="客户数" value={stats?.total_customers != null ? `${stats.total_customers} 户` : "—"} />
          <SummaryTile label="CR10" value={stats?.cr10_ratio ?? "—"} />
        </div>
      )}
    </Card>
  );
}

function PositionsQualityPanel({
  startDate,
  endDate,
  subType,
  counterpartyStats,
}: {
  startDate: string | null;
  endDate: string | null;
  subType: string | null;
  counterpartyStats: CounterpartyStatsResponse | undefined;
}) {
  const client = useApiClient();
  const ratingEnvelopeQuery = useQuery({
    queryKey: ["positions", "quality-rating", client.mode, startDate, endDate, subType ?? ""],
    queryFn: async () => {
      if (!startDate || !endDate) {
        throw new Error("missing range");
      }
      return client.getPositionsStatsRating({
        startDate,
        endDate,
        subType,
      });
    },
    enabled: Boolean(startDate && endDate),
    retry: false,
  });
  const industryEnvelopeQuery = useQuery({
    queryKey: ["positions", "quality-industry", client.mode, startDate, endDate, subType ?? ""],
    queryFn: async () => {
      if (!startDate || !endDate) {
        throw new Error("missing range");
      }
      return client.getPositionsStatsIndustry({
        startDate,
        endDate,
        subType,
        topN: 10,
      });
    },
    enabled: Boolean(startDate && endDate),
    retry: false,
  });

  const rating: RatingStatsResponse | undefined = ratingEnvelopeQuery.data?.result;
  const industry: IndustryStatsResponse | undefined = industryEnvelopeQuery.data?.result;
  const topRating = topRatingItem(rating?.items);
  const topIndustry = industry?.items?.[0] ?? null;
  const meta = ratingEnvelopeQuery.data?.result_meta ?? industryEnvelopeQuery.data?.result_meta;
  const ytmCoverage = counterpartyStats?.ytm_rate_coverage ?? rating?.ytm_rate_coverage;
  const couponCoverage = counterpartyStats?.coupon_rate_coverage;
  const policy = rateCoveragePolicyLabel(ytmCoverage?.policy ?? couponCoverage?.policy);
  const dateCoverage = counterpartyStats?.num_days ?? rating?.num_days ?? industry?.num_days;

  return (
    <Card size="small" title="质量与集中度">
      <div className="positions-view__quality-grid">
        <div className="positions-view__quality-item">
          <span className="positions-view__quality-label">日期覆盖</span>
          <span className="positions-view__quality-value">
            {dateCoverage != null ? `${dateCoverage} 天` : "—"}
          </span>
        </div>
        <div className="positions-view__quality-item">
          <span className="positions-view__quality-label">CR10</span>
          <span className="positions-view__quality-value">{counterpartyStats?.cr10_ratio ?? "—"}</span>
        </div>
        <div className="positions-view__quality-item">
          <span className="positions-view__quality-label">YTM 覆盖</span>
          <span className="positions-view__quality-value">{formatCoverageSummary(ytmCoverage)}</span>
        </div>
        <div className="positions-view__quality-item">
          <span className="positions-view__quality-label">票息覆盖</span>
          <span className="positions-view__quality-value">{formatCoverageSummary(couponCoverage)}</span>
        </div>
        <div className="positions-view__quality-item">
          <span className="positions-view__quality-label">最高评级集中</span>
          <span className="positions-view__quality-value">
            {topRating ? `${topRating.rating} · ${topRating.percentage}%` : "—"}
          </span>
        </div>
        <div className="positions-view__quality-item">
          <span className="positions-view__quality-label">最高行业集中</span>
          <span className="positions-view__quality-value">
            {topIndustry ? `${topIndustry.industry} · ${topIndustry.percentage}%` : "—"}
          </span>
        </div>
      </div>
      <div className="positions-view__quality-note">
        口径：{policy}；质量/来源/规则：{metaSummary(meta)}
      </div>
    </Card>
  );
}

export default function PositionsView() {
  const client = useApiClient();
  const [searchParams] = useSearchParams();
  const explicitReportDate = searchParams.get("report_date")?.trim() || "";

  const datesQuery = useQuery({
    queryKey: ["positions", "balance-analysis-dates", client.mode],
    queryFn: () => client.getBalanceAnalysisDates(),
    retry: false,
  });

  const dateOptions = useMemo(() => {
    const dates = datesQuery.data?.result.report_dates ?? [];
    if (explicitReportDate && !dates.includes(explicitReportDate)) {
      return [explicitReportDate, ...dates];
    }
    return dates;
  }, [datesQuery.data?.result.report_dates, explicitReportDate]);

  const [selectedReportDate, setSelectedReportDate] = useState("");
  const reportDate = useMemo(() => {
    if (explicitReportDate) {
      return explicitReportDate;
    }
    return selectedReportDate || datesQuery.data?.result.report_dates[0] || "";
  }, [datesQuery.data?.result.report_dates, explicitReportDate, selectedReportDate]);

  const [tab, setTab] = useState<TabKey>("bonds");
  const [rangeTouched, setRangeTouched] = useState(false);
  const [rangeFrom, setRangeFrom] = useState("");
  const [rangeTo, setRangeTo] = useState("");

  useEffect(() => {
    if (rangeTouched) {
      return;
    }
    if (!reportDate) {
      return;
    }
    const y = Number(reportDate.slice(0, 4));
    if (!Number.isFinite(y)) {
      return;
    }
    setRangeFrom(`${y}-01-01`);
    setRangeTo(reportDate);
  }, [rangeTouched, reportDate]);

  const startDate = rangeFrom.trim() || null;
  const endDate = rangeTo.trim() || null;

  const [selectedSubType, setSelectedSubType] = useState("");
  const [selectedProductType, setSelectedProductType] = useState("");
  const [direction, setDirection] = useState<InterbankDirectionFilter>("ALL");
  const [interbankFilterOpen, setInterbankFilterOpen] = useState(false);
  const [searchText, setSearchText] = useState("");
  const [page, setPage] = useState(1);

  const [customerModalOpen, setCustomerModalOpen] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState<string | null>(null);

  useEffect(() => {
    setPage(1);
    setSearchText("");
    if (tab === "bonds") {
      setSelectedProductType("");
      setDirection("ALL");
    } else {
      setSelectedSubType("");
    }
  }, [tab]);

  useEffect(() => {
    setPage(1);
  }, [tab, selectedSubType, selectedProductType, direction, reportDate]);

  const bondSubTypesQuery = useQuery({
    queryKey: ["positions", "bond-subtypes", client.mode, reportDate],
    queryFn: async () => {
      const envelope = await client.getPositionsBondSubTypes(reportDate || null);
      return envelope.result.sub_types;
    },
    enabled: tab === "bonds" && Boolean(reportDate),
    retry: false,
  });

  const interbankProductTypesQuery = useQuery({
    queryKey: ["positions", "interbank-product-types", client.mode, reportDate],
    queryFn: async () => {
      const envelope = await client.getPositionsInterbankProductTypes(reportDate || null);
      return envelope.result.product_types;
    },
    enabled: tab === "interbank" && Boolean(reportDate),
    retry: false,
  });

  useEffect(() => {
    if (tab === "bonds") {
      setSelectedSubType("");
    } else {
      setSelectedProductType("");
      setDirection("ALL");
    }
  }, [reportDate, tab]);

  const bondsListQuery = useQuery({
    queryKey: ["positions", "bonds-list", client.mode, reportDate, selectedSubType, page],
    queryFn: async () => {
      const envelope = await client.getPositionsBondsList({
        reportDate: reportDate || null,
        subType: selectedSubType || null,
        page,
        pageSize: PAGE_SIZE,
        includeIssued: false,
      });
      return envelope.result;
    },
    enabled: tab === "bonds" && Boolean(reportDate),
    retry: false,
  });

  const interbankListQuery = useQuery({
    queryKey: [
      "positions",
      "interbank-list",
      client.mode,
      reportDate,
      selectedProductType,
      direction,
      page,
    ],
    queryFn: async () => {
      const envelope = await client.getPositionsInterbankList({
        reportDate: reportDate || null,
        productType: selectedProductType || null,
        direction,
        page,
        pageSize: PAGE_SIZE,
      });
      return envelope.result;
    },
    enabled: tab === "interbank" && Boolean(reportDate),
    retry: false,
  });

  const bondsCpQuery = useQuery({
    queryKey: ["positions", "cp-bonds", client.mode, startDate, endDate, selectedSubType],
    queryFn: async () => {
      const envelope = await client.getPositionsCounterpartyBonds({
        startDate: startDate!,
        endDate: endDate!,
        subType: selectedSubType || null,
        topN: 50,
        page: 1,
        pageSize: 50,
      });
      return envelope.result;
    },
    enabled: tab === "bonds" && Boolean(startDate && endDate),
    retry: false,
  });

  const interbankSplitQuery = useQuery({
    queryKey: ["positions", "cp-interbank-split", client.mode, startDate, endDate, selectedProductType],
    queryFn: async () => {
      const envelope = await client.getPositionsCounterpartyInterbankSplit({
        startDate: startDate!,
        endDate: endDate!,
        productType: selectedProductType || null,
        topN: 50,
      });
      return envelope.result;
    },
    enabled: tab === "interbank" && Boolean(startDate && endDate),
    retry: false,
  });

  const bondsCp = bondsCpQuery.data;
  const interbankCpSplit = interbankSplitQuery.data;

  const filteredBondsCpItems = useMemo(() => {
    const items = bondsCp?.items ?? [];
    const q = searchText.trim();
    if (!q) {
      return items;
    }
    return items.filter((x) => x.customer_name.includes(q));
  }, [bondsCp?.items, searchText]);

  const filteredAssetItems = useMemo(() => {
    const items = interbankCpSplit?.asset_items ?? [];
    const q = searchText.trim();
    if (!q) {
      return items;
    }
    return items.filter((x) => x.customer_name.includes(q));
  }, [interbankCpSplit?.asset_items, searchText]);

  const filteredLiabilityItems = useMemo(() => {
    const items = interbankCpSplit?.liability_items ?? [];
    const q = searchText.trim();
    if (!q) {
      return items;
    }
    return items.filter((x) => x.customer_name.includes(q));
  }, [interbankCpSplit?.liability_items, searchText]);

  const currentList = tab === "bonds" ? bondsListQuery.data : interbankListQuery.data;
  const listLoading = tab === "bonds" ? bondsListQuery.isLoading : interbankListQuery.isLoading;
  const totalPages = currentList ? Math.ceil(currentList.total / PAGE_SIZE) : 0;
  const canPrev = page > 1;
  const canNext = currentList ? page * PAGE_SIZE < currentList.total : false;

  const datesBlockingError = datesQuery.isError && !reportDate;
  const datesEmpty =
    !explicitReportDate &&
    !datesQuery.isLoading &&
    !datesBlockingError &&
    (datesQuery.data?.result.report_dates.length ?? 0) === 0;
  const activeScopeLabel =
    tab === "bonds"
      ? selectedSubType || "全部业务种类"
      : selectedProductType || "全部产品类型";
  const activePeerFilterLabel =
    tab === "bonds"
      ? searchText || "未输入客户"
      : `${direction === "ALL" ? "全部方向" : direction === "Asset" ? "资产端" : "负债端"} · ${
          searchText || "未输入对手方"
        }`;
  const dataModeLabel = client.mode === "real" ? "真实只读链路" : "本地演示数据";
  const dataModeStyle = {
    display: "inline-flex",
    alignItems: "center",
    padding: "7px 12px",
    borderRadius: 999,
    background: client.mode === "real" ? designTokens.color.success[50] : designTokens.color.primary[50],
    color:
      client.mode === "real"
        ? displayTokens.apiMode.realForeground
        : displayTokens.apiMode.mockForeground,
    fontSize: 12,
    fontWeight: 700,
    letterSpacing: 0,
  } as const;

  return (
    <section data-testid="positions-page">
      <PageDecisionHero
        testId="positions-decision-hero"
        title="持仓透视"
        titleTestId="positions-page-title"
        eyebrow="组合工作台"
        businessQuestion="先锁定报告日和观察区间，再判断债券评级收益率、行业分布和客户集中度是否需要下钻。"
        actions={<span style={dataModeStyle}>{dataModeLabel}</span>}
        reportDateSlot={
          <span>
            报表日：{reportDate || "—"} · 区间：{startDate || "—"} ~ {endDate || "—"} ·
            数据来源：ZQTZ + TYWL
          </span>
        }
        conclusion={
          <DataStatusStrip testId="positions-data-status">
            <span>日均分母=有数据 report_date 数</span>
            <span>{tab === "bonds" ? "当前：债券持仓" : "当前：同业持仓"}</span>
            <span>{activeScopeLabel}</span>
          </DataStatusStrip>
        }
      >
        <KpiBand testId="positions-kpi-band">
          <KpiBandMetric label="区间起" value={startDate || "—"} footer="当前查询起始日" />
          <KpiBandMetric label="区间止" value={endDate || "—"} footer="当前查询结束日" />
          <KpiBandMetric
            label={tab === "bonds" ? "业务种类" : "产品类型"}
            value={activeScopeLabel}
            footer={tab === "bonds" ? "债券主筛选" : "同业主筛选"}
          />
          <KpiBandMetric label={tab === "bonds" ? "客户搜索" : "方向/对手方"} value={activePeerFilterLabel} />
        </KpiBand>
      </PageDecisionHero>

      <PageFilterTray testId="positions-filter-tray" style={{ marginBottom: 16 }}>
        <FilterBar>
          <div>
            <Typography.Text type="secondary">报告日</Typography.Text>
            <div>
              <Select
                aria-label="positions-report-date"
                style={{ minWidth: 160 }}
                value={reportDate || undefined}
                placeholder="选择报告日"
                disabled={Boolean(explicitReportDate) || datesBlockingError}
                options={dateOptions.map((d) => ({ value: d, label: d }))}
                onChange={(v) => setSelectedReportDate(v)}
              />
            </div>
          </div>
          <div>
            <Typography.Text type="secondary">区间起</Typography.Text>
            <div>
              <Input
                type="date"
                value={rangeFrom}
                onChange={(e) => {
                  setRangeTouched(true);
                  setRangeFrom(e.target.value);
                }}
                disabled={!reportDate}
              />
            </div>
          </div>
          <div>
            <Typography.Text type="secondary">区间止</Typography.Text>
            <div>
              <Input
                type="date"
                value={rangeTo}
                onChange={(e) => {
                  setRangeTouched(true);
                  setRangeTo(e.target.value);
                }}
                disabled={!reportDate}
              />
            </div>
          </div>
          {explicitReportDate ? (
            <Typography.Text type="secondary" style={{ alignSelf: "flex-end" }}>
              已由地址栏报告日参数固定
            </Typography.Text>
          ) : null}
        </FilterBar>
      </PageFilterTray>

      {datesBlockingError ? (
        <Typography.Text type="danger">无法加载资产负债可用日期，请稍后重试。</Typography.Text>
      ) : null}
      {datesEmpty ? (
        <Typography.Text type="secondary">暂无可用报告日。</Typography.Text>
      ) : null}

      <div className="positions-view__workspace-head">
        <div>
          <span className="positions-view__eyebrow">正式读面</span>
          <h2 className="positions-view__workspace-title">持仓工作区</h2>
        </div>
        <Tabs
          className="positions-view__tabs"
          activeKey={tab}
          onChange={(k) => setTab(k as TabKey)}
          items={[
            { key: "bonds", label: "债券持仓" },
            { key: "interbank", label: "同业持仓" },
          ]}
        />
      </div>

      {tab === "bonds" ? (
        <>
          <Row gutter={[16, 16]} className="positions-view__analysis-row">
          <Col xs={24} xl={16}>
            <Card size="small" className="positions-view__control-card">
              <Space wrap style={{ width: "100%" }} align="end">
                <div style={{ flex: "1 1 200px" }}>
                  <Typography.Text type="secondary">业务种类</Typography.Text>
                  <Select
                    aria-label="positions-bond-subtype"
                    data-testid="positions-bond-subtype-select"
                    style={{ width: "100%", marginTop: 4 }}
                    value={selectedSubType || ALL_BOND_SUBTYPE}
                    loading={bondSubTypesQuery.isLoading}
                    options={[
                      { value: ALL_BOND_SUBTYPE, label: "全部业务种类" },
                      ...(bondSubTypesQuery.data ?? []).map((s) => ({ value: s, label: s })),
                    ]}
                    onChange={(v) => setSelectedSubType(v === ALL_BOND_SUBTYPE ? "" : v)}
                  />
                </div>
                <div style={{ flex: "1 1 220px" }}>
                  <Typography.Text type="secondary">授信主体搜索（右侧客户表）</Typography.Text>
                  <Input
                    style={{ marginTop: 4 }}
                    placeholder="输入客户名称…"
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                  />
                </div>
              </Space>
            </Card>

            <Card
              size="small"
              className="positions-view__table-card"
              title={selectedSubType || "全部债券持仓"}
              extra={
                bondsListQuery.data ? (
                  <Typography.Text type="secondary">
                    {bondsListQuery.data.total} 条 · 第 {page}/{Math.max(1, totalPages)} 页
                  </Typography.Text>
                ) : null
              }
            >
              {listLoading ? (
                <div className="positions-view__loading">
                  <Spin />
                </div>
              ) : bondsListQuery.data && bondsListQuery.data.items.length > 0 ? (
                <>
                  <Table
                    size="small"
                    pagination={false}
                    scroll={{ x: "max-content" }}
                    dataSource={bondsListQuery.data.items.map((row, index) => ({
                      key: [
                        page,
                        index,
                        row.bond_code || "",
                        row.asset_class || "",
                        row.market_value || "",
                      ].join(":"),
                      ...row,
                    }))}
                    columns={[
                      { title: "代码", dataIndex: "bond_code" },
                      { title: "授信主体", dataIndex: "credit_name", render: (v: string | null) => v || "—" },
                      { title: "业务种类", dataIndex: "sub_type", render: (v: string | null) => v || "—" },
                      {
                        title: "市值",
                        dataIndex: "market_value",
                        align: "right",
                        render: (v: string | null) => formatAmountYi(v),
                      },
                      {
                        title: "估值净价",
                        dataIndex: "valuation_net_price",
                        align: "right",
                        render: (v: string | null) => (v ? `${v}` : "—"),
                      },
                      {
                        title: "收益率",
                        dataIndex: "yield_rate",
                        align: "right",
                        render: (v: string | null) => formatRatePercent(v),
                      },
                    ]}
                  />
                  {currentList ? (
                    <Space className="positions-view__pager">
                      <Typography.Text type="secondary">
                        共 {currentList.total} 条，第 {page}/{Math.max(1, totalPages)} 页
                      </Typography.Text>
                      <Space>
                        <Button disabled={!canPrev} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                          上一页
                        </Button>
                        <Button disabled={!canNext} onClick={() => setPage((p) => p + 1)}>
                          下一页
                        </Button>
                      </Space>
                    </Space>
                  ) : null}
                </>
              ) : (
                <Typography.Text type="secondary">暂无数据</Typography.Text>
              )}
            </Card>
          </Col>

          <Col xs={24} xl={8}>
            <Space direction="vertical" size={12} className="positions-view__insight-rail">
              <BondsPortfolioSnapshotCard stats={bondsCp} loading={bondsCpQuery.isLoading} />
              <Card
                size="small"
                title="授信主体"
                extra={<Typography.Text type="secondary">Top 50 · 点击下钻</Typography.Text>}
              >
                {bondsCpQuery.isLoading ? (
                  <div className="positions-view__loading">
                    <Spin />
                  </div>
                ) : bondsCp && filteredBondsCpItems.length > 0 ? (
                  <Table
                    size="small"
                    pagination={false}
                    scroll={{ x: "max-content" }}
                    dataSource={filteredBondsCpItems.map((row) => ({
                      key: row.customer_name,
                      ...row,
                    }))}
                    onRow={(record) => ({
                      onClick: () => {
                        setSelectedCustomer(record.customer_name);
                        setCustomerModalOpen(true);
                      },
                      style: { cursor: "pointer" },
                    })}
                    columns={[
                      {
                        title: "客户",
                        dataIndex: "customer_name",
                        ellipsis: true,
                        render: (v: string) => (
                          <Typography.Link>{v}</Typography.Link>
                        ),
                      },
                      {
                        title: "日均",
                        dataIndex: "avg_daily_balance",
                        align: "right",
                        render: (v: string) => formatAmountYi(v),
                      },
                      {
                        title: "加权收益率",
                        dataIndex: "weighted_rate",
                        align: "right",
                        render: (v: string | null) => formatRatePercent(v),
                      },
                      {
                        title: "加权付息率",
                        dataIndex: "weighted_coupon_rate",
                        align: "right",
                        render: (v: string | null | undefined) =>
                          v ? formatRatePercent(v) : "—",
                      },
                    ]}
                  />
                ) : (
                  <Typography.Text type="secondary">暂无数据</Typography.Text>
                )}
              </Card>
              <PositionsQualityPanel
                startDate={startDate}
                endDate={endDate}
                subType={selectedSubType || null}
                counterpartyStats={bondsCp}
              />
              <RatingDistributionCard
                startDate={startDate}
                endDate={endDate}
                subType={selectedSubType || null}
              />
              <IndustryDistributionCard
                startDate={startDate}
                endDate={endDate}
                subType={selectedSubType || null}
              />
            </Space>
          </Col>
        </Row>
        </>
      ) : (
        <>
          <Row gutter={[16, 16]} className="positions-view__analysis-row">
            <Col xs={24} xl={16}>
              <Card size="small" className="positions-view__control-card">
                <Space wrap style={{ width: "100%" }} align="end">
                  <div style={{ flex: "1 1 200px" }}>
                    <Typography.Text type="secondary">产品类型</Typography.Text>
                    <Select
                      style={{ width: "100%", marginTop: 4 }}
                      value={selectedProductType || ALL_INTERBANK_PRODUCT}
                      loading={interbankProductTypesQuery.isLoading}
                      options={[
                        { value: ALL_INTERBANK_PRODUCT, label: "全部产品类型" },
                        ...(interbankProductTypesQuery.data ?? []).map((s) => ({
                          value: s,
                          label: s,
                        })),
                      ]}
                      onChange={(v) => setSelectedProductType(v === ALL_INTERBANK_PRODUCT ? "" : v)}
                    />
                  </div>
                  <Button onClick={() => setInterbankFilterOpen(true)}>筛选</Button>
                  <div style={{ flex: "1 1 220px" }}>
                    <Typography.Text type="secondary">对手方搜索（右侧客户表）</Typography.Text>
                    <Input
                      style={{ marginTop: 4 }}
                      placeholder="输入对手方名称…"
                      value={searchText}
                      onChange={(e) => setSearchText(e.target.value)}
                    />
                  </div>
                </Space>
              </Card>

              <Card
                size="small"
                className="positions-view__table-card"
                title={selectedProductType || "全部同业持仓"}
                extra={
                  interbankListQuery.data ? (
                    <Typography.Text type="secondary">
                      {interbankListQuery.data.total} 条 · 第 {page}/{Math.max(1, totalPages)} 页
                    </Typography.Text>
                  ) : null
                }
              >
                {listLoading ? (
                  <div className="positions-view__loading">
                    <Spin />
                  </div>
                ) : interbankListQuery.data && interbankListQuery.data.items.length > 0 ? (
                  <>
                    <Table
                      size="small"
                      pagination={false}
                      scroll={{ x: "max-content" }}
                      dataSource={interbankListQuery.data.items.map((row, index) => ({
                        key: [
                          page,
                          index,
                          row.deal_id || "",
                          row.counterparty || "",
                          row.amount || "",
                        ].join(":"),
                        ...row,
                      }))}
                      columns={[
                        { title: "交易ID", dataIndex: "deal_id" },
                        { title: "对手方", dataIndex: "counterparty", ellipsis: true, render: (v: string | null) => v || "—" },
                        { title: "产品类型", dataIndex: "product_type", render: (v: string | null) => v || "—" },
                        { title: "方向", dataIndex: "direction", render: (v: string | null) => v || "—" },
                        {
                          title: "金额",
                          dataIndex: "amount",
                          align: "right",
                          render: (v: string) => formatAmountYi(v),
                        },
                        {
                          title: "利率",
                          dataIndex: "interest_rate",
                          align: "right",
                          render: (v: string | null) => formatRatePercent(v),
                        },
                        {
                          title: "到期日",
                          dataIndex: "maturity_date",
                          align: "right",
                          render: (v: string | null) => v || "—",
                        },
                      ]}
                    />
                    {currentList ? (
                      <Space className="positions-view__pager">
                        <Typography.Text type="secondary">
                          共 {currentList.total} 条，第 {page}/{Math.max(1, totalPages)} 页
                        </Typography.Text>
                        <Space>
                          <Button disabled={!canPrev} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                            上一页
                          </Button>
                          <Button disabled={!canNext} onClick={() => setPage((p) => p + 1)}>
                            下一页
                          </Button>
                        </Space>
                      </Space>
                    ) : null}
                  </>
                ) : (
                  <Typography.Text type="secondary">暂无数据</Typography.Text>
                )}
              </Card>
            </Col>

            <Col xs={24} xl={8}>
              <Space direction="vertical" size={12} className="positions-view__insight-rail">
                <Card
                  size="small"
                  title={
                    <span>
                      <span
                        style={{
                          display: "inline-block",
                          width: 8,
                          height: 8,
                          borderRadius: 999,
                          background: "#389e0d",
                          marginRight: 8,
                        }}
                      />
                      资产端（拆出/存放）
                    </span>
                  }
                  extra={<Typography.Text type="secondary">Top 50，我行收取利息</Typography.Text>}
                >
                  <Typography.Text type="secondary">分母：{interbankCpSplit?.num_days ?? "—"} 天</Typography.Text>
                  <Row gutter={16} style={{ marginTop: 8 }}>
                    <Col span={12}>
                      <Typography.Text type="secondary">日均余额</Typography.Text>
                      <div className="positions-view__side-value positions-view__side-value--asset">
                        {formatAmountYi(interbankCpSplit?.asset_total_avg_daily)}
                      </div>
                    </Col>
                    <Col span={12}>
                      <Typography.Text type="secondary">加权利率</Typography.Text>
                      <div className="positions-view__side-value positions-view__side-value--asset">
                        {interbankCpSplit?.asset_total_weighted_rate
                          ? formatRatePercent(interbankCpSplit.asset_total_weighted_rate)
                          : "—"}
                      </div>
                    </Col>
                  </Row>
                </Card>
                <Card size="small" title="资产端客户排名">
                  <Typography.Text type="secondary">
                    {interbankCpSplit?.asset_customer_count ?? 0} 户
                  </Typography.Text>
                  {interbankSplitQuery.isLoading ? (
                    <div className="positions-view__loading">
                      <Spin />
                    </div>
                  ) : filteredAssetItems.length > 0 ? (
                    <Table
                      size="small"
                      pagination={false}
                      scroll={{ x: "max-content", y: 240 }}
                      dataSource={filteredAssetItems.map((row) => ({
                        key: row.customer_name,
                        ...row,
                      }))}
                      columns={[
                        { title: "对手方", dataIndex: "customer_name", ellipsis: true },
                        {
                          title: "日均",
                          dataIndex: "avg_daily_balance",
                          align: "right",
                          render: (v: string) => formatAmountYi(v),
                        },
                        {
                          title: "利率",
                          dataIndex: "weighted_rate",
                          align: "right",
                          render: (v: string | null) => formatRatePercent(v),
                        },
                      ]}
                    />
                  ) : (
                    <Typography.Text type="secondary">暂无资产端数据</Typography.Text>
                  )}
                </Card>

                <Card
                  size="small"
                  title={
                    <span>
                      <span
                        style={{
                          display: "inline-block",
                          width: 8,
                          height: 8,
                          borderRadius: 999,
                          background: "#cf1322",
                          marginRight: 8,
                        }}
                      />
                      负债端（拆入/存入）
                    </span>
                  }
                  extra={<Typography.Text type="secondary">Top 50，我行支付利息</Typography.Text>}
                >
                  <Typography.Text type="secondary">分母：{interbankCpSplit?.num_days ?? "—"} 天</Typography.Text>
                  <Row gutter={16} style={{ marginTop: 8 }}>
                    <Col span={12}>
                      <Typography.Text type="secondary">日均余额</Typography.Text>
                      <div className="positions-view__side-value positions-view__side-value--liability">
                        {formatAmountYi(interbankCpSplit?.liability_total_avg_daily)}
                      </div>
                    </Col>
                    <Col span={12}>
                      <Typography.Text type="secondary">加权利率</Typography.Text>
                      <div className="positions-view__side-value positions-view__side-value--liability">
                        {interbankCpSplit?.liability_total_weighted_rate
                          ? formatRatePercent(interbankCpSplit.liability_total_weighted_rate)
                          : "—"}
                      </div>
                    </Col>
                  </Row>
                </Card>
                <Card size="small" title="负债端客户排名">
                  <Typography.Text type="secondary">
                    {interbankCpSplit?.liability_customer_count ?? 0} 户
                  </Typography.Text>
                  {interbankSplitQuery.isLoading ? (
                    <div className="positions-view__loading">
                      <Spin />
                    </div>
                  ) : filteredLiabilityItems.length > 0 ? (
                    <Table
                      size="small"
                      pagination={false}
                      scroll={{ x: "max-content", y: 240 }}
                      dataSource={filteredLiabilityItems.map((row) => ({
                        key: row.customer_name,
                        ...row,
                      }))}
                      columns={[
                        { title: "对手方", dataIndex: "customer_name", ellipsis: true },
                        {
                          title: "日均",
                          dataIndex: "avg_daily_balance",
                          align: "right",
                          render: (v: string) => formatAmountYi(v),
                        },
                        {
                          title: "利率",
                          dataIndex: "weighted_rate",
                          align: "right",
                          render: (v: string | null) => formatRatePercent(v),
                        },
                      ]}
                    />
                  ) : (
                    <Typography.Text type="secondary">暂无负债端数据</Typography.Text>
                  )}
                </Card>
              </Space>
            </Col>
          </Row>

          <Modal
            title="同业筛选"
            open={interbankFilterOpen}
            onCancel={() => setInterbankFilterOpen(false)}
            footer={[
              <Button
                key="reset"
                onClick={() => {
                  setDirection("ALL");
                }}
              >
                重置
              </Button>,
              <Button key="ok" type="primary" onClick={() => setInterbankFilterOpen(false)}>
                应用
              </Button>,
            ]}
          >
            <Typography.Text type="secondary">方向</Typography.Text>
            <Select
              style={{ width: "100%", marginTop: 8 }}
              value={direction}
              options={[
                { value: "ALL", label: "全部" },
                { value: "Asset", label: "资产" },
                { value: "Liability", label: "负债" },
              ]}
              onChange={(v) => setDirection(v as InterbankDirectionFilter)}
            />
          </Modal>
        </>
      )}

      <CustomerDetailModal
        open={customerModalOpen}
        onClose={() => setCustomerModalOpen(false)}
        customerName={selectedCustomer}
        reportDate={reportDate}
      />
    </section>
  );
}
