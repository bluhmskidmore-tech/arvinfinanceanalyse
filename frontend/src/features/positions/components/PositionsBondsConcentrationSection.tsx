import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Input, Spin, Table, Typography } from "antd";
import type { TableColumnsType } from "antd";

import { useApiClient } from "../../../api/client";
import type {
  CounterpartyStatItem,
  CounterpartyStatsResponse,
  IndustryStatsResponse,
  RatingStatsResponse,
} from "../../../api/contracts";
import {
  coverageQualityDisplay,
  POSITIONS_QUERY_STALE_TIME_MS,
  rateCoveragePolicyLabel,
  topRatingItem,
} from "../model/positionsPageModel";
import { EM_DASH } from "../../../utils/format";
import { formatAmountYi, formatPercentValue, formatRatePercent } from "../utils/format";

type CounterpartyRow = CounterpartyStatItem & { key: string };

const BONDS_COUNTERPARTY_COLUMNS: TableColumnsType<CounterpartyRow> = [
  {
    title: "客户",
    dataIndex: "customer_name",
    ellipsis: true,
    render: (v: string) => <Typography.Link>{v}</Typography.Link>,
  },
  {
    title: "区间累计",
    dataIndex: "total_amount",
    align: "right",
    className: "positions-view__num-cell",
    render: (v: string) => formatAmountYi(v),
  },
  {
    title: "日均",
    dataIndex: "avg_daily_balance",
    align: "right",
    className: "positions-view__num-cell",
    render: (v: string) => formatAmountYi(v),
  },
  {
    title: "加权收益率",
    dataIndex: "weighted_rate",
    align: "right",
    className: "positions-view__num-cell",
    render: (v: string | null) => formatRatePercent(v),
  },
  {
    title: "加权付息率",
    dataIndex: "weighted_coupon_rate",
    align: "right",
    className: "positions-view__num-cell",
    render: (v: string | null | undefined) => (v ? formatRatePercent(v) : EM_DASH),
  },
  {
    title: "笔数",
    dataIndex: "transaction_count",
    align: "right",
    className: "positions-view__num-cell",
    render: (v: number | null | undefined) => (v != null ? `${v}` : EM_DASH),
  },
];

/** 质量与集中度面板：内部 useQuery 保留（queryKey 与迁移前逐字一致）。 */
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
  /*
   * queryKey 与两张分布卡共用（stats-rating / stats-industry），React Query
   * 自动去重：同一评级/行业端点此前被质量面板与分布卡各打一遍（重区间聚合
   * ×2），统一键后每组参数只发一次请求。queryFn 返回完整信封，卡侧取 .result。
   */
  const ratingEnvelopeQuery = useQuery({
    queryKey: ["positions", "stats-rating", client.mode, startDate, endDate, subType ?? ""],
    queryFn: async () => {
      if (!startDate || !endDate) {
        throw new Error("missing range");
      }
      return client.getPositionsStatsRating({
        startDate,
        endDate,
        subType: subType ?? null,
      });
    },
    enabled: Boolean(startDate && endDate),
    staleTime: POSITIONS_QUERY_STALE_TIME_MS,
    retry: false,
  });
  const industryEnvelopeQuery = useQuery({
    queryKey: ["positions", "stats-industry", client.mode, startDate, endDate, subType ?? ""],
    queryFn: async () => {
      if (!startDate || !endDate) {
        throw new Error("missing range");
      }
      return client.getPositionsStatsIndustry({
        startDate,
        endDate,
        subType: subType ?? null,
        topN: 10,
      });
    },
    enabled: Boolean(startDate && endDate),
    staleTime: POSITIONS_QUERY_STALE_TIME_MS,
    retry: false,
  });

  const rating: RatingStatsResponse | undefined = ratingEnvelopeQuery.data?.result;
  const industry: IndustryStatsResponse | undefined = industryEnvelopeQuery.data?.result;
  const topRating = topRatingItem(rating?.items);
  const topIndustry = industry?.items?.[0] ?? null;
  const ytmCoverage = counterpartyStats?.ytm_rate_coverage ?? rating?.ytm_rate_coverage;
  const couponCoverage = counterpartyStats?.coupon_rate_coverage;
  const policy = rateCoveragePolicyLabel(ytmCoverage?.policy ?? couponCoverage?.policy);
  const dateCoverage = counterpartyStats?.num_days ?? rating?.num_days ?? industry?.num_days;
  const ytmParts = coverageQualityDisplay(ytmCoverage);
  const couponParts = coverageQualityDisplay(couponCoverage);

  /* 格子统一「标签/主值/小注」三段节奏（与 KPI 带同构），长句不再挤进主值。 */
  const qualityItems: Array<{ label: string; value: string; note?: string; title?: string }> = [
    { label: "日期覆盖", value: dateCoverage != null ? `${dateCoverage} 天` : EM_DASH },
    { label: "CR10", value: counterpartyStats?.cr10_ratio ?? EM_DASH },
    {
      label: "YTM 覆盖",
      value: ytmParts.value,
      note: ytmParts.note,
      title: ytmCoverage ? `已覆盖 ${formatAmountYi(ytmCoverage.covered_amount)}` : undefined,
    },
    {
      label: "票息覆盖",
      value: couponParts.value,
      note: couponParts.note,
      title: couponCoverage
        ? `已覆盖 ${formatAmountYi(couponCoverage.covered_amount)}`
        : undefined,
    },
    {
      label: "最高评级集中",
      value: topRating ? `${topRating.rating} / ${formatPercentValue(topRating.percentage)}` : EM_DASH,
    },
    {
      label: "最高行业集中",
      value: topIndustry
        ? `${topIndustry.industry} / ${formatPercentValue(topIndustry.percentage)}`
        : EM_DASH,
    },
  ];

  return (
    <div className="positions-view__panel">
      <h3 className="positions-view__panel-title">质量与集中度</h3>
      <div className="positions-view__quality-grid">
        {qualityItems.map((item) => (
          <div key={item.label} className="positions-view__quality-item" title={item.title}>
            <span className="positions-view__quality-label">{item.label}</span>
            <span className="positions-view__quality-value">{item.value}</span>
            {item.note ? (
              <span className="positions-view__quality-item-note" title={item.note}>
                {item.note}
              </span>
            ) : null}
          </div>
        ))}
      </div>
      {/* 来源/规则版本哈希不再入带底（与证据区重复且必然截断）；只留口径一句。 */}
      <p className="positions-view__quality-note">口径：{policy}</p>
    </div>
  );
}

/**
 * 03 授信主体与质量：客户搜索 + 授信主体 Top50 表（点击下钻）+ 质量与集中度面板。
 * 搜索只过滤本区客户表，不回写查询参数。
 */
export default function PositionsBondsConcentrationSection({
  startDate,
  endDate,
  subType,
  stats,
  statsLoading,
  searchText,
  onSearchTextChange,
  onCustomerOpen,
}: {
  startDate: string | null;
  endDate: string | null;
  subType: string | null;
  stats: CounterpartyStatsResponse | undefined;
  statsLoading: boolean;
  searchText: string;
  onSearchTextChange: (next: string) => void;
  onCustomerOpen: (customerName: string) => void;
}) {
  const filteredItems = useMemo(() => {
    const items = stats?.items ?? [];
    const q = searchText.trim();
    if (!q) {
      return items;
    }
    return items.filter((x) => x.customer_name.includes(q));
  }, [stats?.items, searchText]);

  const dataSource = useMemo<CounterpartyRow[]>(
    () =>
      filteredItems.map((row) => ({
        key: row.customer_name,
        ...row,
      })),
    [filteredItems],
  );

  /*
   * 垂直结构：质量六格横带在上、授信主体全宽表在下。左右分栏会让右栏
   * 在长表旁边留出大段裸空白（DESIGN.md §5 反模式），横带 + 全宽表更整。
   */
  return (
    <div className="positions-view__stack">
      <PositionsQualityPanel
        startDate={startDate}
        endDate={endDate}
        subType={subType}
        counterpartyStats={stats}
      />

      <div className="positions-view__panel">
        <div className="positions-view__panel-head">
          <h3 className="positions-view__panel-title">授信主体</h3>
          <span className="positions-view__panel-hint">Top 50，点击行下钻客户明细</span>
        </div>
        <label className="positions-view__field">
          <span className="positions-view__field-label">客户搜索</span>
          <Input
            className="positions-view__search-input"
            placeholder="输入客户名称…"
            value={searchText}
            onChange={(e) => onSearchTextChange(e.target.value)}
          />
        </label>
        {statsLoading ? (
          <div className="positions-view__table-state positions-view__table-state--loading">
            <Spin />
          </div>
        ) : stats && filteredItems.length > 0 ? (
          <Table
            size="small"
            className="positions-view__table positions-view__table--clickable"
            pagination={false}
            scroll={{ x: "max-content" }}
            dataSource={dataSource}
            onRow={(record) => ({
              onClick: () => onCustomerOpen(record.customer_name),
            })}
            columns={BONDS_COUNTERPARTY_COLUMNS}
          />
        ) : (
          <p className="positions-view__table-state">暂无数据</p>
        )}
      </div>
    </div>
  );
}
