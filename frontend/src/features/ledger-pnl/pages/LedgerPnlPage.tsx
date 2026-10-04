import { useEffect, useMemo, useRef, useState } from "react";
import { useIsFetching, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import { useDeferredSectionSeen } from "../../../hooks/useDeferredSectionSeen";
import { EM_DASH } from "../../../utils/format";
import { FilterBar } from "../../../components/FilterBar";
import { LedgerPnlAccountDetailDrawer } from "../components/LedgerPnlAccountDetailDrawer";
import { LedgerPnlAccountDetailSection } from "../components/LedgerPnlAccountDetailSection";
import { LedgerPnlAccountSummarySection } from "../components/LedgerPnlAccountSummarySection";
import { LedgerPnlAuditVerdict } from "../components/LedgerPnlAuditVerdict";
import { LedgerPnlCandidateFinancialIndicatorsPanel } from "../components/LedgerPnlCandidateFinancialIndicatorsPanel";
import { LedgerPnlFinancialIndicatorSummaryPanel } from "../components/LedgerPnlFinancialIndicatorSummaryPanel";
import { LedgerPnlMonthlyReconciliation } from "../components/LedgerPnlMonthlyReconciliation";
import { LedgerPnlSectionNav } from "../components/LedgerPnlSectionNav";
import { LedgerPnlSectionLead, LedgerSectionSkeleton } from "../components/LedgerPnlSectionPresentation";
import { LedgerPnlSummaryCards } from "../components/LedgerPnlSummaryCards";
import {
  LedgerPnlAnalysisWorkbench,
  type LedgerPnlContributorSelection,
} from "../components/LedgerPnlAnalysisWorkbench";
import { useLedgerPnlSectionNavigation } from "../hooks/useLedgerPnlSectionNavigation";
import type { LedgerFunctionalAuditProps } from "../models/ledgerPnlAuditModel";
import { ledgerSectionState, reportDateToMonth } from "../models/ledgerPnlDisplay";
import {
  LEDGER_PNL_CURRENCY_BASIS_OPTIONS,
  LEDGER_PNL_REPORT_DATE_SELECT_ID,
  LEDGER_PNL_SECTION_IDS,
  normalizeLedgerPnlCurrencyBasis,
} from "../models/ledgerPnlPageConstants";
import "./LedgerPnlPage.css";

export default function LedgerPnlPage() {
  const client = useApiClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const ledgerPnlFetchingCount = useIsFetching({ queryKey: ["ledger-pnl"] });
  const [selectedContributor, setSelectedContributor] = useState<LedgerPnlContributorSelection | null>(null);
  const [detailAccountFilter, setDetailAccountFilter] = useState<LedgerPnlContributorSelection | null>(null);
  const detailTableRef = useRef<HTMLDivElement>(null);
  const reportDateFromQuery = searchParams.get("report_date")?.trim() ?? "";
  const currencyFromQuery = searchParams.get("currency")?.trim() ?? "";
  const currency = normalizeLedgerPnlCurrencyBasis(currencyFromQuery);

  const datesQuery = useQuery({
    queryKey: ["ledger-pnl", "dates", client.mode],
    queryFn: () => client.getLedgerPnlDates(),
    retry: false,
  });

  const reportDates = useMemo(() => datesQuery.data?.result.dates ?? [], [datesQuery.data?.result.dates]);
  const selectedReportDate = reportDateFromQuery || reportDates[0] || "";

  const summaryQuery = useQuery({
    queryKey: ["ledger-pnl", "summary", client.mode, selectedReportDate, currency],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getLedgerPnlSummary(selectedReportDate, currency),
    retry: false,
  });

  const dataQuery = useQuery({
    queryKey: ["ledger-pnl", "data", client.mode, selectedReportDate, currency],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getLedgerPnlData(selectedReportDate, currency),
    retry: false,
  });

  const analysisQuery = useQuery({
    queryKey: ["ledger-pnl", "analysis", client.mode, selectedReportDate, currency],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getLedgerPnlAnalysis(selectedReportDate, currency),
    retry: false,
  });

  const monthlyAnalysisDatesQuery = useQuery({
    queryKey: ["ledger-pnl", "monthly-analysis", "dates", client.mode],
    queryFn: () => client.getLedgerPnlMonthlyAnalysisDates(),
    retry: false,
  });

  const summary = summaryQuery.data?.result;
  const locateContributorInDetail = (selection: LedgerPnlContributorSelection) => {
    setDetailAccountFilter(selection);
    detailTableRef.current?.scrollIntoView({ block: "start", inline: "nearest" });
    detailTableRef.current?.focus({ preventScroll: true });
  };
  const monthlyAnalysisMonths = monthlyAnalysisDatesQuery.data?.result.report_months ?? [];
  const requestedAnalysisMonth = reportDateToMonth(selectedReportDate);
  const selectedReportDateMissingFromDates =
    Boolean(selectedReportDate) &&
    !datesQuery.isLoading &&
    reportDates.length > 0 &&
    !reportDates.includes(selectedReportDate);
  const hasMatchingAnalysisMonth =
    Boolean(requestedAnalysisMonth) && monthlyAnalysisMonths.includes(requestedAnalysisMonth);
  const selectedAnalysisMonth = hasMatchingAnalysisMonth ? requestedAnalysisMonth : "";

  /*
   * 视口门控：三个重区块（经营指标 / 候选指标 / 对账与日均）进入视口才发起查询，
   * 首屏只保留 dates/summary/data/analysis 与轻量的月度日期清单。
   * 兜底延时取 0：jsdom（无 IntersectionObserver）里一个宏任务后即视为可见，
   * 现有页面级集成测试的 waitFor 足以覆盖，无需逐条改造。
   * seen 一旦为 true 不再回退，区块挂载后的行为与门控前完全一致。
   */
  const indicatorsSection = useDeferredSectionSeen<HTMLDivElement>(true, 0);
  const candidateSection = useDeferredSectionSeen<HTMLDivElement>(true, 0);
  const reconciliationSection = useDeferredSectionSeen<HTMLElement>(true, 0);

  const formalIndicatorSourceContractQuery = useQuery({
    queryKey: ["ledger-pnl", "formal-financial-indicators", client.mode, requestedAnalysisMonth],
    enabled: reconciliationSection.seen && Boolean(requestedAnalysisMonth),
    queryFn: () => client.getLedgerPnlFormalFinancialIndicators(requestedAnalysisMonth),
    retry: false,
  });

  const formalIndicatorRuleChecksQuery = useQuery({
    queryKey: ["ledger-pnl", "formal-indicator-rule-checks", client.mode, requestedAnalysisMonth],
    enabled: reconciliationSection.seen && Boolean(requestedAnalysisMonth),
    queryFn: () => client.getLedgerPnlFormalIndicatorRuleChecks(requestedAnalysisMonth),
    retry: false,
  });

  const monthlyAnalysisWorkbookQuery = useQuery({
    queryKey: ["ledger-pnl", "monthly-analysis", "workbook", client.mode, selectedAnalysisMonth],
    enabled: reconciliationSection.seen && hasMatchingAnalysisMonth,
    queryFn: () => client.getLedgerPnlMonthlyAnalysisWorkbook({ reportMonth: selectedAnalysisMonth }),
    retry: false,
  });

  const monthlyAnalysisWorkbook = monthlyAnalysisWorkbookQuery.data?.result;
  const formalIndicatorSourceContract = formalIndicatorSourceContractQuery.data?.result;

  const { sectionNavItems, wakeSectionsForNavigate } = useLedgerPnlSectionNavigation({
    indicatorsSection,
    candidateSection,
    reconciliationSection,
    ledgerPnlFetchingCount,
  });

  useEffect(() => {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("report_date");
    nextParams.delete("currency");
    if (selectedReportDate) {
      nextParams.set("report_date", selectedReportDate);
    }
    nextParams.set("currency", currency);

    const nextSearch = nextParams.toString();
    if (nextSearch !== searchParams.toString()) {
      setSearchParams(nextParams, { replace: true });
    }
  }, [currency, searchParams, selectedReportDate, setSearchParams]);

  /*
   * B1：LedgerFunctionalAuditStrip 的 props 只装一次，同时喂给经营结论卡的状态行
   * （复用其 tone 状态机得出的 title）与展开区里原样渲染的审计条本体。
   */
  const ledgerFunctionalAuditProps: LedgerFunctionalAuditProps = {
    selectedReportDate,
    selectedReportDateMissingFromDates,
    reportDates,
    datesMeta: datesQuery.data?.result_meta,
    analysisEnvelope: analysisQuery.data,
    analysisError: analysisQuery.error,
    requestedReportMonth: requestedAnalysisMonth,
    monthlyAnalysisWorkbook,
    monthlyAnalysisWorkbookMeta: monthlyAnalysisWorkbookQuery.data?.result_meta,
    formalIndicatorSourceContract,
    hasMatchingAnalysisMonth,
    isMonthlyAnalysisDatesLoading: monthlyAnalysisDatesQuery.isLoading,
    isMonthlyAnalysisDatesError: monthlyAnalysisDatesQuery.isError,
    isMonthlyAnalysisWorkbookLoading: monthlyAnalysisWorkbookQuery.isLoading,
    isMonthlyAnalysisWorkbookError: monthlyAnalysisWorkbookQuery.isError,
    isFormalContractLoading: formalIndicatorSourceContractQuery.isLoading,
    isFormalContractError: formalIndicatorSourceContractQuery.isError,
    isDatesLoading: datesQuery.isLoading,
    isDatesError: datesQuery.isError,
    isAnalysisLoading: analysisQuery.isLoading,
    isAnalysisError: analysisQuery.isError,
    reconciliationDeferred: !reconciliationSection.seen,
  };

  /*
   * 深色 owner 由外层 ThemedRouteBoundary 的 data-moss-theme="dark" 承担；
   * 页根只声明 Nocturne scope，重复声明 owner 会让深色路由校验判定出两个 owner。
   */
  return (
    <section
      data-testid="ledger-pnl-page"
      data-moss-theme-scope="ledger-pnl"
      className="ledger-pnl-page theme-dh-api"
    >
      <div className="ledger-pnl-header">
        <div>
          <h1 data-testid="ledger-pnl-page-title" className="ledger-pnl-header__title">
            总账损益
          </h1>
          <p data-testid="ledger-pnl-page-subtitle" className="ledger-pnl-header__subtitle">
            科目口径损益总览、币种汇总与账户明细。页面直接消费后端总账口径读模型，
            不在前端补算会计科目聚合。
          </p>
        </div>
        <span
          className={`ledger-pnl-header__mode-badge ledger-pnl-header__mode-badge--${
            client.mode === "real" ? "real" : "mock"
          }`}
        >
          {client.mode === "real" ? "真实 API 只读链路 · 非正式口径" : "本地演示数据"}
        </span>
      </div>

      <FilterBar className="ledger-pnl-filters">
        <label>
          <span className="ledger-pnl-filters__label">报告日</span>
          <select
            id={LEDGER_PNL_REPORT_DATE_SELECT_ID}
            data-testid="ledger-pnl-report-date-control"
            aria-label="总账损益报告日"
            value={selectedReportDate}
            onChange={(event) => {
              const nextParams = new URLSearchParams(searchParams);
              nextParams.delete("report_date");
              nextParams.delete("currency");
              if (event.target.value) {
                nextParams.set("report_date", event.target.value);
              }
              nextParams.set("currency", currency);
              setSearchParams(nextParams, { replace: true });
            }}
            className="ledger-pnl-filters__select"
          >
            {selectedReportDate && !reportDates.includes(selectedReportDate) ? (
              <option value={selectedReportDate}>{selectedReportDate}</option>
            ) : null}
            {reportDates.length === 0 && !selectedReportDate ? <option value="">暂无可选报告日</option> : null}
            {reportDates.map((reportDate) => (
              <option key={reportDate} value={reportDate}>
                {reportDate}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="ledger-pnl-filters__label">
            账务口径
          </span>
          <select
            data-testid="ledger-pnl-currency-control"
            aria-label="总账损益账务口径"
            value={currency}
            onChange={(event) => {
              const nextParams = new URLSearchParams(searchParams);
              nextParams.set("currency", normalizeLedgerPnlCurrencyBasis(event.target.value));
              setSearchParams(nextParams, { replace: true });
            }}
            className="ledger-pnl-filters__select ledger-pnl-filters__select--currency"
          >
            {LEDGER_PNL_CURRENCY_BASIS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <p className="ledger-pnl-filters__note">
          CNX（综本）与 CNY（人民币账）是重叠账务口径，不可相加。
          {selectedReportDateMissingFromDates ? (
            <span className="ledger-pnl-filters__note--warn">
              当前报告日不在可选列表中，仍按查询日期读取总账数据
            </span>
          ) : null}
        </p>
      </FilterBar>

      <LedgerPnlSectionNav
        items={sectionNavItems}
        onBeforeNavigate={wakeSectionsForNavigate}
      />

      <LedgerPnlAuditVerdict audit={ledgerFunctionalAuditProps} summary={summary} />

      <section id={LEDGER_PNL_SECTION_IDS.summary} className="ledger-pnl-section">
        <LedgerPnlSectionLead
          title="账面总览"
          state={ledgerSectionState(summaryQuery, {
            isEmpty: summary?.data_status === "no_data",
            emptyLabel: "当期无总账证据",
          })}
          note={`${currency} 口径 · 亿元`}
        />
        <div
          data-testid="ledger-pnl-summary-cards"
          className="ledger-pnl-summary-grid"
        >
          <LedgerPnlSummaryCards summary={summary} analysisPayload={analysisQuery.data?.result} />
        </div>
      </section>

      <LedgerPnlAccountDetailDrawer
        selection={selectedContributor}
        reportDate={selectedReportDate}
        currency={currency}
        onClose={() => setSelectedContributor(null)}
        onLocate={locateContributorInDetail}
      />

      <section id={LEDGER_PNL_SECTION_IDS.analysis} className="ledger-pnl-section">
        <LedgerPnlSectionLead title="损益分析" state={ledgerSectionState(analysisQuery)} />
        <LedgerPnlAnalysisWorkbench
          envelope={analysisQuery.data}
          isLoading={analysisQuery.isLoading}
          isError={analysisQuery.isError}
          error={analysisQuery.error}
          onRetry={() => {
            void analysisQuery.refetch();
          }}
          onSelectContributor={setSelectedContributor}
        />
      </section>

      <section
        id={LEDGER_PNL_SECTION_IDS.indicators}
        ref={indicatorsSection.ref}
        className="ledger-pnl-section"
      >
        <LedgerPnlSectionLead title="经营指标" note={`${requestedAnalysisMonth || EM_DASH} · 总账口径`} />
        {indicatorsSection.seen ? (
          <LedgerPnlFinancialIndicatorSummaryPanel
            reportMonth={requestedAnalysisMonth}
            currency={currency}
          />
        ) : (
          <LedgerSectionSkeleton
            testId="ledger-pnl-indicators-skeleton"
            title="经营指标情况表（总账口径）"
            minHeight={260}
          />
        )}
      </section>

      <section
        id={LEDGER_PNL_SECTION_IDS.candidate}
        ref={candidateSection.ref}
        className="ledger-pnl-section"
      >
        <LedgerPnlSectionLead title="候选指标" note="候选口径，不可正式使用" />
        {candidateSection.seen ? (
          <LedgerPnlCandidateFinancialIndicatorsPanel
            reportMonth={requestedAnalysisMonth}
            currency={currency}
          />
        ) : (
          <LedgerSectionSkeleton
            testId="ledger-pnl-candidate-skeleton"
            title="候选财务指标"
            minHeight={320}
          />
        )}
      </section>

      <section
        id={LEDGER_PNL_SECTION_IDS.reconciliation}
        ref={reconciliationSection.ref}
        className="ledger-pnl-section"
      >
        <LedgerPnlSectionLead title="对账与日均" note="月度工作簿口径" />
        <LedgerPnlMonthlyReconciliation
          requestedAnalysisMonth={requestedAnalysisMonth}
          selectedAnalysisMonth={selectedAnalysisMonth}
          deferred={!reconciliationSection.seen}
          hasMatchingAnalysisMonth={hasMatchingAnalysisMonth}
          monthlyAnalysisDatesQuery={monthlyAnalysisDatesQuery}
          monthlyAnalysisWorkbookQuery={monthlyAnalysisWorkbookQuery}
          formalIndicatorSourceContractQuery={formalIndicatorSourceContractQuery}
          formalIndicatorRuleChecksQuery={formalIndicatorRuleChecksQuery}
        />
      </section>

      <LedgerPnlAccountSummarySection
        summary={summary}
        isLoading={summaryQuery.isLoading}
        isError={summaryQuery.isError}
      />

      <LedgerPnlAccountDetailSection
        data={dataQuery.data?.result}
        isLoading={dataQuery.isLoading}
        isError={dataQuery.isError}
        detailAccountFilter={detailAccountFilter}
        onClearAccountFilter={() => setDetailAccountFilter(null)}
        anchorRef={detailTableRef}
      />

      <section id={LEDGER_PNL_SECTION_IDS.evidence} className="ledger-pnl-section">
        <LedgerPnlSectionLead title="证据与元信息" note="接口口径与来源版本" />
        {/* 证据层默认折叠（DESIGN §6 溯源分层）：端点 meta、trace、来源版本收进展开区，内容零删减。 */}
        <details className="ledger-pnl-governance-details">
          <summary>展开 7 个接口的口径、trace 与来源版本明细</summary>
          <div className="ledger-pnl-evidence-layer">
            <FormalResultMetaPanel
              testId="ledger-pnl-result-meta-panel"
              sections={[
                { key: "dates", title: "Ledger 报告日", meta: datesQuery.data?.result_meta },
                { key: "summary", title: "Ledger 汇总", meta: summaryQuery.data?.result_meta },
                { key: "data", title: "Ledger 明细", meta: dataQuery.data?.result_meta },
                { key: "analysis", title: "Ledger 候选分析", meta: analysisQuery.data?.result_meta },
                { key: "monthly-analysis-dates", title: "月度分析月份", meta: monthlyAnalysisDatesQuery.data?.result_meta },
                {
                  key: "monthly-analysis-workbook",
                  title: "月度分析工作簿",
                  meta: monthlyAnalysisWorkbookQuery.data?.result_meta,
                },
                {
                  key: "formal-financial-indicator-source-contract",
                  title: "正式财务指标源契约",
                  meta: formalIndicatorSourceContractQuery.data?.result_meta,
                },
              ]}
            />
          </div>
        </details>
      </section>
    </section>
  );
}
