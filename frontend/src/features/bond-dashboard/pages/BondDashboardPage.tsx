import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Select } from "antd";
import { useLocation, useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import type { BondDashboardBundleSectionId } from "../../../api/contracts";
import {
  KpiStrip,
  SECTION_HEAD_STACK_CLASSNAME,
  SectionGrid,
  SectionHead,
  StateSurface,
  StateSurfaceQuotaProvider,
  type KpiCell,
  type SectionMetaField,
  type SurfaceStatus,
} from "../../../components/layout";
import { EM_DASH, type MetricTone } from "../../../pageModel";
import {
  BOND_DASHBOARD_PAGE_BUNDLE_SECTIONS,
  bondDashboardAssetSectionForGroup,
  selectBondDashboardBundleSection,
} from "../bondDashboardBundleModel";
import { type AssetGroupBy } from "../components/AssetStructurePie";
import { useBondDashboardBundleQuery } from "../hooks/useBondDashboardBundleQuery";
import {
  buildBondDashboardCaliberItems,
  buildBondDashboardKpiBand,
  buildBondDashboardScreenNotices,
  buildBondDashboardSectionStatusItems,
  buildDashboardConclusion,
  describeFirstScreenMetaFallback,
  type BondDashboardKpiCell,
  type BondDashboardScreenNotice,
} from "../model/bondDashboardPageModel";
import { bondBundleSectionState, bondSectionState, bondSectionStatus } from "../sectionStatus";
import BondStructureSection from "../sections/BondStructureSection";
import BusinessTypeSection from "../sections/BusinessTypeSection";
import EvidenceSection from "../sections/EvidenceSection";
import MaturityIndustrySection from "../sections/MaturityIndustrySection";
import PortfolioRiskSection from "../sections/PortfolioRiskSection";
import "./BondDashboardPage.css";

/**
 * notice key → 既有测试锚点：dates error 与 dates empty 两个状态块共用
 * `bond-dashboard-page-state`（互斥出现），与旧 antd Alert 时代逐字一致。
 */
const NOTICE_TEST_IDS: Record<BondDashboardScreenNotice["key"], string> = {
  "dates-error": "bond-dashboard-page-state",
  "dates-empty": "bond-dashboard-page-state",
  "bundle-error": "bond-dashboard-bundle-state",
  stale: "bond-dashboard-stale-banner",
};

/**
 * notice 三档 → 原语五态。原三档的页面私有配色（红描边 / panel-2 中性 / 琥珀描边）
 * 与 StateSurface 的 error / empty / stale 逐档同色，映射后页面不再自带状态色。
 */
const NOTICE_STATUS: Record<BondDashboardScreenNotice["kind"], SurfaceStatus> = {
  error: "error",
  info: "empty",
  warning: "stale",
};

/**
 * §6 全页状态配额的登记键：按「说的是哪个事实」而不是按 notice 实例登记，
 * dates 读取失败与无可用报告日说的是同一个事实（报告日不可用），共用一个键。
 */
const NOTICE_DEDUPE_KEYS: Record<BondDashboardScreenNotice["key"], string> = {
  "dates-error": "bond-dashboard-report-date-availability",
  "dates-empty": "bond-dashboard-report-date-availability",
  "bundle-error": "bond-dashboard-bundle-availability",
  stale: "bond-dashboard-first-screen-fallback",
};

/** 环比 tone 词表（页面语义）→ 原语 tone 词表（MetricTone）。 */
const KPI_DELTA_TONE: Record<BondDashboardKpiCell["momTone"], MetricTone> = {
  up: "positive",
  down: "negative",
  flat: "neutral",
  none: "neutral",
};

/** 4×2 单框横带；720 以下折 2 列（与重构前断点一致）。 */
const KPI_COLS = { base: 2, md: 4, lg: 4, xl: 4 } as const;

/** 结论块（hero 大数字 + 结论句双栏 + 18/20 内边距）的实测高度，用作占位下限。 */
const CONCLUSION_MIN_HEIGHT = 148;

function toKpiCells(cells: BondDashboardKpiCell[]): KpiCell[] {
  return cells.map((cell) => ({
    key: cell.key,
    label: cell.label,
    value: cell.value,
    unit: cell.unit,
    // 环比恒占一行（含缺值的「环比 —」），保持八格底部读数位对齐。
    delta: `环比 ${cell.mom ?? EM_DASH}`,
    deltaTone: KPI_DELTA_TONE[cell.momTone],
    note: cell.note ?? null,
  }));
}

/**
 * 口径行并入 01 区分区头 meta：模型给的是 "标签：值" 展示串，这里只做拆分，
 * "·" 配额与竖线分栏由 SectionHead 内部按字段数推导，页面无法违反 §7。
 */
function toCaliberMeta(items: string[]): SectionMetaField[] {
  return items.map((item) => {
    const separator = item.indexOf("：");
    return separator < 0
      ? { label: item, value: "" }
      : { label: item.slice(0, separator), value: item.slice(separator + 1) };
  });
}

/**
 * notice 渲染：empty 档走 StateSurface 的收缩消息框（§5），该分支按设计不消费
 * children，所以描述文案走 reason；error / stale 档走行内状态行 + 内容位。
 */
function NoticeSurface({ notice }: { notice: BondDashboardScreenNotice }) {
  const status = NOTICE_STATUS[notice.kind];
  const testId = NOTICE_TEST_IDS[notice.key];
  const dedupeKey = NOTICE_DEDUPE_KEYS[notice.key];

  if (status === "empty") {
    return (
      <StateSurface
        testId={testId}
        status={status}
        message={notice.title}
        reason={notice.description}
        dedupeKey={dedupeKey}
      />
    );
  }
  return (
    <StateSurface testId={testId} status={status} message={notice.title} dedupeKey={dedupeKey}>
      {notice.description}
    </StateSurface>
  );
}

export default function BondDashboardPage() {
  const client = useApiClient();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  // 深链（如组合首页「去债券总览复核」）可携带 report_date；仅当该值出现在
  // 可用报告日集合中才采用，非法/伪参数回退最新日，三态处理保持不变。
  const requestedReportDate = searchParams.get("report_date")?.trim() ?? "";
  const [reportDate, setReportDate] = useState<string | null>(null);
  const [assetGroupBy, setAssetGroupBy] = useState<AssetGroupBy>("bond_type");

  const datesQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "dates"],
    queryFn: () => client.getBondDashboardDates(),
  });

  useEffect(() => {
    const dates = datesQuery.data?.result.report_dates;
    if (reportDate === null && dates && dates.length > 0) {
      setReportDate(
        requestedReportDate && dates.includes(requestedReportDate)
          ? requestedReportDate
          : dates[0],
      );
    }
  }, [datesQuery.data, reportDate, requestedReportDate]);

  // react-router 数据路由不会自动滚到 hash 锚点；挂载后对分区 id 做一次定位。
  useEffect(() => {
    const anchorId = location.hash.startsWith("#") ? location.hash.slice(1) : "";
    if (!anchorId) return;
    document.getElementById(anchorId)?.scrollIntoView?.({ block: "start" });
  }, [location.hash]);

  const rd = reportDate ?? "";

  const bundleQuery = useBondDashboardBundleQuery(client, rd || null, BOND_DASHBOARD_PAGE_BUNDLE_SECTIONS, {
    enabled: Boolean(rd),
    industryTopN: 10,
  });
  const bundleLoading = bundleQuery.isLoading;
  const bundleError = bundleQuery.isError;

  const headlineEnvelope = selectBondDashboardBundleSection(bundleQuery.data, "headline-kpis");
  const riskEnvelope = selectBondDashboardBundleSection(bundleQuery.data, "risk-indicators");
  const assetEnvelope = selectBondDashboardBundleSection(
    bundleQuery.data,
    bondDashboardAssetSectionForGroup(assetGroupBy),
  );
  const ratingEnvelope = selectBondDashboardBundleSection(bundleQuery.data, "asset-structure-rating");
  const tenorEnvelope = selectBondDashboardBundleSection(
    bundleQuery.data,
    "asset-structure-tenor-bucket",
  );
  const yieldEnvelope = selectBondDashboardBundleSection(bundleQuery.data, "yield-distribution");
  const portfolioEnvelope = selectBondDashboardBundleSection(bundleQuery.data, "portfolio-comparison");
  const spreadEnvelope = selectBondDashboardBundleSection(bundleQuery.data, "spread-analysis");
  const maturityEnvelope = selectBondDashboardBundleSection(bundleQuery.data, "maturity-structure");
  const industryEnvelope = selectBondDashboardBundleSection(bundleQuery.data, "industry-distribution");
  const businessTypeEnvelope = selectBondDashboardBundleSection(
    bundleQuery.data,
    "business-type-metrics",
  );

  const dateOptions = datesQuery.data?.result.report_dates ?? [];
  const datesEmpty = !datesQuery.isLoading && !datesQuery.isError && dateOptions.length === 0;
  /*
   * 报告日终态不可用且尚未选定报告日：bundle 查询 enabled=false，不会有请求在途。
   * rd 已落地（如刷新时 dates 二次失败）不算阻断，bundle 仍按自身状态呈现。
   */
  const reportDateUnavailable = !rd && (datesQuery.isError || datesEmpty);

  /*
   * 分区级读取状态：bundle 已经按分区返回 section_statuses / failed_sections
   * （06 区证据披露一直在用），这里把同一份信息接到各数据块上，让「请求已结束但
   * 该分区没回数」露出失败而不是继续显示骨架（DESIGN.md §6 不能静默吞态）。
   */
  const sectionState = (section: BondDashboardBundleSectionId) =>
    bondBundleSectionState({ bundle: bundleQuery.data, bundleError, reportDateUnavailable, section });
  const assetState = sectionState(bondDashboardAssetSectionForGroup(assetGroupBy));
  const ratingState = sectionState("asset-structure-rating");
  const tenorState = sectionState("asset-structure-tenor-bucket");
  const yieldState = sectionState("yield-distribution");
  const portfolioState = sectionState("portfolio-comparison");
  const spreadState = sectionState("spread-analysis");
  const maturityState = sectionState("maturity-structure");
  const industryState = sectionState("industry-distribution");
  const riskState = sectionState("risk-indicators");
  const businessTypeState = sectionState("business-type-metrics");

  const firstScreenFallbackNotices = [
    describeFirstScreenMetaFallback("首屏指标", headlineEnvelope?.result_meta, rd || null),
    describeFirstScreenMetaFallback("风险指标", riskEnvelope?.result_meta, rd || null),
  ].filter((notice): notice is string => notice !== null);
  const notices = buildBondDashboardScreenNotices({
    datesError: datesQuery.isError,
    datesEmpty,
    bundleError,
    fallbackNotices: firstScreenFallbackNotices,
  });
  const conclusion =
    headlineEnvelope?.result && riskEnvelope?.result
      ? buildDashboardConclusion(headlineEnvelope.result, riskEnvelope.result)
      : null;
  const kpiBand = buildBondDashboardKpiBand({
    headline: headlineEnvelope?.result,
    loading: bundleLoading,
  });
  const kpiCells = toKpiCells(kpiBand.cells);
  /*
   * 结论 hero 大数字（FR-6 / 方向 A）：复用 KPI 带里已格式化的持仓规模格，
   * 不新增数据链路；缺值时整栏不渲染（不放大 EM_DASH 破折号）。
   */
  const heroScaleCell = kpiBand.cells.find((cell) => cell.key === "total_market_value");
  const showConclusionHero = Boolean(heroScaleCell && heroScaleCell.value !== EM_DASH);
  const caliberItems = buildBondDashboardCaliberItems({
    reportDate: rd,
    prevReportDate: headlineEnvelope?.result.prev_report_date ?? null,
    dataSource: datesQuery.data?.data_source,
    dataBuiltAt: headlineEnvelope?.result_meta?.data_built_at,
  });
  const sectionStatusItems = buildBondDashboardSectionStatusItems(bundleQuery.data);
  /*
   * KPI 横带渲染门：首屏未 settle（dates 在途、默认报告日尚未落地、bundle 在途）
   * 时渲染无 testid 的骨架横带，与旧 HeadlineKpis「无数据不出格子」的时序语义一致
   * （测试 findByTestId 等待的是带真实数据的格子）；占位 EM_DASH 格只在终态披露
   * （dates 失败 / 无可用报告日 / bundle 失败或分区缺失）。骨架用的是同一个
   * KpiStrip（同格数、同 min-height），因此 settle 前后不再有横带高度跳变。
   */
  const firstScreenSettled =
    datesQuery.isError || datesEmpty || bundleQuery.isError || bundleQuery.isSuccess;
  const kpiBandPending = !firstScreenSettled;
  const verdictStatus = bondSectionStatus({
    loading: datesQuery.isLoading || bundleLoading,
    error: datesQuery.isError || bundleError,
    empty: datesEmpty,
  });

  /*
   * 深色 owner 由外层 ThemedRouteBoundary 的 data-moss-theme="dark" 承担；
   * 页根只声明主题 scope，重复声明 owner 会让深色路由校验判定出两个 owner。
   */
  return (
    <StateSurfaceQuotaProvider>
      <div
        data-testid="bond-dashboard-page"
        data-moss-theme-scope="bond-dashboard"
        className="bond-dashboard-page theme-dh-api"
      >
        <header className="bond-dashboard-page__header">
          <div className="bond-dashboard-page__header-copy">
            <h1 className="bond-dashboard-page__title">债券总览</h1>
            <p className="bond-dashboard-page__subtitle">
              正式债券分析事实的组合读数：规模、收益率、久期与结构分布。
            </p>
          </div>
          <span
            className={`bond-dashboard-page__mode-badge bond-dashboard-page__mode-badge--${
              client.mode === "real" ? "real" : "mock"
            }`}
          >
            {client.mode === "real" ? "真实 API 只读链路" : "演示数据链路"}
          </span>
        </header>

        <div className="bond-dashboard-page__toolbar" data-testid="bond-dashboard-toolbar">
          <label className="bond-dashboard-page__toolbar-field">
            <span className="bond-dashboard-page__toolbar-label">报告日</span>
            <Select
              aria-label="bond-dashboard-report-date"
              className="bond-dashboard-page__report-select"
              value={reportDate ?? undefined}
              loading={datesQuery.isLoading}
              disabled={datesQuery.isLoading || datesQuery.isError || dateOptions.length === 0}
              options={dateOptions.map((date) => ({ label: date, value: date }))}
              onChange={(value) => setReportDate(value)}
              placeholder="选择日期"
              getPopupContainer={(t) => t.parentElement ?? document.body}
            />
          </label>
          <button
            type="button"
            className="bond-dashboard-page__refresh"
            onClick={() => {
              void datesQuery.refetch();
              // refetch 会绕过 enabled 门；报告日未定时不发空参 bundle 请求。
              if (rd) void bundleQuery.refetch();
            }}
          >
            刷新
          </button>
        </div>

        {/* 一个 stack 容器 = 一个独立编号域；序号由 SectionHead 的 CSS counter 生成。 */}
        <div className={SECTION_HEAD_STACK_CLASSNAME}>
          {/* 分区间距 24px（FR-6 呼吸放宽）；分区内部仍走各自的 12/16 紧凑档。 */}
          <SectionGrid gap={24}>
            {/* 01 当日结论：readiness 锚点（bond-dashboard-conclusion）必须留在本文件。 */}
            <section className="bond-dashboard-section" id="bond-dashboard-section-verdict">
              {/* 口径行从 KPI 带下方并入分区头 meta，旧 `bond-dashboard-caliber`
                  锚点随之落到分区头上，口径文案仍在该锚点的文本内。 */}
              <SectionHead
                testId="bond-dashboard-caliber"
                title="当日结论"
                state={bondSectionState(verdictStatus)}
                meta={toCaliberMeta(caliberItems)}
              />
              <SectionGrid gap={12}>
                {notices.map((notice) => (
                  <NoticeSurface key={notice.key} notice={notice} />
                ))}
                {!datesEmpty && conclusion ? (
                  <section
                    data-testid="bond-dashboard-conclusion"
                    className="bond-dashboard-page__conclusion"
                  >
                    {showConclusionHero && heroScaleCell ? (
                      <div className="bond-dashboard-page__conclusion-hero">
                        <span className="bond-dashboard-page__conclusion-hero-label">
                          {heroScaleCell.label}
                        </span>
                        <div className="bond-dashboard-page__conclusion-hero-value-row">
                          <strong className="bond-dashboard-page__conclusion-hero-value">
                            {heroScaleCell.value}
                          </strong>
                          {heroScaleCell.unit ? (
                            <span className="bond-dashboard-page__conclusion-hero-unit">
                              {heroScaleCell.unit}
                            </span>
                          ) : null}
                        </div>
                        {heroScaleCell.mom ? (
                          <span
                            className="bond-dashboard-page__conclusion-hero-delta"
                            data-tone={KPI_DELTA_TONE[heroScaleCell.momTone]}
                          >
                            环比 {heroScaleCell.mom}
                          </span>
                        ) : null}
                      </div>
                    ) : null}
                    <div className="bond-dashboard-page__conclusion-copy">
                      <span className="bond-dashboard-page__conclusion-kicker">{conclusion.title}</span>
                      <div className="bond-dashboard-page__conclusion-body">{conclusion.body}</div>
                      <div className="bond-dashboard-page__conclusion-detail">{conclusion.detail}</div>
                    </div>
                  </section>
                ) : !datesEmpty && kpiBandPending ? (
                  /* 结论块占位：结论到达时会把下方 KPI 横带整体下推，占位按结论块
                     实测高度撑住这段版面（DESIGN.md §11.10）。 */
                  <StateSurface status="loading" minHeight={CONCLUSION_MIN_HEIGHT} />
                ) : null}
                {kpiBandPending ? (
                  <KpiStrip cells={kpiCells} cols={KPI_COLS} size="hero" loading />
                ) : (
                  <div data-testid="bond-dashboard-headline-kpis">
                    <KpiStrip
                      testId="bond-dashboard-kpi"
                      cells={kpiCells}
                      cols={KPI_COLS}
                      size="hero"
                      loading={kpiBand.loading}
                    />
                  </div>
                )}
              </SectionGrid>
            </section>

            {/* 02-06 编号分区：分区帧与分区头由各 section 文件渲染。 */}
            <BondStructureSection
              assetData={assetEnvelope?.result}
              assetState={assetState}
              groupBy={assetGroupBy}
              onGroupByChange={setAssetGroupBy}
              ratingData={ratingEnvelope?.result}
              ratingState={ratingState}
              yieldData={yieldEnvelope?.result}
              tenorData={tenorEnvelope?.result}
              yieldState={yieldState}
              tenorState={tenorState}
            />
            <MaturityIndustrySection
              maturityData={maturityEnvelope?.result}
              maturityState={maturityState}
              industryData={industryEnvelope?.result}
              industryState={industryState}
            />
            <PortfolioRiskSection
              portfolioData={portfolioEnvelope?.result}
              portfolioState={portfolioState}
              headline={headlineEnvelope?.result}
              spreadData={spreadEnvelope?.result}
              spreadState={spreadState}
              riskData={riskEnvelope?.result}
              riskState={riskState}
            />
            <BusinessTypeSection
              items={businessTypeEnvelope?.result.items}
              state={businessTypeState}
            />
            <EvidenceSection
              datesMeta={datesQuery.data?.result_meta}
              bundleMeta={bundleQuery.data?.result_meta}
              headlineMeta={headlineEnvelope?.result_meta}
              riskMeta={riskEnvelope?.result_meta}
              datesEmpty={datesEmpty}
              sectionStatusItems={sectionStatusItems}
            />
          </SectionGrid>
        </div>
      </div>
    </StateSurfaceQuotaProvider>
  );
}
