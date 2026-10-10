import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Tabs } from "antd";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/clientContext";
import type { BondPositionItem, InterbankPositionItem } from "../../../api/contracts";
import { FilterBar } from "../../../components/FilterBar";
import {
  KpiStrip,
  SectionHead,
  StateSurface,
  StateSurfaceQuotaProvider,
  type KpiCell,
  type SectionState,
  type SurfaceStatus,
} from "../../../components/layout";
import type { LabeledValue } from "../../../pageModel";
import {
  buildPositionsBondsKpiBand,
  buildPositionsCaliberItems,
  buildPositionsFirstScreenStatus,
  buildPositionsInterbankKpiBand,
  buildPositionsPrimaryListTableState,
  normalizePositionsPrimaryListEnvelope,
  POSITIONS_QUERY_STALE_TIME_MS,
  type PositionsTabKey,
} from "../model/positionsPageModel";
import CustomerDetailModal from "./CustomerDetailModal";
import PositionsBondsConcentrationSection from "./PositionsBondsConcentrationSection";
import PositionsBondsDistributionSection from "./PositionsBondsDistributionSection";
import PositionsBondsWorkspaceSection from "./PositionsBondsWorkspaceSection";
import PositionsEvidenceSection from "./PositionsEvidenceSection";
import PositionsInterbankSplitSection from "./PositionsInterbankSplitSection";
import PositionsInterbankWorkspaceSection, {
  type InterbankDirectionFilter,
} from "./PositionsInterbankWorkspaceSection";
import "./PositionsView.css";

const PAGE_SIZE = 20;

/** 六格横带：≥1281 一行六格，1281 以下三格，720 以下折两格。 */
const KPI_COLS = { base: 2, md: 3, lg: 3, xl: 6 } as const;

/**
 * 首屏状态条三档（antd Alert 的 error / warning / info）→ 原语五态。
 * 模型里 `info` 只产出「暂无可用报告日 / 当前报告日暂无数据」两句，是真空态；
 * `warning` 只产出「回退到最近可用快照 / 数据可能偏旧」，是过期态。两档在原语里
 * 分别是中性收缩框与琥珀状态行，与迁移前 Alert 的 info 蓝 / warning 琥珀同档。
 */
const FIRST_SCREEN_STATUS: Record<"error" | "warning" | "info", SurfaceStatus> = {
  error: "error",
  warning: "stale",
  info: "empty",
};

/**
 * 分区头状态位：loading/error/empty 三态露出一句话，ready 返回 null。
 * 文案与迁移前 `PositionsSectionLead` 逐字一致，只是渲染换成原语。
 */
function positionsSectionState(
  query: { isLoading: boolean; isError: boolean },
  options?: { isEmpty?: boolean; emptyLabel?: string },
): SectionState {
  if (query.isLoading) {
    return { label: "读取中", tone: "loading" };
  }
  if (query.isError) {
    return { label: "读取失败", tone: "error" };
  }
  if (options?.isEmpty) {
    return { label: options.emptyLabel ?? "暂无数据", tone: "empty" };
  }
  return null;
}

/**
 * `LabeledValue` → 原语格。`status: "loading"` 原来只是把主值染灰，横带整体
 * 在读时改由 KpiStrip 的骨架档表达，格级 status 不再需要落到样式上。
 */
function toKpiCells(items: LabeledValue[]): KpiCell[] {
  return items.map((item) => {
    const amount = item.value.match(/^(.*) (亿元|万亿元|户)$/u);
    return {
      key: item.key,
      label: item.label,
      value: amount?.[1] ?? item.value,
      unit: amount ? ` ${amount[2]}` : undefined,
      note: item.note ?? null,
    };
  });
}

export default function PositionsView() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const explicitReportDate = searchParams.get("report_date")?.trim() || "";

  const datesQuery = useQuery({
    queryKey: ["positions", "balance-analysis-dates", client.mode],
    queryFn: () => client.getBalanceAnalysisDates(),
    staleTime: POSITIONS_QUERY_STALE_TIME_MS,
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

  const [tab, setTab] = useState<PositionsTabKey>("bonds");
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

  const rangeError = rangeTouched && (!rangeFrom || !rangeTo)
    ? "请补全区间起止日期，区间统计暂不查询。"
    : rangeFrom && rangeTo && rangeFrom > rangeTo
      ? "区间起始日期不能晚于结束日期，请调整后查看区间统计。"
      : null;
  // 无效区间不进入任何区间查询，包括下方评级、行业和质量分布。
  const startDate = rangeError ? null : rangeFrom.trim() || null;
  const endDate = rangeError ? null : rangeTo.trim() || null;

  const [selectedSubType, setSelectedSubType] = useState("");
  const [selectedProductType, setSelectedProductType] = useState("");
  const [direction, setDirection] = useState<InterbankDirectionFilter>("ALL");
  const [searchText, setSearchText] = useState("");
  const [page, setPage] = useState(1);

  const [customerModalOpen, setCustomerModalOpen] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState<string | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);

  const handleTabChange = (nextTab: PositionsTabKey) => {
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

  /** 分区 Select 已把「全部」哨兵归一成空串，这里只重置分页并落状态。 */
  const handleBondSubTypeChange = (nextSubType: string) => {
    setPage(1);
    setSelectedSubType(nextSubType);
  };

  const handleInterbankProductTypeChange = (nextProductType: string) => {
    setPage(1);
    setSelectedProductType(nextProductType);
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
    staleTime: POSITIONS_QUERY_STALE_TIME_MS,
    retry: false,
  });

  const interbankProductTypesQuery = useQuery({
    queryKey: ["positions", "interbank-product-types", client.mode, reportDate],
    queryFn: async () => {
      const envelope = await client.getPositionsInterbankProductTypes(reportDate || null);
      return envelope.result.product_types;
    },
    enabled: tab === "interbank" && Boolean(reportDate),
    staleTime: POSITIONS_QUERY_STALE_TIME_MS,
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
        // enabled 守卫保证 reportDate 非空；后端 report_date 为必填 Query 参数。
        reportDate,
        subType: selectedSubType || null,
        page,
        pageSize: PAGE_SIZE,
        includeIssued: false,
      }),
    enabled: tab === "bonds" && Boolean(reportDate),
    staleTime: POSITIONS_QUERY_STALE_TIME_MS,
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
        // enabled 守卫保证 reportDate 非空；后端 report_date 为必填 Query 参数。
        reportDate,
        productType: selectedProductType || null,
        direction,
        page,
        pageSize: PAGE_SIZE,
      }),
    enabled: tab === "interbank" && Boolean(reportDate),
    staleTime: POSITIONS_QUERY_STALE_TIME_MS,
    retry: false,
  });

  /*
   * 聚合信封保留整只 envelope：result 供 KPI 读数，result_meta 供证据区。
   * queryKey 与拆信封时期逐字一致。
   */
  const bondsCpQuery = useQuery({
    queryKey: ["positions", "cp-bonds", client.mode, startDate, endDate, selectedSubType],
    queryFn: () =>
      client.getPositionsCounterpartyBonds({
        startDate: startDate!,
        endDate: endDate!,
        subType: selectedSubType || null,
        topN: 50,
        page: 1,
        pageSize: 50,
      }),
    enabled: tab === "bonds" && Boolean(startDate && endDate),
    staleTime: POSITIONS_QUERY_STALE_TIME_MS,
    retry: false,
  });

  const interbankSplitQuery = useQuery({
    queryKey: ["positions", "cp-interbank-split", client.mode, startDate, endDate, selectedProductType],
    queryFn: () =>
      client.getPositionsCounterpartyInterbankSplit({
        startDate: startDate!,
        endDate: endDate!,
        productType: selectedProductType || null,
        topN: 50,
      }),
    enabled: tab === "interbank" && Boolean(startDate && endDate),
    staleTime: POSITIONS_QUERY_STALE_TIME_MS,
    retry: false,
  });

  const bondsCp = bondsCpQuery.data?.result;
  const interbankCpSplit = interbankSplitQuery.data?.result;
  const bondsListEnvelope = normalizePositionsPrimaryListEnvelope<BondPositionItem>(
    bondsListQuery.data,
  );
  const interbankListEnvelope = normalizePositionsPrimaryListEnvelope<InterbankPositionItem>(
    interbankListQuery.data,
  );
  const bondsList = bondsListEnvelope?.result;
  const interbankList = interbankListEnvelope?.result;

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
  const firstScreenStatus = buildPositionsFirstScreenStatus({
    tab,
    datesError: datesBlockingError,
    datesEmpty,
    listError,
    listTableState,
    meta: currentListEnvelope?.result_meta,
  });

  const kpiItems = useMemo(
    () =>
      tab === "bonds"
        ? buildPositionsBondsKpiBand({ stats: bondsCp, loading: bondsCpQuery.isLoading })
        : buildPositionsInterbankKpiBand({
            split: interbankCpSplit,
            loading: interbankSplitQuery.isLoading,
          }),
    [tab, bondsCp, bondsCpQuery.isLoading, interbankCpSplit, interbankSplitQuery.isLoading],
  );

  const caliberItems = buildPositionsCaliberItems({
    tab,
    reportDate,
    startDate,
    endDate,
    scopeLabel: activeScopeLabel,
  });

  const aggregateQuery = tab === "bonds" ? bondsCpQuery : interbankSplitQuery;
  const listEvidenceMeta =
    tab === "bonds" ? bondsListQuery.data?.result_meta : interbankListQuery.data?.result_meta;
  const aggregateEvidenceMeta = aggregateQuery.data?.result_meta;
  const workspaceTabs = (
    <Tabs
      className="positions-view__tabs"
      activeKey={tab}
      onChange={(key) => handleTabChange(key as PositionsTabKey)}
      items={[
        { key: "bonds", label: "债券持仓" },
        { key: "interbank", label: "同业持仓" },
      ]}
    />
  );

  /*
   * 深色 owner 由外层 ThemedRouteBoundary 的 data-moss-theme="dark" 独占；
   * 页根只声明换肤 scope，重复声明 owner 会让深色路由校验判定出两个 owner。
   */
  return (
    <StateSurfaceQuotaProvider>
    <section
      className="positions-view theme-dh-api"
      data-testid="positions-page"
      data-moss-theme-scope="positions"
    >
      <header className="positions-view__header">
        <div className="positions-view__header-copy">
          <h1 data-testid="positions-page-title" className="positions-view__title">
            持仓透视
          </h1>
        </div>
        <span className="positions-view__mode-note">
          {client.mode === "real" ? "明细按报告日，指标按观察区间" : "本地演示数据"}
        </span>
      </header>

      <div data-testid="positions-filter-tray" className="positions-view__filter-tray">
        <FilterBar className="positions-view__filters">
          <label>
            <span className="positions-view__filters-label">报告日</span>
            <select
              aria-label="positions-report-date"
              className="positions-view__filters-control"
              value={reportDate}
              disabled={Boolean(explicitReportDate) || datesBlockingError}
              onChange={(event) => handleReportDateChange(event.target.value)}
            >
              {!reportDate ? <option value="">选择报告日</option> : null}
              {dateOptions.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="positions-view__filters-label">区间起</span>
            <input
              aria-label="持仓区间起始日期"
              className="positions-view__filters-control"
              type="date"
              value={rangeFrom}
              aria-invalid={Boolean(rangeError)}
              aria-describedby={rangeError ? "positions-range-error" : undefined}
              onChange={(e) => {
                setRangeTouched(true);
                setRangeFrom(e.target.value);
              }}
              disabled={!reportDate}
            />
          </label>
          <label>
            <span className="positions-view__filters-label">区间止</span>
            <input
              aria-label="持仓区间结束日期"
              className="positions-view__filters-control"
              type="date"
              value={rangeTo}
              aria-invalid={Boolean(rangeError)}
              aria-describedby={rangeError ? "positions-range-error" : undefined}
              onChange={(e) => {
                setRangeTouched(true);
                setRangeTo(e.target.value);
              }}
              disabled={!reportDate}
            />
          </label>
          {explicitReportDate ? (
            <p className="positions-view__filters-note">当前链接已限定报告日</p>
          ) : null}
          <button
            type="button"
            className="positions-view__refresh"
            data-testid="positions-refresh"
            onClick={() => {
              /* 失效本页全部只读查询（前缀 ["positions"]），仅活跃查询重发；
                 与 bond-dashboard 刷新钮同语义（绕过 5 分钟 staleTime）。 */
              void queryClient.invalidateQueries({ queryKey: ["positions"] });
            }}
          >
            刷新
          </button>
        </FilterBar>
        {rangeError ? (
          <p id="positions-range-error" className="positions-view__range-error" role="alert">
            {rangeError}
          </p>
        ) : null}
      </div>

      <section
        id="positions-section-verdict"
        className="positions-view__section"
        data-testid="positions-decision-hero"
      >
        {firstScreenStatus ? (
          <StateSurface
            testId="positions-data-state-alert"
            status={FIRST_SCREEN_STATUS[firstScreenStatus.type]}
            message={firstScreenStatus.message}
            reason={firstScreenStatus.description}
            density="compact"
            dedupeKey="positions-first-screen-availability"
          />
        ) : null}
        {/*
          * 不走 KpiStrip 的骨架档：模型在读取中已经返回带标签的 EM_DASH 占位格
          * （`kpiBandPlaceholders`），六格标签自始至终在位，切到骨架反而会让首屏
          * 标签消失一拍。格级 `status: "loading"` 原本只把主值染灰，属可放弃的
          * 细节（见报告「原语层缺口」）。
          */}
        <KpiStrip
          testId="positions-kpi-band"
          cells={toKpiCells(kpiItems)}
          cols={KPI_COLS}
          size="compact"
        />
        <p data-testid="positions-analysis-boundary" className="positions-view__candidate-boundary">
          明细与区间统计仅供分析，未经正式口径批准。
          <a href="#positions-section-evidence" onClick={() => setEvidenceOpen(true)}>
            查看口径依据
          </a>
        </p>
      </section>

      <section
        id="positions-section-workspace"
        className="positions-view__section"
        aria-label="持仓工作区"
      >
        {tab === "bonds" ? (
          <PositionsBondsWorkspaceSection
            tabs={workspaceTabs}
            reportDate={reportDate}
            subTypeValue={selectedSubType}
            subTypeOptions={bondSubTypesQuery.data}
            subTypeLoading={bondSubTypesQuery.isLoading}
            onSubTypeChange={handleBondSubTypeChange}
            listState={listTableState}
            items={bondsList?.items ?? []}
            total={currentList?.total}
            page={page}
            totalPages={totalPages}
            canPrev={canPrev}
            canNext={canNext}
            onPrevPage={() => setPage((p) => Math.max(1, p - 1))}
            onNextPage={() => setPage((p) => p + 1)}
          />
        ) : (
          <PositionsInterbankWorkspaceSection
            tabs={workspaceTabs}
            reportDate={reportDate}
            productTypeValue={selectedProductType}
            productTypeOptions={interbankProductTypesQuery.data}
            productTypeLoading={interbankProductTypesQuery.isLoading}
            onProductTypeChange={handleInterbankProductTypeChange}
            direction={direction}
            onDirectionChange={handleDirectionChange}
            listState={listTableState}
            items={interbankList?.items ?? []}
            total={currentList?.total}
            page={page}
            totalPages={totalPages}
            canPrev={canPrev}
            canNext={canNext}
            onPrevPage={() => setPage((p) => Math.max(1, p - 1))}
            onNextPage={() => setPage((p) => p + 1)}
          />
        )}
      </section>

      {tab === "bonds" ? (
        <section id="positions-section-concentration" className="positions-view__section">
          <SectionHead
            title="授信主体与质量"
            numbered={false}
            state={rangeError ? null : positionsSectionState(bondsCpQuery, {
              isEmpty: (bondsCp?.items.length ?? 0) === 0,
            })}
          />
          {rangeError ? (
            <StateSurface status="empty" message="请先修正观察区间，再查看授信主体统计。" />
          ) : (
            <PositionsBondsConcentrationSection
              startDate={startDate}
              endDate={endDate}
              subType={selectedSubType || null}
              stats={bondsCp}
              statsLoading={bondsCpQuery.isLoading}
              statsError={bondsCpQuery.isError}
              searchText={searchText}
              onSearchTextChange={setSearchText}
              onCustomerOpen={(customerName) => {
                setSelectedCustomer(customerName);
                setCustomerModalOpen(true);
              }}
            />
          )}
        </section>
      ) : (
        <section id="positions-section-split" className="positions-view__section">
          <SectionHead
            title="资产负债结构"
            numbered={false}
            state={rangeError ? null : positionsSectionState(interbankSplitQuery, {
              isEmpty:
                (interbankCpSplit?.asset_items.length ?? 0) === 0 &&
                (interbankCpSplit?.liability_items.length ?? 0) === 0,
            })}
          />
          {rangeError ? (
            <StateSurface status="empty" message="请先修正观察区间，再查看资产负债结构。" />
          ) : (
            <PositionsInterbankSplitSection
              split={interbankCpSplit}
              loading={interbankSplitQuery.isLoading}
              isError={interbankSplitQuery.isError}
              searchText={searchText}
              onSearchTextChange={setSearchText}
            />
          )}
        </section>
      )}

      {tab === "bonds" ? (
        <section id="positions-section-distribution" className="positions-view__section">
          <SectionHead title="评级与行业分布" numbered={false} />
          {rangeError ? (
            <StateSurface status="empty" message="请先修正观察区间，再查看评级与行业分布。" />
          ) : (
            <PositionsBondsDistributionSection
              startDate={startDate}
              endDate={endDate}
              subType={selectedSubType || null}
            />
          )}
        </section>
      ) : null}

      <section id="positions-section-evidence" className="positions-view__section">
        <PositionsEvidenceSection
          tab={tab}
          listMeta={listEvidenceMeta}
          aggregateMeta={aggregateEvidenceMeta}
          caliberItems={caliberItems}
          open={evidenceOpen}
          onOpenChange={setEvidenceOpen}
        />
      </section>

      <CustomerDetailModal
        open={customerModalOpen}
        onClose={() => setCustomerModalOpen(false)}
        customerName={selectedCustomer}
        reportDate={reportDate}
      />
    </section>
    </StateSurfaceQuotaProvider>
  );
}
