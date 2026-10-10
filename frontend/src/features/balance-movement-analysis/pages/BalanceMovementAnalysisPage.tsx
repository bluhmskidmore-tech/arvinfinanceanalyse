import { Button } from "antd";
import { FilterBar } from "../../../components/FilterBar";
import { PageStateSurface } from "../../../components/page/PagePrimitives";
import { designTokens, nocturneTokens } from "../../../theme/designSystem";
import type { BalanceMovementBucket } from "../../../api/contracts";
import { BalanceMovementBucketEvidence } from "../components/BalanceMovementBucketEvidence";
import { BalanceMovementReadStatus } from "../components/BalanceMovementReadStatus";
import { DataQualityBanner } from "../../../components/page/DataQualityBanner";
import { SixMonthStructurePanel } from "../components/BalanceStructureEvolution";

import { buildBalanceMovementCsv, downloadCsv } from "../lib/balanceMovementCsv";
import {
  FigmaDecisionHero,
  FigmaLoadingHero,
  FigmaEmptyHero,
  FigmaKpiRibbon,
  FigmaDriversAndStructure,
} from "../components/BalanceMovementDecisionOverview";
import {
  FigmaMaturityAndConcentration,
  ZqtzMaturityStructurePanel,
  ZqtzConcentrationAnalysisPanel,
} from "../components/BalanceMovementMaturityConcentration";
import { EvidenceStrip, DataStatesGovernancePanel } from "../components/BalanceMovementTrust";
import {
  FigmaAccountingBuckets,
  StructureBridgeStage,
  LiveBasisDecompositionStage,
  DrilldownUnavailablePanel,
} from "../components/BalanceMovementAccountingEvidence";

import { isPreviousCalendarMonth } from "../lib/balanceMovementBusinessModel";

import { BusinessBalanceMatrixSection } from "../components/BalanceMovementBusinessTables";

import { useBalanceMovementAnalysis } from "../hooks/useBalanceMovementAnalysis";
import { useBalanceMovementViewModel } from "../hooks/useBalanceMovementViewModel";
import { BalanceMovementBusinessSummary } from "../components/BalanceMovementBusinessSummary";
import { ZqtzAssetDetailTable } from "../components/BalanceMovementBusinessTables";
import { BalanceMovementSupplementaryContent } from "../components/BalanceMovementSupplementaryContent";
import "./BalanceMovementAnalysisPage.css";
import "./BalanceMovementAnalysisFigma.css";

export default function BalanceMovementAnalysisPage() {
  const {
    datesQuery,
    detailQuery,
    reportDates,
    dateStatus,
    selectedDate,
    requestedReportDate,
    actualReportDate,
    readStatus,
    selectedBucket,
    isEvidenceOpen,
    updateBucketSelection,
    updateEvidenceSelection,
    currencyBasis,
    isRefreshing,
    refreshMessage,
    refreshError,
    updateReportDateSelection,
    handleRefresh,
  } = useBalanceMovementAnalysis();
  const {
    businessTopMomMoves,
    topMovementDriver,
    residualWaterfallComponent,
    unsupportedWaterfallComponents,
    zqtzMaturityStructure,
    zqtzConcentrationAnalysis,
    analysisDimensionCards,
    hasResultStatus,
    resultMeta,
    resultStatusReasons,
    summary,
    balanceChangePct,
    movementDrivers,
    reconciliationLabel,
    hasBalanceChangeTotal,
    compactMaturityGroups,
    issuerConcentration,
    rows,
    balanceStructureChartRows,
    structureShareTableRows,
    balanceStructureInsight,
    structureMigrationAnalysis,
    differenceAttributionWaterfall,
    explanationClosure,
    basisMovementDecomposition,
    zqtzCalibrationAnalysis,
    businessMatrixMonths,
    balanceChangeTotal,
    structureDriverHint,
    rowByBucket,
    movementDriverByBucket,
    businessTopSixMonthMoves,
    zqtzAssetDetailRows,
    zqtzAssetDetailSummaryRow,
    businessTrendMonths,
    businessMatrixLiabilityRows,
    businessProjectTableRows,
    currentTrendMonth,
    previousTrendMonth,
    governanceMeta,
    businessMatrixAssetRows,
    shareRowByReportMonth,
    historicalAnomalyDiagnostics,
  } = useBalanceMovementViewModel(detailQuery.data);

  function handleExportCsv() {
    if (!detailQuery.data) {
      return;
    }
    const csv = buildBalanceMovementCsv({
      result: detailQuery.data.result,
      resultMeta,
      selectedBucket,
      requestedReportDate,
      readStatus,
      businessTopMove: businessTopMomMoves[0],
      accountingTopDriver: topMovementDriver,
      residualComponent: residualWaterfallComponent,
      unsupportedComponents: unsupportedWaterfallComponents,
      maturityStructure: zqtzMaturityStructure,
      concentrationAnalysis: zqtzConcentrationAnalysis,
      explanationClosure,
      dimensionCards: analysisDimensionCards,
      historicalAnomalyDiagnostics,
    });
    downloadCsv(
      `balance-movement-analysis-${detailQuery.data.result.report_date}-${detailQuery.data.result.currency_basis}-${selectedBucket}.csv`,
      csv,
    );
  }

  return (
    <section
      data-testid="balance-movement-analysis-page"
      data-moss-theme-scope="balance-movement-analysis"
      className="balance-movement-page theme-dh-api"
    >
      <header className="balance-movement-page-header" data-testid="balance-movement-analysis-page-header">
        <div className="balance-movement-page-header__identity">
          <span>投资组合 / 资产结构</span>
          <h1 data-testid="balance-movement-analysis-title">资产余额变动分析</h1>
        </div>
        <div className="balance-movement-page-header__actions">
          <label>
            <span>报告月</span>
            <select
              aria-label="余额变动分析-报告日期"
              value={selectedDate}
              onChange={(event) => updateReportDateSelection(event.target.value)}
            >
              {reportDates.map((reportDate) => (
                <option key={reportDate} value={reportDate}>{reportDate}</option>
              ))}
            </select>
          </label>
          <label className="balance-movement-page-header__currency">
            <span>币种</span>
            <select
              aria-label="余额变动分析-控制币种"
              value={currencyBasis}
              disabled
              title="当前页面仅开放 CNX 正式口径"
            >
              <option value="CNX">CNX</option>
            </select>
          </label>
          <button
            type="button"
            data-testid="balance-movement-analysis-refresh"
            onClick={() => void handleRefresh()}
            disabled={!selectedDate || isRefreshing}
          >
            {isRefreshing ? "刷新中" : "刷新数据"}
          </button>
          <button
            type="button"
            data-testid="balance-movement-analysis-export-csv"
            onClick={handleExportCsv}
            disabled={!detailQuery.data}
          >
            导出 CSV
          </button>
        </div>
      </header>
      <div className="balance-movement-page-body">
        {refreshMessage ? (
          <div className="balance-movement-refresh-message" data-testid="balance-movement-analysis-refresh-message">
            {refreshMessage}
          </div>
        ) : null}
        {dateStatus ? (
          <BalanceMovementReadStatus
            {...dateStatus}
            testId="balance-movement-analysis-date-status"
            isFetching={datesQuery.isFetching}
            hasCachedResult={Boolean(datesQuery.data)}
            onRetry={() => void datesQuery.refetch()}
          />
        ) : null}
        {detailQuery.isError ? (
          <BalanceMovementReadStatus
            tone="error"
            title="余额变动加载失败"
            detail="请重试读取；持续失败时请检查服务与读模型状态。"
            testId="balance-movement-analysis-detail-status"
            isFetching={detailQuery.isFetching}
            hasCachedResult={Boolean(detailQuery.data)}
            onRetry={() => void detailQuery.refetch()}
          />
        ) : null}
        {hasResultStatus ? (
          <div className="balance-movement-quality-alert" data-testid="balance-movement-analysis-result-status">
            <DataQualityBanner resultMeta={resultMeta} degradedReasons={resultStatusReasons} />
            <div data-testid="balance-movement-analysis-result-status-facts" role="status">
              {resultStatusReasons.join(" · ")}
            </div>
          </div>
        ) : null}

        {summary && topMovementDriver && datesQuery.data?.result ? (
          <FigmaDecisionHero
            balanceChangePct={balanceChangePct}
            balanceChangeTotal={summary.balance_change_total}
            topDriver={topMovementDriver}
            movementDrivers={movementDrivers}
            dates={datesQuery.data.result}
            readStatus={readStatus}
            selectedDate={actualReportDate}
            reconciliationLabel={reconciliationLabel}
            currencyBasis={currencyBasis}
          />
        ) : detailQuery.isLoading && selectedDate && datesQuery.data?.result ? (
          <FigmaLoadingHero
            dates={datesQuery.data.result}
            readStatus={readStatus}
            selectedDate={actualReportDate}
            reconciliationLabel={reconciliationLabel}
            currencyBasis={currencyBasis}
          />
        ) : !detailQuery.isError && datesQuery.data?.result ? (
          <FigmaEmptyHero
            dates={datesQuery.data.result}
            readStatus={readStatus}
            selectedDate={actualReportDate}
            reconciliationLabel={reconciliationLabel}
            currencyBasis={currencyBasis}
          />
        ) : null}

        {summary && topMovementDriver ? (
          <FigmaKpiRibbon
            summary={summary}
            topDriver={topMovementDriver}
            hasBalanceChangeTotal={hasBalanceChangeTotal}
            reconciliationLabel={reconciliationLabel}
            balanceChangePct={balanceChangePct}
          />
        ) : null}

        {movementDrivers.length > 0 ? <FigmaDriversAndStructure drivers={movementDrivers} /> : null}

        {detailQuery.data ? (
          <FigmaMaturityAndConcentration
            maturityGroups={compactMaturityGroups}
            issuerDimension={issuerConcentration}
            maturityCoverage={zqtzMaturityStructure?.meta.coverage_pct}
            unknownMaturityAmount={zqtzMaturityStructure?.meta.unknown_total}
          />
        ) : null}

        {resultMeta ? (
          <EvidenceStrip
            meta={resultMeta}
            reportDate={actualReportDate}
            currencyBasis={currencyBasis}
          />
        ) : null}

        <section aria-label="分类桶只读复核">
          <FilterBar className="balance-movement-filter-bar">
            <label className="balance-movement-filter-field" style={{ fontSize: designTokens.fontSize[12] }}>
              <span>复核分类桶</span>
              <select
                aria-label="余额变动分析-分类桶"
                value={selectedBucket}
                onChange={(event) => updateBucketSelection(event.target.value as BalanceMovementBucket | "all")}
                style={{
                  height: designTokens.density.tableRowNormal,
                  paddingInline: designTokens.space[3],
                  border: "1px solid var(--dh-api-line)",
                  borderRadius: nocturneTokens.radius,
                  background: "var(--dh-api-panel)",
                  color: "var(--dh-api-ink)",
                  fontSize: designTokens.fontSize[13],
                }}
              >
                <option value="all">全部</option><option value="AC">AC</option><option value="OCI">OCI</option><option value="TPL">TPL</option>
              </select>
            </label>
            <Button disabled={selectedBucket === "all" || !detailQuery.data || detailQuery.isError} onClick={() => updateEvidenceSelection(true)}>查看分类桶来源</Button>
          </FilterBar>
          <p className="balance-movement-derived-panel__summary">分类桶选择作用于核心对账、来源复核与 CSV 分类明细；本页其余汇总和诊断保留全资产范围。</p>
          <p className="balance-movement-derived-panel__summary" data-testid="balance-movement-selection-dates">请求日期 {requestedReportDate || selectedDate} · 实际报告日 {actualReportDate}</p>
          {rows.length > 0 ? <FigmaAccountingBuckets rows={selectedBucket === "all" ? rows : rows.filter((row) => row.basis_bucket === selectedBucket)} /> : null}
        </section>
        {isEvidenceOpen && selectedBucket !== "all" ? (
          detailQuery.isLoading ? <PageStateSurface variant="loading" description="正在载入分类桶来源复核" />
            : detailQuery.isError ? <PageStateSurface
              variant="error"
              title="分类桶来源读取失败"
              description="暂时无法获取来源证据，请重试。"
              actions={<button type="button" onClick={() => void detailQuery.refetch()}>重试读取</button>}
            />
              : detailQuery.data ? <BalanceMovementBucketEvidence result={detailQuery.data.result} bucket={selectedBucket} onReturn={() => updateEvidenceSelection(false)} />
                : <PageStateSurface variant="empty" description="当前暂无分类桶来源证据。" />
        ) : null}

        {balanceStructureChartRows.length > 0 ||
        structureShareTableRows.length > 0 ||
        balanceStructureInsight ? (
          <SixMonthStructurePanel
            chartRows={balanceStructureChartRows}
            balanceStructureInsight={balanceStructureInsight}
          />
        ) : null}

      <StructureBridgeStage
        analysis={structureMigrationAnalysis}
        waterfall={differenceAttributionWaterfall}
        closure={explanationClosure}
      />

      {basisMovementDecomposition ? (
        <LiveBasisDecompositionStage
          decomposition={basisMovementDecomposition}
          hasCalibration={Boolean(zqtzCalibrationAnalysis)}
        />
      ) : detailQuery.data ? (
        <DrilldownUnavailablePanel
          testId="balance-movement-analysis-basis-decomposition"
          eyebrow="会计分类驱动拆解"
          title="AC / OCI / TPL 驱动拆解"
          fieldName="basis_movement_decomposition"
        />
      ) : null}

      {zqtzMaturityStructure ? (
        <ZqtzMaturityStructurePanel structure={zqtzMaturityStructure} />
      ) : detailQuery.data ? (
        <DrilldownUnavailablePanel
          testId="balance-movement-analysis-zqtz-maturity"
          eyebrow="ZQTZ 到期视图"
          title="期限 / 到期结构"
          fieldName="zqtz_maturity_structure"
        />
      ) : null}

      {zqtzConcentrationAnalysis ? (
        <ZqtzConcentrationAnalysisPanel analysis={zqtzConcentrationAnalysis} />
      ) : detailQuery.data ? (
        <DrilldownUnavailablePanel
          testId="balance-movement-analysis-zqtz-concentration"
          eyebrow="ZQTZ 集中度视图"
          title="主体 / 评级 / 行业集中度"
          fieldName="zqtz_concentration_analysis"
        />
      ) : null}

      {summary && topMovementDriver ? (
        <BalanceMovementBusinessSummary
          topMovementDriver={topMovementDriver}
          businessMatrixMonths={businessMatrixMonths}
          hasBalanceChangeTotal={hasBalanceChangeTotal}
          balanceChangeTotal={balanceChangeTotal}
          structureDriverHint={structureDriverHint}
          rowByBucket={rowByBucket}
          movementDriverByBucket={movementDriverByBucket}
          businessTopMomMoves={businessTopMomMoves}
          businessTopSixMonthMoves={businessTopSixMonthMoves}
          movementDrivers={movementDrivers}
        />
      ) : null}
      {zqtzAssetDetailRows.length > 0 ? (
        <ZqtzAssetDetailTable
          businessMatrixMonths={businessMatrixMonths}
          zqtzAssetDetailRows={zqtzAssetDetailRows}
          zqtzAssetDetailSummaryRow={zqtzAssetDetailSummaryRow}
        />
      ) : null}

      {businessTrendMonths.length > 0 ? (
        <BusinessBalanceMatrixSection
          months={businessMatrixMonths}
          liabilityRows={businessMatrixLiabilityRows}
          projectRows={businessProjectTableRows}
          balanceRows={rows}
          accountingSnapshotsAreNonAdjacent={Boolean(
            currentTrendMonth &&
              previousTrendMonth &&
              !isPreviousCalendarMonth(
                currentTrendMonth.report_date,
                previousTrendMonth.report_date,
              )
          )}
        />
      ) : null}
      <DataStatesGovernancePanel
        isLoading={datesQuery.isFetching || detailQuery.isFetching || isRefreshing}
        hasReportDates={reportDates.length > 0}
        hasRows={rows.length > 0}
        freshnessStatus={datesQuery.data?.result.freshness_status}
        requestedReportDate={requestedReportDate || selectedDate}
        resolvedReportDate={actualReportDate}
        readStatus={readStatus}
        hasError={datesQuery.isError || detailQuery.isError}
        datesReadFailed={datesQuery.isError}
        datesReadConfirmed={datesQuery.isSuccess && !datesQuery.isFetching}
        refreshError={refreshError}
        resultMeta={resultMeta}
        governanceMeta={governanceMeta}
        supplementary={() => (
          <BalanceMovementSupplementaryContent
            detailData={detailQuery.data}
            governanceMeta={governanceMeta}
            businessMatrixMonths={businessMatrixMonths}
            businessMatrixAssetRows={businessMatrixAssetRows}
            structureShareTableRows={structureShareTableRows}
            shareRowByReportMonth={shareRowByReportMonth}
            zqtzCalibrationAnalysis={zqtzCalibrationAnalysis}
            historicalAnomalyDiagnostics={historicalAnomalyDiagnostics}
          />
        )}
      />
      </div>
    </section>
  );
}
