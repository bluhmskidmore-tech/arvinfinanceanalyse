import type { MouseEvent as ReactMouseEvent, ReactNode } from "react";

import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitCapabilityResult,
  MacroToolkitHasonStrategy,
  MacroToolkitShadowPortfolioReport,
  MacroToolkitSignalCard,
  MacroToolkitStrategySummary,
} from "../../../api/macroToolkitClient";
import { MT_SHELL_MAIN } from "../lib/macroToolkitPageChrome";
import { ObservationEvidenceTraceSummary } from "../sections/MacroToolkitDataHealthSections";
import {
  MacroToolkitInvestmentEvidenceSection,
  MacroToolkitObservationComparisonSection,
} from "../sections/MacroToolkitObservationSections";

// 宏观观察（observation 模式）壳：只负责只读观察布局的装配。
// 全部区块从 MacroToolkitPage 纯搬移，行为与文案不变；
// 数据编排仍留在页面主体。
export function MacroToolkitObservationView({
  analysis,
  visibleSignalCards,
  primarySignal,
  selectedEvidenceHref,
  strategySummaries,
  strategySupplyState,
  fullRealStrategyCount,
  partialRealStrategyCount,
  degradedStrategyCount,
  sampleStrategyCount,
  shadowPortfolioReport,
  strategyQuery,
  capabilityResults,
  degradedResultCount,
  hasonStrategy,
  isCoreAnalysis,
  handleDeferredContentLinkClick,
  cockpitSection,
  analysisFailedAlert,
  fullAnalysisErrorAlert,
  initialAnalysisLoadingSection,
  analysisEvidenceFlow,
  modelSignalMatrixSection,
  crisisEvidenceSection,
  reportBundleSection,
}: {
  analysis: MacroToolkitAnalysisPayload | undefined;
  visibleSignalCards: MacroToolkitSignalCard[];
  primarySignal: MacroToolkitSignalCard | null;
  selectedEvidenceHref: string | null;
  strategySummaries: MacroToolkitStrategySummary[];
  strategySupplyState: "loading" | "failed" | "loaded";
  fullRealStrategyCount: number;
  partialRealStrategyCount: number;
  degradedStrategyCount: number;
  sampleStrategyCount: number;
  shadowPortfolioReport: MacroToolkitShadowPortfolioReport | null;
  strategyQuery: { isFetching: boolean; isError: boolean; error: unknown };
  capabilityResults: MacroToolkitCapabilityResult[];
  degradedResultCount: number;
  hasonStrategy: MacroToolkitHasonStrategy | null;
  isCoreAnalysis: boolean;
  handleDeferredContentLinkClick: (event: ReactMouseEvent<HTMLElement>) => void;
  cockpitSection: ReactNode;
  analysisFailedAlert: ReactNode;
  fullAnalysisErrorAlert: ReactNode;
  initialAnalysisLoadingSection: ReactNode;
  analysisEvidenceFlow: ReactNode;
  modelSignalMatrixSection: ReactNode;
  crisisEvidenceSection: ReactNode;
  reportBundleSection: ReactNode;
}) {
  const observationSignalRiskComparisonSection = analysis ? (
    <MacroToolkitObservationComparisonSection
      signalCards={visibleSignalCards}
      primarySignal={primarySignal}
      risk={analysis.a_share_risk}
    />
  ) : null;
  const investmentEvidenceSection = analysis ? (
    <MacroToolkitInvestmentEvidenceSection
      analysis={analysis}
      showOperations={false}
      selectedEvidenceHref={selectedEvidenceHref}
      strategySummaries={strategySummaries}
      strategySupplyState={strategySupplyState}
      fullRealStrategyCount={fullRealStrategyCount}
      partialRealStrategyCount={partialRealStrategyCount}
      degradedStrategyCount={degradedStrategyCount}
      sampleStrategyCount={sampleStrategyCount}
      shadowPortfolioReport={shadowPortfolioReport}
      strategyQuery={strategyQuery}
    />
  ) : null;
  const observationEvidenceTraceSummary = analysis ? (
    <ObservationEvidenceTraceSummary
      dataHealth={analysis.data_health}
      capabilityResults={capabilityResults}
      degradedResultCount={degradedResultCount}
      hasonStrategy={hasonStrategy ?? undefined}
      isCoreAnalysis={isCoreAnalysis}
    />
  ) : null;

  return (
    <main
      className={`${MT_SHELL_MAIN} macro-toolkit-page__main`}
      onClickCapture={handleDeferredContentLinkClick}
    >
      <div className="macro-toolkit-page__primary">
        {cockpitSection}

        <div className="macro-toolkit-page__content">
          {analysisFailedAlert}
          {fullAnalysisErrorAlert}
          {initialAnalysisLoadingSection}
          {analysis ? (
            <>
              {analysisEvidenceFlow}
              <div className="macro-toolkit-observation-flow" aria-label="宏观观察阅读顺序">
                {observationSignalRiskComparisonSection}
                {modelSignalMatrixSection}
                {investmentEvidenceSection}
              </div>
              <div className="macro-toolkit-observation-evidence-flow" aria-label="宏观观察证据追踪">
                {crisisEvidenceSection}
                {observationEvidenceTraceSummary}
              </div>
            </>
          ) : null}
        </div>

        {reportBundleSection}
      </div>
    </main>
  );
}
