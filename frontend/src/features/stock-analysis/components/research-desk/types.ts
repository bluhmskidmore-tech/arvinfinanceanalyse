import type {
  StockCandidateReviewQueueItem,
  StockRiskExitRow,
} from "../../lib/stockAnalysisPageModel";
import type {
  ResearchDeskDossierTab,
  ResearchDeskPoolTab,
  ResearchDeskSignalWindow,
  StockAnalysisResearchDeskModel,
} from "../../lib/stockAnalysisResearchDeskModel";

// Tab 联合类型以 lib 模型为唯一定义，组件层只做再导出，避免两处漂移。
export type { ResearchDeskDossierTab, ResearchDeskPoolTab };

export type ResearchDeskMetricCard = {
  key: string;
  label: string;
  value: string;
  detail: string;
  accent: string;
};

export type ResearchDeskSnapshotItem = {
  label: string;
  value: string;
};

export type ResearchDeskEvidenceItem = {
  key: string;
  label: string;
  value: string;
  rail: "primary" | "supporting";
};

export type ResearchDeskAuditRow = {
  time: string;
  kind: string;
  subject: string;
  detail: string;
  source: string;
  score: string;
  status: string;
  owner: string;
};

export type ResearchDeskHistoryStat = {
  total: number;
  matured: number;
  latestDate: string | null;
  avgReturn5d: number | null;
};

export type ResearchDeskEndpointItem = {
  key: string;
  label: string;
  statusLabel: string;
  businessDateLabel: string;
  description: string;
  tone: string;
};

// 信号窗口以 lib 模型的定义为准（tone 允许 negative），组件层只做再导出。
export type { ResearchDeskSignalWindow };

export type ResearchDeskHistoryRow = {
  snapshot_as_of_date: string;
  candidate_rank: number;
  data_status: string;
  signalLabel: string;
  return1d: string;
  return5d: string;
  return20d: string;
};

export type ResearchDeskKeyValue = {
  key: string;
  label: string;
  value: string;
};

export type ResearchDeskFactorCell = ResearchDeskKeyValue & {
  accent: string;
  /** 截面分位徽章，如 "P90"；样本不足或值不可解析时为 null，不渲染。 */
  percentile: string | null;
};

export type ResearchDeskTimelineItem = {
  key: string;
  time: string;
  detail: string;
};

export type StockAnalysisResearchDeskProps = {
  /**
   * 研究台的全部派生展示数据（结论、关键数据、因子格、财务、时间线、证据来源、审计行）。
   * 由 `buildStockAnalysisResearchDeskModel` 生成；组件只负责布局与交互，不再从 rawFields 重算。
   */
  model: StockAnalysisResearchDeskModel;
  queueSearchText: string;
  onQueueSearchTextChange: (value: string) => void;
  sectorOptions: Array<[string, string]>;
  selectedSectorCode: string | null;
  onSelectSector: (sectorCode: string | null) => void;
  poolTab: ResearchDeskPoolTab;
  onPoolTabChange: (tab: ResearchDeskPoolTab) => void;
  dossierTab: ResearchDeskDossierTab;
  onDossierTabChange: (tab: ResearchDeskDossierTab) => void;
  poolCandidates: StockCandidateReviewQueueItem[];
  queueVisibleCount: number;
  queueTotalCount: number;
  queueCountLabel?: string;
  interactionsDisabled?: boolean;
  restrictedActionsDisabled?: boolean;
  reviewQueueUsesHybridFusion: boolean;
  selectedCandidate: StockCandidateReviewQueueItem | null;
  selectedCandidateCode: string | null;
  onSelectCandidate: (stockCode: string) => void;
  watchlistCodes: string[];
  onToggleWatchlist: (stockCode: string) => void;
  selectedRisk: StockRiskExitRow | null;
  noteDraft: string;
  onNoteDraftChange: (value: string) => void;
  savedNote: string;
  onSaveNote: () => void;
  onOpenDeepResearch: () => void;
  onJumpToEvidence: () => void;
  onOpenDetailDrawer: () => void;
  onOpenHistory: () => void;
  sectorLinkSummary: string;
  sectorLinkFocus: string;
  queueEmptyHeadline: string;
  queueEmptyDetail: string;
  historyLoading: boolean;
  historyLoaded: boolean;
};
