import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Tabs } from "antd";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import type { BondPositionItem, InterbankPositionItem } from "../../../api/contracts";
import { FilterBar } from "../../../components/FilterBar";
import {
  buildPositionsBondsKpiBand,
  buildPositionsCaliberItems,
  buildPositionsFirstScreenStatus,
  buildPositionsInterbankKpiBand,
  buildPositionsPrimaryListTableState,
  normalizePositionsPrimaryListEnvelope,
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
import PositionsKpiBand from "./PositionsKpiBand";
import PositionsSectionLead, { type PositionsSectionState } from "./PositionsSectionLead";
import "./PositionsView.css";

const PAGE_SIZE = 20;

/** 分区头状态位：loading/error/empty 三态露出一句话，ready 返回 null。 */
function positionsSectionState(
  query: { isLoading: boolean; isError: boolean },
  options?: { isEmpty?: boolean; emptyLabel?: string },
): PositionsSectionState {
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
  const activePeerFilterLabel =
    tab === "bonds"
      ? searchText || "未输入客户"
      : `${direction === "ALL" ? "全部方向" : direction === "Asset" ? "资产端" : "负债端"} / ${
          searchText || "未输入对手方"
        }`;
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
    peerFilterLabel: activePeerFilterLabel,
  });

  const aggregateQuery = tab === "bonds" ? bondsCpQuery : interbankSplitQuery;
  const listEvidenceMeta =
    tab === "bonds" ? bondsListQuery.data?.result_meta : interbankListQuery.data?.result_meta;
  const aggregateEvidenceMeta = aggregateQuery.data?.result_meta;

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
      <header className="positions-view__header">
        <div className="positions-view__header-copy">
          <h1 data-testid="positions-page-title" className="positions-view__title">
            持仓透视
          </h1>
          <p className="positions-view__subtitle">
            先锁定报告日和观察区间，再判断债券评级收益率、行业分布和客户集中度是否需要下钻。
          </p>
        </div>
        <span
          className={`positions-view__mode-badge positions-view__mode-badge--${
            client.mode === "real" ? "real" : "mock"
          }`}
        >
          {client.mode === "real" ? "真实只读链路" : "本地演示数据"}
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
              onChange={(e) => {
                setRangeTouched(true);
                setRangeTo(e.target.value);
              }}
              disabled={!reportDate}
            />
          </label>
          {explicitReportDate ? (
            <p className="positions-view__filters-note">已由地址栏报告日参数固定</p>
          ) : null}
        </FilterBar>
      </div>

      <section
        id="positions-section-verdict"
        className="positions-view__section"
        data-testid="positions-decision-hero"
      >
        <PositionsSectionLead title="当日结论" />
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
        <PositionsKpiBand testId="positions-kpi-band" items={kpiItems} />
        <div data-testid="positions-data-status" className="positions-view__caliber">
          {caliberItems.map((item, index) => (
            <span key={`${index}-${item}`} className="positions-view__caliber-item">
              {item}
            </span>
          ))}
        </div>
      </section>

      <section id="positions-section-workspace" className="positions-view__section">
        <PositionsSectionLead
          title="持仓工作区"
          actions={
            <Tabs
              className="positions-view__tabs"
              activeKey={tab}
              onChange={(k) => handleTabChange(k as PositionsTabKey)}
              items={[
                { key: "bonds", label: "债券持仓" },
                { key: "interbank", label: "同业持仓" },
              ]}
            />
          }
        />
        {tab === "bonds" ? (
          <PositionsBondsWorkspaceSection
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
            reportDate={reportDate}
            productTypeValue={selectedProductType}
            productTypeOptions={interbankProductTypesQuery.data}
            productTypeLoading={interbankProductTypesQuery.isLoading}
            onProductTypeChange={handleInterbankProductTypeChange}
            direction={direction}
            onDirectionChange={handleDirectionChange}
            filterOpen={interbankFilterOpen}
            onFilterOpenChange={setInterbankFilterOpen}
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
          <PositionsSectionLead
            title="授信主体与质量"
            state={positionsSectionState(bondsCpQuery, {
              isEmpty: (bondsCp?.items.length ?? 0) === 0,
            })}
          />
          <PositionsBondsConcentrationSection
            startDate={startDate}
            endDate={endDate}
            subType={selectedSubType || null}
            stats={bondsCp}
            statsLoading={bondsCpQuery.isLoading}
            searchText={searchText}
            onSearchTextChange={setSearchText}
            onCustomerOpen={(customerName) => {
              setSelectedCustomer(customerName);
              setCustomerModalOpen(true);
            }}
          />
        </section>
      ) : (
        <section id="positions-section-split" className="positions-view__section">
          <PositionsSectionLead
            title="资产负债结构"
            state={positionsSectionState(interbankSplitQuery, {
              isEmpty:
                (interbankCpSplit?.asset_items.length ?? 0) === 0 &&
                (interbankCpSplit?.liability_items.length ?? 0) === 0,
            })}
          />
          <PositionsInterbankSplitSection
            split={interbankCpSplit}
            loading={interbankSplitQuery.isLoading}
            searchText={searchText}
            onSearchTextChange={setSearchText}
          />
        </section>
      )}

      {tab === "bonds" ? (
        <section id="positions-section-distribution" className="positions-view__section">
          <PositionsSectionLead title="评级与行业分布" />
          <PositionsBondsDistributionSection
            startDate={startDate}
            endDate={endDate}
            subType={selectedSubType || null}
          />
        </section>
      ) : null}

      <section id="positions-section-evidence" className="positions-view__section">
        <PositionsSectionLead title="证据与口径" />
        <PositionsEvidenceSection
          tab={tab}
          listMeta={listEvidenceMeta}
          aggregateMeta={aggregateEvidenceMeta}
        />
      </section>

      <CustomerDetailModal
        open={customerModalOpen}
        onClose={() => setCustomerModalOpen(false)}
        customerName={selectedCustomer}
        reportDate={reportDate}
      />
    </section>
  );
}
