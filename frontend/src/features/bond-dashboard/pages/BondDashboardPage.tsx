import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Select } from "antd";
import { useLocation, useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import {
  BOND_DASHBOARD_PAGE_BUNDLE_SECTIONS,
  bondDashboardAssetSectionForGroup,
  selectBondDashboardBundleSection,
} from "../bondDashboardBundleModel";
import { type AssetGroupBy } from "../components/AssetStructurePie";
import BondDashboardKpiBand from "../components/BondDashboardKpiBand";
import BondDashboardSectionLead, {
  type BondDashboardSectionState,
} from "../components/BondDashboardSectionLead";
import { useBondDashboardBundleQuery } from "../hooks/useBondDashboardBundleQuery";
import {
  buildBondDashboardCaliberItems,
  buildBondDashboardKpiBand,
  buildBondDashboardScreenNotices,
  buildBondDashboardSectionStatusItems,
  buildDashboardConclusion,
  describeFirstScreenMetaFallback,
  type BondDashboardScreenNotice,
} from "../model/bondDashboardPageModel";
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

/** 01 区分区头状态位：loading/error/empty 三态露一句话，正常返回 null。 */
function verdictLeadState(
  loading: boolean,
  error: boolean,
  isEmpty: boolean,
): BondDashboardSectionState {
  if (loading) return { label: "读取中", tone: "loading" };
  if (error) return { label: "读取失败", tone: "error" };
  if (isEmpty) return { label: "暂无数据", tone: "empty" };
  return null;
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
  const caliberItems = buildBondDashboardCaliberItems({
    reportDate: rd,
    prevReportDate: headlineEnvelope?.result.prev_report_date ?? null,
    dataSource: datesQuery.data?.data_source,
  });
  const sectionStatusItems = buildBondDashboardSectionStatusItems(bundleQuery.data);
  /*
   * KPI 横带渲染门：首屏未 settle（dates 在途、默认报告日尚未落地、bundle 在途）
   * 时渲染无 testid 的载入块，与旧 HeadlineKpis「无数据不出格子」的时序语义一致
   * （测试 findByTestId 等待的是带真实数据的格子）；占位 EM_DASH 格只在终态披露
   * （dates 失败 / 无可用报告日 / bundle 失败或分区缺失）。
   */
  const firstScreenSettled =
    datesQuery.isError || datesEmpty || bundleQuery.isError || bundleQuery.isSuccess;
  const kpiBandPending = !firstScreenSettled;

  /*
   * 深色 owner 由外层 ThemedRouteBoundary 的 data-moss-theme="dark" 承担；
   * 页根只声明主题 scope，重复声明 owner 会让深色路由校验判定出两个 owner。
   */
  return (
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

      {/* 01 当日结论：readiness 锚点（bond-dashboard-conclusion）必须留在本文件。 */}
      <section className="bond-dashboard-section" id="bond-dashboard-section-verdict">
        <BondDashboardSectionLead
          title="当日结论"
          state={verdictLeadState(
            datesQuery.isLoading || bundleLoading,
            datesQuery.isError || bundleError,
            datesEmpty,
          )}
        />
        {notices.map((notice) => (
          <div
            key={notice.key}
            data-testid={NOTICE_TEST_IDS[notice.key]}
            role={notice.key === "stale" ? "status" : undefined}
            className={`bond-dashboard-notice bond-dashboard-notice--${notice.kind}`}
          >
            <strong className="bond-dashboard-notice__title">{notice.title}</strong>
            <span className="bond-dashboard-notice__description">{notice.description}</span>
          </div>
        ))}
        {!datesEmpty && conclusion ? (
          <section
            data-testid="bond-dashboard-conclusion"
            className="bond-dashboard-page__conclusion"
          >
            <span className="bond-dashboard-page__conclusion-kicker">{conclusion.title}</span>
            <div className="bond-dashboard-page__conclusion-body">{conclusion.body}</div>
            <div className="bond-dashboard-page__conclusion-detail">{conclusion.detail}</div>
          </section>
        ) : null}
        {kpiBandPending ? (
          <p className="bond-dashboard-page__surface bond-dashboard-page__surface--loading">
            载入中…
          </p>
        ) : (
          <BondDashboardKpiBand cells={kpiBand.cells} loading={kpiBand.loading} />
        )}
        <div className="bond-dashboard-page__caliber" data-testid="bond-dashboard-caliber">
          {caliberItems.map((item, index) => (
            <span key={`${index}-${item}`} className="bond-dashboard-page__caliber-item">
              {item}
            </span>
          ))}
        </div>
      </section>

      {/* 02-06 编号分区：分区帧与 lead 由各 section 文件渲染。 */}
      <BondStructureSection
        assetData={assetEnvelope?.result}
        assetLoading={bundleLoading}
        groupBy={assetGroupBy}
        onGroupByChange={setAssetGroupBy}
        ratingData={ratingEnvelope?.result}
        ratingLoading={bundleLoading}
        yieldData={yieldEnvelope?.result}
        tenorData={tenorEnvelope?.result}
        yieldLoading={bundleLoading}
        tenorLoading={bundleLoading}
      />
      <MaturityIndustrySection
        maturityData={maturityEnvelope?.result}
        maturityLoading={bundleLoading}
        industryData={industryEnvelope?.result}
        industryLoading={bundleLoading}
      />
      <PortfolioRiskSection
        portfolioData={portfolioEnvelope?.result}
        portfolioLoading={bundleLoading}
        headline={headlineEnvelope?.result}
        spreadData={spreadEnvelope?.result}
        spreadLoading={bundleLoading}
        riskData={riskEnvelope?.result}
        riskLoading={bundleLoading}
      />
      <BusinessTypeSection
        items={businessTypeEnvelope?.result.items}
        loading={bundleLoading}
        error={bundleError}
      />
      <EvidenceSection
        datesMeta={datesQuery.data?.result_meta}
        bundleMeta={bundleQuery.data?.result_meta}
        headlineMeta={headlineEnvelope?.result_meta}
        riskMeta={riskEnvelope?.result_meta}
        datesEmpty={datesEmpty}
        sectionStatusItems={sectionStatusItems}
      />
    </div>
  );
}
