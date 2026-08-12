import type { FactorScreenCandidateItem } from "../../../api/contracts";
import type { EChartsOption } from "../../../lib/echarts";
import type {
  StockCandidateReviewQueueItem,
  StockMarketStateCard,
  StockReviewQueueEmptyState,
} from "../lib/stockAnalysisPageModel";
import type {
  StockDataGapOverview,
  StockFactorScreenCardModel,
  StockFirstScreenHeroModel,
  StockMacroCycleCardModel,
} from "../lib/stockAnalysisFirstScreenModel";
import { StockAnalysisFactorCandidatesCard } from "./StockAnalysisFactorCandidatesCard";
import { StockAnalysisFirstScreenHero } from "./StockAnalysisFirstScreenHero";
import { StockAnalysisFirstScreenRail } from "./StockAnalysisFirstScreenRail";
import { StockAnalysisGateConditionsCard } from "./StockAnalysisGateConditionsCard";
import { StockAnalysisMacroCycleCard } from "./StockAnalysisMacroCycleCard";
import { StockAnalysisSectorStrengthCard } from "./StockAnalysisSectorStrengthCard";

type SectorStrengthCardState = "ready" | "loading" | "empty" | "error";

type StockAnalysisDecisionFirstScreenProps = {
  asOfLabel: string;
  requestedAsOfLabel?: string | null;
  staleBannerLabel?: string | null;
  heroModel: StockFirstScreenHeroModel;
  marketState: StockMarketStateCard;
  macroCycleModel: StockMacroCycleCardModel | null;
  sectorCard: {
    state: SectorStrengthCardState;
    chartOption: EChartsOption | null;
    sectorCount: number;
    sourceLabel: string;
    leaderLabel: string | null;
    emptyReason?: string | null;
    errorMessage?: string | null;
  };
  factorModel: StockFactorScreenCardModel | null;
  factorItems: FactorScreenCandidateItem[];
  onOpenFactorDetail: (row: FactorScreenCandidateItem) => void;
  queueTotalCount: number;
  queueVisibleCount: number;
  canReviewCandidates: boolean;
  emptyState: StockReviewQueueEmptyState | null;
  primaryBlockerLabel: string | null;
  topCandidates: StockCandidateReviewQueueItem[];
  onOpenCandidate: (card: StockCandidateReviewQueueItem) => void;
  onJumpToQueue: () => void;
  gapOverview: StockDataGapOverview;
};

/**
 * Product first screen: answer whether review can proceed, what can be observed,
 * and what is blocking — without flooding governance metadata.
 */
export function StockAnalysisDecisionFirstScreen({
  asOfLabel,
  requestedAsOfLabel,
  staleBannerLabel,
  heroModel,
  marketState,
  macroCycleModel,
  sectorCard,
  factorModel,
  factorItems,
  onOpenFactorDetail,
  queueTotalCount,
  queueVisibleCount,
  canReviewCandidates,
  emptyState,
  primaryBlockerLabel,
  topCandidates,
  onOpenCandidate,
  onJumpToQueue,
  gapOverview,
}: StockAnalysisDecisionFirstScreenProps) {
  return (
    <div
      className="stock-analysis-page__decision-first-screen"
      data-testid="stock-analysis-decision-first-screen"
    >
      {staleBannerLabel ? (
        <div
          className="stock-analysis-page__stale-banner"
          data-testid="stock-analysis-stale-banner"
          role="status"
        >
          {staleBannerLabel}。下方结论仅供复核参考。
        </div>
      ) : null}

      <StockAnalysisFirstScreenHero
        asOfLabel={asOfLabel}
        requestedAsOfLabel={requestedAsOfLabel}
        model={heroModel}
      />

      <div className="stock-analysis-page__fs-tri" data-testid="stock-analysis-first-screen-tri">
        <StockAnalysisGateConditionsCard marketState={marketState} />
        <StockAnalysisMacroCycleCard model={macroCycleModel} />
        <StockAnalysisSectorStrengthCard
          state={sectorCard.state}
          chartOption={sectorCard.chartOption}
          sectorCount={sectorCard.sectorCount}
          sourceLabel={sectorCard.sourceLabel}
          leaderLabel={sectorCard.leaderLabel}
          emptyReason={sectorCard.emptyReason}
          errorMessage={sectorCard.errorMessage}
        />
      </div>

      <div className="stock-analysis-page__fs-main" data-testid="stock-analysis-first-screen-primary">
        <StockAnalysisFactorCandidatesCard
          model={factorModel}
          items={factorItems}
          onOpenDetail={onOpenFactorDetail}
        />
        <StockAnalysisFirstScreenRail
          queueTotalCount={queueTotalCount}
          queueVisibleCount={queueVisibleCount}
          canReviewCandidates={canReviewCandidates}
          emptyState={emptyState}
          primaryBlockerLabel={primaryBlockerLabel}
          topCandidates={topCandidates}
          onOpenCandidate={onOpenCandidate}
          onJumpToQueue={onJumpToQueue}
          gapOverview={gapOverview}
        />
      </div>
    </div>
  );
}
