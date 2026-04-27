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
import { FilterBar } from "../../../components/FilterBar";
import type { PositionDirection } from "../../../api/contracts";
import { KpiCard } from "../../workbench/components/KpiCard";
import CustomerDetailModal from "./CustomerDetailModal";
import IndustryDistributionCard from "./IndustryDistributionCard";
import RatingDistributionCard from "./RatingDistributionCard";
import { formatAmountYi, formatRatePercent } from "../utils/format";

const PAGE_SIZE = 20;

type TabKey = "bonds" | "interbank";
type InterbankDirectionFilter = PositionDirection | "ALL";

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 16,
} as const;

const sectionLeadWrapStyle = {
  display: "grid",
  gap: 6,
  marginTop: 28,
} as const;

const sectionEyebrowStyle = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "#8090a8",
} as const;

const sectionTitleStyle = {
  margin: 0,
  fontSize: 18,
  fontWeight: 600,
  color: "#162033",
} as const;

const sectionDescriptionStyle = {
  margin: 0,
  maxWidth: 860,
  color: "#5c6b82",
  fontSize: 13,
  lineHeight: 1.7,
} as const;

function SectionLead(props: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div style={sectionLeadWrapStyle}>
      <span style={sectionEyebrowStyle}>{props.eyebrow}</span>
      <h2 style={sectionTitleStyle}>{props.title}</h2>
      <p style={sectionDescriptionStyle}>{props.description}</p>
    </div>
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
    enabled: tab === "bonds" && Boolean(reportDate) && Boolean(selectedSubType),
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
    enabled: tab === "interbank" && Boolean(reportDate) && Boolean(selectedProductType),
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

  return (
    <section data-testid="positions-page">
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 24,
        }}
      >
        <div>
          <Typography.Title level={2} style={{ margin: 0 }} data-testid="positions-page-title">
            持仓透视
          </Typography.Title>
          <Typography.Paragraph
            style={{ marginTop: 8, marginBottom: 0, maxWidth: 900, color: "#5c6b82" }}
          >
            报表日：{reportDate || "—"}，区间：{startDate || "—"} ~ {endDate || "—"}
            （日均分母=有数据 report_date 数）。数据来源：ZQTZ + TYWL
          </Typography.Paragraph>
        </div>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "8px 12px",
            borderRadius: 999,
            background: client.mode === "real" ? "#e8f6ee" : "#edf3ff",
            color: client.mode === "real" ? "#2f8f63" : "#1f5eff",
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          {client.mode === "real" ? "真实只读链路" : "本地演示数据"}
        </span>
      </div>

      <FilterBar style={{ marginBottom: 16 }} >
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

      {datesBlockingError ? (
        <Typography.Text type="danger">无法加载资产负债可用日期，请稍后重试。</Typography.Text>
      ) : null}
      {datesEmpty ? (
        <Typography.Text type="secondary">暂无可用报告日。</Typography.Text>
      ) : null}

      <SectionLead
        eyebrow="总览"
        title="持仓概览"
        description="先确认报告日和观察区间，再在债券持仓与同业持仓之间切换，查看右侧分布和客户维度信息。"
      />
      <Tabs
        activeKey={tab}
        onChange={(k) => setTab(k as TabKey)}
        items={[
          { key: "bonds", label: "债券持仓" },
          { key: "interbank", label: "同业持仓" },
        ]}
        style={{ marginBottom: 16 }}
      />

      {tab === "bonds" ? (
        <>
          <SectionLead
            eyebrow="债券"
            title="债券持仓"
            description="债券侧继续保留业务种类筛选、主表、评级/行业分布和授信主体视图，不改现有查询与分页逻辑。"
          />
          <Row gutter={[16, 16]}>
            <Col xs={24}>
              <div style={summaryGridStyle}>
                <KpiCard
                  title="区间起始"
                  value={startDate || "—"}
                  detail="当前查询起始日"
                  valueVariant="text"
                />
                <KpiCard
                  title="区间结束"
                  value={endDate || "—"}
                  detail="当前查询结束日"
                  valueVariant="text"
                />
                <KpiCard
                  title="业务种类"
                  value={selectedSubType || "未选择"}
                  detail="债券侧主筛选"
                  valueVariant="text"
                />
                <KpiCard
                  title="客户搜索"
                  value={searchText || "未输入"}
                  detail="影响右侧客户表"
                  valueVariant="text"
                />
              </div>
            </Col>
          <Col xs={24} xl={16}>
            <Card size="small" style={{ marginBottom: 16 }}>
              <Space wrap style={{ width: "100%" }} align="end">
                <div style={{ flex: "1 1 200px" }}>
                  <Typography.Text type="secondary">业务种类</Typography.Text>
                  <Select
                    style={{ width: "100%", marginTop: 4 }}
                    placeholder="请选择业务种类"
                    value={selectedSubType || undefined}
                    loading={bondSubTypesQuery.isLoading}
                    options={(bondSubTypesQuery.data ?? []).map((s) => ({ value: s, label: s }))}
                    onChange={(v) => setSelectedSubType(v)}
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

            <Card size="small">
              {listLoading ? (
                <div style={{ textAlign: "center", padding: 32 }}>
                  <Spin />
                </div>
              ) : !selectedSubType ? (
                <Typography.Text type="secondary">请先选择业务种类</Typography.Text>
              ) : bondsListQuery.data && bondsListQuery.data.items.length > 0 ? (
                <>
                  <Table
                    size="small"
                    pagination={false}
                    dataSource={bondsListQuery.data.items.map((row) => ({
                      key: row.bond_code,
                      ...row,
                    }))}
                    columns={[
                      { title: "代码", dataIndex: "bond_code" },
                      { title: "授信主体", dataIndex: "credit_name", render: (v: string | null) => v || "—" },
                      { title: "业务种类", dataIndex: "sub_type", render: (v: string | null) => v || "—" },
                      {
                        title: "市值(亿元)",
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
                        title: "利率",
                        dataIndex: "yield_rate",
                        align: "right",
                        render: (v: string | null) => formatRatePercent(v),
                      },
                    ]}
                  />
                  {(canPrev || canNext) && (
                    <Space style={{ marginTop: 12, justifyContent: "space-between", width: "100%" }}>
                      <Typography.Text type="secondary">
                        共 {bondsListQuery.data.total} 条，第 {page}/{Math.max(1, totalPages)} 页
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
                  )}
                </>
              ) : (
                <Typography.Text type="secondary">暂无数据</Typography.Text>
              )}
            </Card>
          </Col>

          <Col xs={24} xl={8}>
            <Space direction="vertical" size={16} style={{ width: "100%" }}>
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
              <Card size="small" title="客户维度（授信主体）">
                <Typography.Text type="secondary">Top 50，点击查看明细</Typography.Text>
                <div style={{ marginTop: 8 }}>
                  <Typography.Text>分母：{bondsCp?.num_days ?? "—"} 天</Typography.Text>
                </div>
                <Row gutter={16} style={{ marginTop: 12 }}>
                  <Col span={12}>
                    <Typography.Text type="secondary">区间累计</Typography.Text>
                    <div style={{ fontSize: 18, fontWeight: 600 }}>{formatAmountYi(bondsCp?.total_amount)}</div>
                  </Col>
                  <Col span={12}>
                    <Typography.Text type="secondary">日均合计</Typography.Text>
                    <div style={{ fontSize: 18, fontWeight: 600 }}>{formatAmountYi(bondsCp?.total_avg_daily)}</div>
                  </Col>
                </Row>
                <Row gutter={16} style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #f0f0f0" }}>
                  <Col span={12}>
                    <Typography.Text type="secondary">加权收益率</Typography.Text>
                    <div style={{ fontSize: 16, fontWeight: 600 }}>
                      {bondsCp?.total_weighted_rate ? formatRatePercent(bondsCp.total_weighted_rate) : "—"}
                    </div>
                  </Col>
                  <Col span={12}>
                    <Typography.Text type="secondary">加权付息率</Typography.Text>
                    <div style={{ fontSize: 16, fontWeight: 600 }}>
                      {bondsCp?.total_weighted_coupon_rate
                        ? formatRatePercent(bondsCp.total_weighted_coupon_rate)
                        : "—"}
                    </div>
                  </Col>
                </Row>
              </Card>
              <Card size="small">
                {bondsCpQuery.isLoading ? (
                  <div style={{ textAlign: "center", padding: 24 }}>
                    <Spin />
                  </div>
                ) : bondsCp && filteredBondsCpItems.length > 0 ? (
                  <Table
                    size="small"
                    pagination={false}
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
                        render: (v: string) => (
                          <Typography.Link>{v}</Typography.Link>
                        ),
                      },
                      {
                        title: "日均(亿元)",
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
            </Space>
          </Col>
        </Row>
        </>
      ) : (
        <>
          <SectionLead
            eyebrow="同业"
            title="同业持仓"
            description="同业侧继续保留产品类型、方向筛选、主表与资产/负债端客户排名，只做壳层层级收敛。"
          />
          <div style={summaryGridStyle}>
            <KpiCard
              title="区间起始"
              value={startDate || "—"}
              detail="当前查询起始日"
              valueVariant="text"
            />
            <KpiCard
              title="区间结束"
              value={endDate || "—"}
              detail="当前查询结束日"
              valueVariant="text"
            />
            <KpiCard
              title="产品类型"
              value={selectedProductType || "未选择"}
              detail="同业侧主筛选"
              valueVariant="text"
            />
            <KpiCard
              title="方向"
              value={direction}
              detail="同业方向筛选"
              valueVariant="text"
            />
          </div>
          <Row gutter={[16, 16]}>
            <Col xs={24} xl={16}>
              <Card size="small" style={{ marginBottom: 16 }}>
                <Space wrap style={{ width: "100%" }} align="end">
                  <div style={{ flex: "1 1 200px" }}>
                    <Typography.Text type="secondary">产品类型</Typography.Text>
                    <Select
                      style={{ width: "100%", marginTop: 4 }}
                      placeholder="请选择产品类型"
                      value={selectedProductType || undefined}
                      loading={interbankProductTypesQuery.isLoading}
                      options={(interbankProductTypesQuery.data ?? []).map((s) => ({
                        value: s,
                        label: s,
                      }))}
                      onChange={(v) => setSelectedProductType(v)}
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

              <Card size="small">
                {listLoading ? (
                  <div style={{ textAlign: "center", padding: 32 }}>
                    <Spin />
                  </div>
                ) : !selectedProductType ? (
                  <Typography.Text type="secondary">请先选择产品类型</Typography.Text>
                ) : interbankListQuery.data && interbankListQuery.data.items.length > 0 ? (
                  <>
                    <Table
                      size="small"
                      pagination={false}
                      dataSource={interbankListQuery.data.items.map((row) => ({
                        key: row.deal_id,
                        ...row,
                      }))}
                      columns={[
                        { title: "交易ID", dataIndex: "deal_id" },
                        { title: "对手方", dataIndex: "counterparty", render: (v: string | null) => v || "—" },
                        { title: "产品类型", dataIndex: "product_type", render: (v: string | null) => v || "—" },
                        { title: "方向", dataIndex: "direction", render: (v: string | null) => v || "—" },
                        {
                          title: "金额(亿元)",
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
                    {(canPrev || canNext) && (
                      <Space style={{ marginTop: 12, justifyContent: "space-between", width: "100%" }}>
                        <Typography.Text type="secondary">
                          共 {interbankListQuery.data.total} 条，第 {page}/{Math.max(1, totalPages)} 页
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
                    )}
                  </>
                ) : (
                  <Typography.Text type="secondary">暂无数据</Typography.Text>
                )}
              </Card>
            </Col>

            <Col xs={24} xl={8}>
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
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
                      <div style={{ fontSize: 18, fontWeight: 600, color: "#237804" }}>
                        {formatAmountYi(interbankCpSplit?.asset_total_avg_daily)}
                      </div>
                    </Col>
                    <Col span={12}>
                      <Typography.Text type="secondary">加权利率</Typography.Text>
                      <div style={{ fontSize: 18, fontWeight: 600, color: "#237804" }}>
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
                    <div style={{ textAlign: "center", padding: 24 }}>
                      <Spin />
                    </div>
                  ) : filteredAssetItems.length > 0 ? (
                    <Table
                      size="small"
                      pagination={false}
                      scroll={{ y: 240 }}
                      dataSource={filteredAssetItems.map((row) => ({
                        key: row.customer_name,
                        ...row,
                      }))}
                      columns={[
                        { title: "对手方", dataIndex: "customer_name", ellipsis: true },
                        {
                          title: "日均(亿)",
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
                      <div style={{ fontSize: 18, fontWeight: 600, color: "#a8071a" }}>
                        {formatAmountYi(interbankCpSplit?.liability_total_avg_daily)}
                      </div>
                    </Col>
                    <Col span={12}>
                      <Typography.Text type="secondary">加权利率</Typography.Text>
                      <div style={{ fontSize: 18, fontWeight: 600, color: "#a8071a" }}>
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
                    <div style={{ textAlign: "center", padding: 24 }}>
                      <Spin />
                    </div>
                  ) : filteredLiabilityItems.length > 0 ? (
                    <Table
                      size="small"
                      pagination={false}
                      scroll={{ y: 240 }}
                      dataSource={filteredLiabilityItems.map((row) => ({
                        key: row.customer_name,
                        ...row,
                      }))}
                      columns={[
                        { title: "对手方", dataIndex: "customer_name", ellipsis: true },
                        {
                          title: "日均(亿)",
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
