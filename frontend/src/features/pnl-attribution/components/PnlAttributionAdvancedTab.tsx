/**
 * 高级归因 + Campisi 页签容器。
 * 自 PnlAttributionView.tsx 纯搬移（2026-08-13 拆分）：高级归因元信息面板、
 * Campisi 系列面板与高级归因图表，仅做 props 接线，不改行为。
 */
import type {
  AdvancedAttributionSummary,
  CampisiAttributionPayload,
  CampisiDecisionGradePayload,
  CampisiEnhancedPayload,
  CampisiFourEffectsPayload,
  CampisiMaturityBucketsPayload,
  CarryRollDownPayload,
  KRDAttributionPayload,
  ResultMeta,
  SpreadAttributionPayload,
} from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import { derivePnlDataSectionState } from "../adapters/pnlAttributionAdapter";
import { AdvancedAttributionChart } from "./AdvancedAttributionChart";
import { CampisiAttributionPanel } from "./CampisiAttributionPanel";
import { CampisiDecisionGradePanel } from "./CampisiDecisionGradePanel";
import { CampisiEnhancedPanel } from "./CampisiEnhancedPanel";
import { CampisiMaturityBucketPanel } from "./CampisiMaturityBucketPanel";

export function AdvancedAttributionTabPanels(props: {
  carryData: CarryRollDownPayload | null;
  spreadData: SpreadAttributionPayload | null;
  krdData: KRDAttributionPayload | null;
  summaryData: AdvancedAttributionSummary | null;
  campisiData: CampisiAttributionPayload | null;
  campisiFourEffects: CampisiFourEffectsPayload | null;
  campisiEnhanced: CampisiEnhancedPayload | null;
  campisiMaturityBuckets: CampisiMaturityBucketsPayload | null;
  campisiDecisionGrade: CampisiDecisionGradePayload | null;
  carryMeta: ResultMeta | null;
  spreadMeta: ResultMeta | null;
  krdMeta: ResultMeta | null;
  summaryMeta: ResultMeta | null;
  campisiFourMeta: ResultMeta | null;
  campisiEnhancedMeta: ResultMeta | null;
  campisiMaturityMeta: ResultMeta | null;
  campisiDecisionGradeMeta: ResultMeta | null;
  isLoading: boolean;
  errorMessage: string | null;
  decisionGradeErrorMessage: string | null;
  onRetry: () => void;
}) {
  const advancedMetaRows: [string, ResultMeta | null][] = [
    ["Carry / Roll-down", props.carryMeta],
    ["利差归因", props.spreadMeta],
    ["KRD归因", props.krdMeta],
    ["高级摘要", props.summaryMeta],
    ["Campisi 四效应", props.campisiFourMeta],
    ["Campisi 六效应", props.campisiEnhancedMeta],
    ["Campisi 到期桶", props.campisiMaturityMeta],
    ["Campisi 决策级", props.campisiDecisionGradeMeta],
  ];
  const advancedMetaSections = advancedMetaRows.map(([title, meta], index) => ({
    key: `advanced-${index}`,
    title,
    meta,
  }));

  const advancedCarryState: DataSectionState = derivePnlDataSectionState({
    meta: props.carryMeta,
    isLoading: props.isLoading,
    isError: props.errorMessage !== null,
    errorMessage: props.errorMessage,
    isEmpty: !props.carryData || (props.carryData.items?.length ?? 0) === 0,
  });

  const campisiFourState: DataSectionState = derivePnlDataSectionState({
    meta: props.campisiFourMeta,
    isLoading: props.isLoading,
    isError: props.errorMessage !== null,
    errorMessage: props.errorMessage,
    isEmpty: !(props.campisiFourEffects ?? props.campisiData),
  });

  const campisiEnhancedState: DataSectionState = derivePnlDataSectionState({
    meta: props.campisiEnhancedMeta,
    isLoading: props.isLoading,
    isError: props.errorMessage !== null,
    errorMessage: props.errorMessage,
    isEmpty: !props.campisiEnhanced,
  });

  const campisiMaturityState: DataSectionState = derivePnlDataSectionState({
    meta: props.campisiMaturityMeta,
    isLoading: props.isLoading,
    isError: props.errorMessage !== null,
    errorMessage: props.errorMessage,
    isEmpty: !props.campisiMaturityBuckets,
  });

  const campisiDecisionGradeState: DataSectionState = derivePnlDataSectionState({
    meta: props.campisiDecisionGradeMeta,
    isLoading: props.isLoading,
    isError:
      props.errorMessage !== null || props.decisionGradeErrorMessage !== null,
    errorMessage: props.decisionGradeErrorMessage ?? props.errorMessage,
    isEmpty: !props.campisiDecisionGrade,
  });

  return (
    <>
      <CampisiDecisionGradePanel
        data={props.campisiDecisionGrade}
        state={campisiDecisionGradeState}
        onRetry={props.onRetry}
      />
      <CampisiAttributionPanel
        data={props.campisiFourEffects ?? props.campisiData}
        state={campisiFourState}
        onRetry={props.onRetry}
      />
      <CampisiEnhancedPanel
        data={props.campisiEnhanced}
        state={campisiEnhancedState}
        onRetry={props.onRetry}
      />
      <CampisiMaturityBucketPanel
        data={props.campisiMaturityBuckets}
        state={campisiMaturityState}
        onRetry={props.onRetry}
      />
      <AdvancedAttributionChart
        carryData={props.carryData}
        spreadData={props.spreadData}
        krdData={props.krdData}
        summaryData={props.summaryData}
        state={advancedCarryState}
        onRetry={props.onRetry}
      />
      {/* 证据层收尾：8 张溯源卡约 2.5 屏，放在业务面板之后（§6 先结论后证据）。 */}
      <FormalResultMetaPanel
        testId="pnl-attribution-advanced-view-meta"
        title="高级归因结果元信息"
        emptyText={
          props.isLoading ? "加载中…" : "当前还没有可展示的高级归因元信息。"
        }
        sections={advancedMetaSections}
      />
    </>
  );
}
