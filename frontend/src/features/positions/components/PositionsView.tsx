import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
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
import type { TableColumnsType } from "antd";
import { Link, useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { buildBondTradingDeskPath } from "../../bond-trading-desk/lib/bondTradingDeskPageModel";
import { FilterBar } from "../../../components/FilterBar";
import type {
  BondPositionItem,
  CounterpartyStatItem,
  CounterpartyStatsResponse,
  IndustryStatsResponse,
  InterbankPositionItem,
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

type BondListRow = BondPositionItem & { key: string };
type InterbankListRow = InterbankPositionItem & { key: string };
type CounterpartyRow = CounterpartyStatItem & { key: string };

const INTERBANK_LIST_COLUMNS: TableColumnsType<InterbankListRow> = [
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
];

const BONDS_COUNTERPARTY_COLUMNS: TableColumnsType<CounterpartyRow> = [
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
];

const INTERBANK_COUNTERPARTY_RANK_COLUMNS: TableColumnsType<CounterpartyRow> = [
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
];

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
  return `${meta.quality_flag} / ${compactVersion(meta.source_version)} / ${compactVersion(meta.rule_version)}`;
}

type PositionsFirstScreenStatus = {
  type: "error" | "warning" | "info";
  message: string;
  description: string;
};

type PositionsPrimaryListTableState = "loading" | "error" | "blocked" | "empty" | "ready";

type PositionsPrimaryListMeta = Pick<
  ResultMeta,
  | "quality_flag"
  | "vendor_status"
  | "fallback_mode"
  | "requested_report_date"
  | "resolved_report_date"
  | "as_of_date"
  | "fallback_date"
>;

type PositionsPrimaryListResult<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

type PositionsPrimaryListEnvelope<T> = {
  result_meta: PositionsPrimaryListMeta;
  result: PositionsPrimaryListResult<T>;
};

const POSITIONS_QUALITY_FLAGS: readonly ResultMeta["quality_flag"][] = [
  "ok",
  "warning",
  "error",
  "stale",
  "missing",
];
const POSITIONS_VENDOR_STATUSES: readonly ResultMeta["vendor_status"][] = [
  "ok",
  "vendor_stale",
  "vendor_unavailable",
];
const POSITIONS_FALLBACK_MODES: readonly ResultMeta["fallback_mode"][] = [
  "none",
  "latest_snapshot",
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isAllowedStatus<T extends string>(
  value: unknown,
  allowed: readonly T[],
): value is T {
  return typeof value === "string" && (allowed as readonly string[]).includes(value);
}

function isOptionalDate(value: unknown): value is string | null | undefined {
  return value === undefined || value === null || typeof value === "string";
}

function normalizePositionsPrimaryListEnvelope<T>(
  value: unknown,
): PositionsPrimaryListEnvelope<T> | null {
  if (!isRecord(value) || !isRecord(value.result_meta) || !isRecord(value.result)) {
    return null;
  }

  const meta = value.result_meta;
  const result = value.result;
  const qualityFlag = meta.quality_flag;
  const vendorStatus = meta.vendor_status;
  const fallbackMode = meta.fallback_mode;
  if (
    !isAllowedStatus(qualityFlag, POSITIONS_QUALITY_FLAGS) ||
    !isAllowedStatus(vendorStatus, POSITIONS_VENDOR_STATUSES) ||
    !isAllowedStatus(fallbackMode, POSITIONS_FALLBACK_MODES) ||
    !isOptionalDate(meta.requested_report_date) ||
    !isOptionalDate(meta.resolved_report_date) ||
    !isOptionalDate(meta.as_of_date) ||
    !isOptionalDate(meta.fallback_date)
  ) {
    return null;
  }

  const { items, total, page, page_size: pageSize } = result;
  if (
    !Array.isArray(items) ||
    typeof total !== "number" ||
    !Number.isFinite(total) ||
    !Number.isInteger(total) ||
    total < 0 ||
    typeof page !== "number" ||
    !Number.isInteger(page) ||
    page < 1 ||
    typeof pageSize !== "number" ||
    !Number.isInteger(pageSize) ||
    pageSize < 1
  ) {
    return null;
  }

  return {
    result_meta: {
      quality_flag: qualityFlag,
      vendor_status: vendorStatus,
      fallback_mode: fallbackMode,
      requested_report_date: meta.requested_report_date,
      resolved_report_date: meta.resolved_report_date,
      as_of_date: meta.as_of_date,
      fallback_date: meta.fallback_date,
    },
    result: {
      items: items as T[],
      total,
      page,
      page_size: pageSize,
    },
  };
}

function buildPositionsPrimaryListTableState({
  reportDate,
  datesLoading,
  datesError,
  listLoading,
  listSuccess,
  listError,
  envelope,
}: {
  reportDate: string;
  datesLoading: boolean;
  datesError: boolean;
  listLoading: boolean;
  listSuccess: boolean;
  listError: boolean;
  envelope: PositionsPrimaryListEnvelope<unknown> | null;
}): PositionsPrimaryListTableState {
  if (!reportDate) {
    if (datesLoading) {
      return "loading";
    }
    return datesError ? "error" : "blocked";
  }

  if (listError) {
    return "error";
  }
  if (listLoading || !listSuccess) {
    return "loading";
  }

  if (!envelope) {
    return "error";
  }
  if (envelope.result.total === 0 && envelope.result.items.length === 0) {
    return "empty";
  }
  if (envelope.result.items.length === 0) {
    return "blocked";
  }
  return "ready";
}

function buildPositionsFirstScreenStatus({
  tab,
  datesError,
  datesEmpty,
  listError,
  listTableState,
  meta,
}: {
  tab: TabKey;
  datesError: boolean;
  datesEmpty: boolean;
  listError: boolean;
  listTableState: PositionsPrimaryListTableState;
  meta: PositionsPrimaryListMeta | undefined;
}): PositionsFirstScreenStatus | null {
  const listLabel = tab === "bonds" ? "债券持仓" : "同业持仓";

  if (datesError) {
    return {
      type: "error",
      message: "可用报告日加载失败",
      description: "当前无法确定持仓报告日，请稍后重试。",
    };
  }

  if (listError) {
    return {
      type: "error",
      message: `${listLabel}加载失败`,
      description: "持仓请求未成功，请稍后重试。",
    };
  }

  if (listTableState === "error") {
    return {
      type: "error",
      message: `${listLabel}响应不完整`,
      description: "当前返回内容缺少必要的数据或状态信息，请稍后重试。",
    };
  }

  if (meta?.quality_flag === "error" || meta?.vendor_status === "vendor_unavailable") {
    return {
      type: "error",
      message: `${listLabel}数据当前不可用`,
      description: "当前返回结果未达到可用状态，请稍后重试。",
    };
  }

  if (datesEmpty) {
    return {
      type: "info",
      message: "暂无可用报告日",
      description: "当前无法查询持仓数据。",
    };
  }

  if (listTableState === "empty") {
    return {
      type: "info",
      message: `当前报告日暂无${listLabel}数据`,
      description: "可调整报告日或筛选条件后重试。",
    };
  }

  const stale = meta?.quality_flag === "stale" || meta?.vendor_status === "vendor_stale";
  if (meta?.fallback_mode === "latest_snapshot") {
    const dateDetails = [
      meta.requested_report_date ? `请求日期 ${meta.requested_report_date}` : null,
      meta.resolved_report_date ? `解析日期 ${meta.resolved_report_date}` : null,
      meta.as_of_date ? `有效日期 ${meta.as_of_date}` : null,
      meta.fallback_date ? `回退日期 ${meta.fallback_date}` : null,
    ].filter((item): item is string => Boolean(item));
    return {
      type: "warning",
      message: stale
        ? `${listLabel}已回退至最近可用快照，且该快照可能偏旧`
        : `${listLabel}已回退到最近可用快照`,
      description:
        dateDetails.length > 0
          ? `${dateDetails.join("，")}。`
          : "当前使用最近可用快照，请确认数据日期后使用。",
    };
  }

  if (stale) {
    const effectiveDate = meta.as_of_date || meta.resolved_report_date || meta.fallback_date;
    return {
      type: "warning",
      message: `${listLabel}数据可能偏旧`,
      description: effectiveDate
        ? `有效日期 ${effectiveDate}，请确认后使用。`
        : "当前数据可能滞后，请确认日期后使用。",
    };
  }

  return null;
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
            {topRating ? `${topRating.rating} / ${topRating.percentage}%` : "—"}
          </span>
        </div>
        <div className="positions-view__quality-item">
          <span className="positions-view__quality-label">最高行业集中</span>
          <span className="positions-view__quality-value">
            {topIndustry ? `${topIndustry.industry} / ${topIndustry.percentage}%` : "—"}
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

  const handleTabChange = (nextTab: TabKey) => {
    setPage(1);
    setSearchText("");
    if (nextTab === "bonds") {
      setSelectedProductType("");
      setDirection("ALL");
    } else {
      setSelectedSubType("");
    }
    setTab(nextTab);
  };

  const handleReportDateChange = (nextReportDate: string) => {
    setPage(1);
    setSelectedSubType("");
    setSelectedProductType("");
    setDirection("ALL");
    setSelectedReportDate(nextReportDate);
  };

  const handleBondSubTypeChange = (nextSubType: string) => {
    setPage(1);
    setSelectedSubType(nextSubType === ALL_BOND_SUBTYPE ? "" : nextSubType);
  };

  const handleInterbankProductTypeChange = (nextProductType: string) => {
    setPage(1);
    setSelectedProductType(nextProductType === ALL_INTERBANK_PRODUCT ? "" : nextProductType);
  };

  const handleDirectionChange = (nextDirection: InterbankDirectionFilter) => {
    setPage(1);
    setDirection(nextDirection);
  };

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
    setPage(1);
    setSelectedSubType("");
    setSelectedProductType("");
    setDirection("ALL");
  }, [reportDate]);

  const bondsListQuery = useQuery({
    queryKey: ["positions", "bonds-list", client.mode, reportDate, selectedSubType, page],
    queryFn: () =>
      client.getPositionsBondsList({
        reportDate: reportDate || null,
        subType: selectedSubType || null,
        page,
        pageSize: PAGE_SIZE,
        includeIssued: false,
      }),
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
    queryFn: () =>
      client.getPositionsInterbankList({
        reportDate: reportDate || null,
        productType: selectedProductType || null,
        direction,
        page,
        pageSize: PAGE_SIZE,
      }),
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
  const bondsListEnvelope = normalizePositionsPrimaryListEnvelope<BondPositionItem>(
    bondsListQuery.data,
  );
  const interbankListEnvelope = normalizePositionsPrimaryListEnvelope<InterbankPositionItem>(
    interbankListQuery.data,
  );
  const bondsList = bondsListEnvelope?.result;
  const interbankList = interbankListEnvelope?.result;

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

  const bondsListDataSource = useMemo<BondListRow[]>(
    () =>
      (bondsList?.items ?? []).map((row, index) => ({
        key: [
          page,
          index,
          row.bond_code || "",
          row.asset_class || "",
          row.market_value || "",
        ].join(":"),
        ...row,
      })),
    [bondsList?.items, page],
  );

  const bondsListColumns = useMemo<TableColumnsType<BondListRow>>(
    () => [
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
      {
        title: "单券台",
        key: "trading_desk",
        render: (_: unknown, row: BondPositionItem) =>
          row.bond_code ? (
            <Link
              to={buildBondTradingDeskPath(row.bond_code, reportDate)}
              data-testid={`positions-bond-trading-desk-link-${row.bond_code}`}
            >
              打开
            </Link>
          ) : (
            "—"
          ),
      },
    ],
    [reportDate],
  );

  const interbankListDataSource = useMemo<InterbankListRow[]>(
    () =>
      (interbankList?.items ?? []).map((row, index) => ({
        key: [
          page,
          index,
          row.deal_id || "",
          row.counterparty || "",
          row.amount || "",
        ].join(":"),
        ...row,
      })),
    [interbankList?.items, page],
  );

  const bondsCpDataSource = useMemo<CounterpartyRow[]>(
    () =>
      filteredBondsCpItems.map((row) => ({
        key: row.customer_name,
        ...row,
      })),
    [filteredBondsCpItems],
  );

  const assetRankDataSource = useMemo<CounterpartyRow[]>(
    () =>
      filteredAssetItems.map((row) => ({
        key: row.customer_name,
        ...row,
      })),
    [filteredAssetItems],
  );

  const liabilityRankDataSource = useMemo<CounterpartyRow[]>(
    () =>
      filteredLiabilityItems.map((row) => ({
        key: row.customer_name,
        ...row,
      })),
    [filteredLiabilityItems],
  );

  const currentListEnvelope = tab === "bonds" ? bondsListEnvelope : interbankListEnvelope;
  const currentList = currentListEnvelope?.result;
  const listLoading = tab === "bonds" ? bondsListQuery.isLoading : interbankListQuery.isLoading;
  const listSuccess = tab === "bonds" ? bondsListQuery.isSuccess : interbankListQuery.isSuccess;
  const listError = tab === "bonds" ? bondsListQuery.isError : interbankListQuery.isError;
  const listTableState = buildPositionsPrimaryListTableState({
    reportDate,
    datesLoading: datesQuery.isLoading,
    datesError: datesQuery.isError,
    listLoading,
    listSuccess,
    listError,
    envelope: currentListEnvelope,
  });
  const currentListTotal = currentList?.total;
  const currentListItemCount = currentList?.items.length;

  useEffect(() => {
    if (
      page > 1 &&
      listTableState === "blocked" &&
      currentListTotal != null &&
      currentListTotal > 0 &&
      currentListItemCount === 0
    ) {
      setPage(1);
    }
  }, [currentListItemCount, currentListTotal, listTableState, page]);

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
      : `${direction === "ALL" ? "全部方向" : direction === "Asset" ? "资产端" : "负债端"} / ${
          searchText || "未输入对手方"
        }`;
  const dataModeLabel = client.mode === "real" ? "真实只读链路" : "本地演示数据";
  const dataModeClass =
    client.mode === "real"
      ? "positions-view__mode-pill positions-view__mode-pill--real"
      : "positions-view__mode-pill positions-view__mode-pill--mock";
  const firstScreenStatus = buildPositionsFirstScreenStatus({
    tab,
    datesError: datesBlockingError,
    datesEmpty,
    listError,
    listTableState,
    meta: currentListEnvelope?.result_meta,
  });

  /*
   * 深色 owner 由外层 ThemedRouteBoundary 的 data-moss-theme="dark" 独占；
   * 页根只声明换肤 scope，重复声明 owner 会让深色路由校验判定出两个 owner。
   */
  return (
    <section
      className="positions-view theme-dh-api"
      data-testid="positions-page"
      data-moss-theme-scope="positions"
    >
      <PageDecisionHero
        testId="positions-decision-hero"
        title="持仓透视"
        titleTestId="positions-page-title"
        eyebrow="组合工作台"
        businessQuestion="先锁定报告日和观察区间，再判断债券评级收益率、行业分布和客户集中度是否需要下钻。"
        actions={<span className={dataModeClass}>{dataModeLabel}</span>}
        reportDateSlot={
          <span>
            {/* DESIGN.md §7: meta line · quota ≤ 1 */}
            报表日：{reportDate || "—"} · 区间：{startDate || "—"} ~ {endDate || "—"}
            {" | "}
            数据来源：ZQTZ + TYWL
          </span>
        }
        conclusion={
          <>
            {firstScreenStatus ? (
              <Alert
                data-testid="positions-data-state-alert"
                type={firstScreenStatus.type}
                showIcon
                message={firstScreenStatus.message}
                description={firstScreenStatus.description}
              />
            ) : null}
            <Alert
              data-testid="positions-list-candidate-boundary"
              className="positions-view__candidate-boundary"
              type="warning"
              showIcon
              message="持仓列表指标边界"
              description="GAP-POS-LIST 尚未关闭；MTR-POS-001、MTR-POS-002 仍为 candidate，pending_confirmation=true，bound_sample_id=none。"
            />
            <DataStatusStrip testId="positions-data-status">
              <span>日均分母=有数据 report_date 数</span>
              <span>{tab === "bonds" ? "当前：债券持仓" : "当前：同业持仓"}</span>
              <span>{activeScopeLabel}</span>
            </DataStatusStrip>
          </>
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
                onChange={handleReportDateChange}
              />
            </div>
          </div>
          <div>
            <Typography.Text type="secondary">区间起</Typography.Text>
            <div>
              <Input
                aria-label="持仓区间起始日期"
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
                aria-label="持仓区间结束日期"
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
            <Typography.Text type="secondary" className="positions-view__filter-self-end">
              已由地址栏报告日参数固定
            </Typography.Text>
          ) : null}
        </FilterBar>
      </PageFilterTray>

      <div className="positions-view__workspace-head">
        <div>
          <span className="positions-view__eyebrow">正式读面</span>
          <h2 className="positions-view__workspace-title">持仓工作区</h2>
        </div>
        <Tabs
          className="positions-view__tabs"
          activeKey={tab}
          onChange={(k) => handleTabChange(k as TabKey)}
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
              <Space wrap className="positions-view__full-width" align="end">
                <div className="positions-view__filter-field">
                  <Typography.Text type="secondary">业务种类</Typography.Text>
                  <Select
                    aria-label="positions-bond-subtype"
                    data-testid="positions-bond-subtype-select"
                    className="positions-view__control-gap"
                    value={selectedSubType || ALL_BOND_SUBTYPE}
                    loading={bondSubTypesQuery.isLoading}
                    options={[
                      { value: ALL_BOND_SUBTYPE, label: "全部业务种类" },
                      ...(bondSubTypesQuery.data ?? []).map((s) => ({ value: s, label: s })),
                    ]}
                    onChange={handleBondSubTypeChange}
                  />
                </div>
                <div className="positions-view__filter-field--wide">
                  <Typography.Text type="secondary">授信主体搜索（右侧客户表）</Typography.Text>
                  <Input
                    className="positions-view__control-gap"
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
                bondsList ? (
                  <Typography.Text type="secondary">
                    {bondsList.total} 条 / 第 {page}/{Math.max(1, totalPages)} 页
                  </Typography.Text>
                ) : null
              }
            >
              {listTableState === "loading" ? (
                <div
                  className="positions-view__loading"
                  data-testid="positions-bonds-list-loading"
                >
                  <Spin />
                </div>
              ) : listTableState === "error" ? (
                <Typography.Text type="secondary" data-testid="positions-bonds-list-error">
                  债券持仓暂不可用
                </Typography.Text>
              ) : listTableState === "ready" ? (
                <>
                  <Table
                    size="small"
                    pagination={false}
                    scroll={{ x: "max-content" }}
                    dataSource={bondsListDataSource}
                    columns={bondsListColumns}
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
              ) : listTableState === "empty" ? (
                <Typography.Text type="secondary" data-testid="positions-bonds-list-empty">
                  暂无数据
                </Typography.Text>
              ) : (
                <Typography.Text type="secondary" data-testid="positions-bonds-list-blocked">
                  {reportDate
                    ? page > 1
                      ? "当前页无明细，正在返回第一页"
                      : "当前范围明细暂不可用"
                    : "请先选择可用报告日"}
                </Typography.Text>
              )}
            </Card>
          </Col>

          <Col xs={24} xl={8}>
            <Space direction="vertical" size={12} className="positions-view__insight-rail">
              <BondsPortfolioSnapshotCard stats={bondsCp} loading={bondsCpQuery.isLoading} />
              <Card
                size="small"
                title="授信主体"
                extra={<Typography.Text type="secondary">Top 50 / 点击下钻</Typography.Text>}
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
                    dataSource={bondsCpDataSource}
                    onRow={(record) => ({
                      onClick: () => {
                        setSelectedCustomer(record.customer_name);
                        setCustomerModalOpen(true);
                      },
                      style: { cursor: "pointer" },
                    })}
                    columns={BONDS_COUNTERPARTY_COLUMNS}
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
                <Space wrap className="positions-view__full-width" align="end">
                  <div className="positions-view__filter-field">
                    <Typography.Text type="secondary">产品类型</Typography.Text>
                    <Select
                      className="positions-view__control-gap"
                      value={selectedProductType || ALL_INTERBANK_PRODUCT}
                      loading={interbankProductTypesQuery.isLoading}
                      options={[
                        { value: ALL_INTERBANK_PRODUCT, label: "全部产品类型" },
                        ...(interbankProductTypesQuery.data ?? []).map((s) => ({
                          value: s,
                          label: s,
                        })),
                      ]}
                      onChange={handleInterbankProductTypeChange}
                    />
                  </div>
                  <Button onClick={() => setInterbankFilterOpen(true)}>筛选</Button>
                  <div className="positions-view__filter-field--wide">
                    <Typography.Text type="secondary">对手方搜索（右侧客户表）</Typography.Text>
                    <Input
                      className="positions-view__control-gap"
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
                  interbankList ? (
                    <Typography.Text type="secondary">
                      {interbankList.total} 条 / 第 {page}/{Math.max(1, totalPages)} 页
                    </Typography.Text>
                  ) : null
                }
              >
                {listTableState === "loading" ? (
                  <div
                    className="positions-view__loading"
                    data-testid="positions-interbank-list-loading"
                  >
                    <Spin />
                  </div>
                ) : listTableState === "error" ? (
                  <Typography.Text
                    type="secondary"
                    data-testid="positions-interbank-list-error"
                  >
                    同业持仓暂不可用
                  </Typography.Text>
                ) : listTableState === "ready" ? (
                  <>
                    <Table
                      size="small"
                      pagination={false}
                      scroll={{ x: "max-content" }}
                      dataSource={interbankListDataSource}
                      columns={INTERBANK_LIST_COLUMNS}
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
                ) : listTableState === "empty" ? (
                  <Typography.Text type="secondary" data-testid="positions-interbank-list-empty">
                    暂无数据
                  </Typography.Text>
                ) : (
                  <Typography.Text
                    type="secondary"
                    data-testid="positions-interbank-list-blocked"
                  >
                    {reportDate
                      ? page > 1
                        ? "当前页无明细，正在返回第一页"
                        : "当前范围明细暂不可用"
                      : "请先选择可用报告日"}
                  </Typography.Text>
                )}
              </Card>
            </Col>

            <Col xs={24} xl={8}>
              <Space direction="vertical" size={12} className="positions-view__insight-rail">
                <Card
                  size="small"
                  title={
                    <span>
                      <span className="positions-view__side-dot positions-view__side-dot--asset" />
                      资产端（拆出/存放）
                    </span>
                  }
                  extra={<Typography.Text type="secondary">Top 50，我行收取利息</Typography.Text>}
                >
                  <Typography.Text type="secondary">分母：{interbankCpSplit?.num_days ?? "—"} 天</Typography.Text>
                  <Row gutter={16} className="positions-view__metric-row">
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
                      dataSource={assetRankDataSource}
                      columns={INTERBANK_COUNTERPARTY_RANK_COLUMNS}
                    />
                  ) : (
                    <Typography.Text type="secondary">暂无资产端数据</Typography.Text>
                  )}
                </Card>

                <Card
                  size="small"
                  title={
                    <span>
                      <span className="positions-view__side-dot positions-view__side-dot--liability" />
                      负债端（拆入/存入）
                    </span>
                  }
                  extra={<Typography.Text type="secondary">Top 50，我行支付利息</Typography.Text>}
                >
                  <Typography.Text type="secondary">分母：{interbankCpSplit?.num_days ?? "—"} 天</Typography.Text>
                  <Row gutter={16} className="positions-view__metric-row">
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
                      dataSource={liabilityRankDataSource}
                      columns={INTERBANK_COUNTERPARTY_RANK_COLUMNS}
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
                  handleDirectionChange("ALL");
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
              className="positions-view__modal-select"
              value={direction}
              options={[
                { value: "ALL", label: "全部" },
                { value: "Asset", label: "资产" },
                { value: "Liability", label: "负债" },
              ]}
              onChange={(v) => handleDirectionChange(v as InterbankDirectionFilter)}
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
