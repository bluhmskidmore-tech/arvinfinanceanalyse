import { useCallback, useEffect, useState } from "react";

import { useApiClient } from "../../../api/client";
import type { Numeric } from "../../../api/contracts";
import { FilterBar } from "../../../components/FilterBar";
import type { DataSectionState } from "../../../components/DataSection.types";
import type {
  AdvancedAttributionSummary,
  CampisiAttributionPayload,
  CampisiEnhancedPayload,
  CampisiFourEffectsPayload,
  CampisiMaturityBucketsPayload,
  CarryRollDownPayload,
  KRDAttributionPayload,
  PnlAttributionAnalysisSummary,
  PnlCompositionPayload,
  ResultMeta,
  SpreadAttributionPayload,
  TPLMarketCorrelationPayload,
  VolumeRateAttributionPayload,
} from "../../../api/contracts";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { derivePnlDataSectionState } from "../adapters/pnlAttributionAdapter";
import { AdvancedAttributionChart } from "./AdvancedAttributionChart";
import { AttributionWaterfallChart } from "./AttributionWaterfallChart";
import { CampisiAttributionPanel } from "./CampisiAttributionPanel";
import { CampisiEnhancedPanel } from "./CampisiEnhancedPanel";
import { CampisiMaturityBucketPanel } from "./CampisiMaturityBucketPanel";
import { PnLCompositionChart } from "./PnLCompositionChart";
import { TPLMarketChart } from "./TPLMarketChart";
import { VolumeRateAnalysisChart } from "./VolumeRateAnalysisChart";

const shellStyle = {
  display: "flex",
  flexDirection: "column" as const,
  gap: designTokens.space[5],
};

const headerCardStyle = {
  padding: designTokens.space[5],
  borderRadius: designTokens.radius.lg,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: designTokens.color.primary[50],
  boxShadow: designTokens.shadow.card,
} as const;

const modeBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
  borderRadius: 999,
  fontSize: designTokens.fontSize[12],
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
} as const;

const sectionLeadWrapStyle = {
  display: "grid",
  gap: designTokens.space[2],
} as const;

const sectionEyebrowStyle = {
  fontSize: designTokens.fontSize[11],
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: designTokens.color.neutral[600],
} as const;

const sectionTitleStyle = {
  margin: 0,
  fontSize: designTokens.fontSize[18],
  fontWeight: 600,
  color: designTokens.color.neutral[900],
} as const;

const sectionDescriptionStyle = {
  margin: 0,
  maxWidth: 900,
  color: designTokens.color.neutral[700],
  fontSize: designTokens.fontSize[13],
  lineHeight: designTokens.lineHeight.relaxed,
} as const;

const tabBarStyle = {
  display: "flex",
  flexWrap: "wrap" as const,
  gap: designTokens.space[2],
  alignItems: "center",
};

const metaStripStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: designTokens.space[3],
  marginTop: designTokens.space[4],
  padding: designTokens.space[4],
  borderRadius: designTokens.radius.md,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: designTokens.color.primary[50],
} as const;

const metaCellStyle = {
  display: "grid",
  gap: designTokens.space[1],
} as const;

const metaLabelStyle = {
  fontSize: designTokens.fontSize[11],
  fontWeight: 700,
  letterSpacing: "0.06em",
  textTransform: "uppercase",
  color: designTokens.color.neutral[600],
} as const;

const metaValueStyle = {
  fontSize: designTokens.fontSize[13],
  color: designTokens.color.neutral[900],
  lineHeight: designTokens.lineHeight.normal,
} as const;

function tabStyle(active: boolean, variant: "default" | "advanced" = "default") {
  const base = {
    padding: `${designTokens.space[3]}px ${designTokens.space[4]}px`,
    borderRadius: designTokens.radius.md,
    fontWeight: 600,
    fontSize: designTokens.fontSize[14],
    cursor: "pointer",
    border: "1px solid",
  } as const;
  if (variant === "advanced") {
    return {
      ...base,
      borderColor: active ? designTokens.color.primary[700] : designTokens.color.primary[200],
      background: active ? designTokens.color.primary[700] : designTokens.color.primary[50],
      color: active ? designTokens.color.primary[50] : designTokens.color.primary[700],
    };
  }
  return {
    ...base,
    borderColor: active ? designTokens.color.primary[600] : designTokens.color.neutral[300],
    background: active ? designTokens.color.primary[100] : designTokens.color.primary[50],
    color: active ? designTokens.color.primary[600] : designTokens.color.neutral[900],
  };
}

function numericRaw(value: Numeric | null | undefined): number | null | undefined {
  if (value === null || value === undefined) {
    return undefined;
  }
  return value.raw ?? undefined;
}

function formatYi(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const yi = value / 100_000_000;
  return `${yi >= 0 ? "+" : ""}${yi.toFixed(2)} 亿`;
}

function formatYiNumeric(value: Numeric | null | undefined): string {
  return formatYi(numericRaw(value));
}

function SectionLead(props: {
  eyebrow: string;
  title: string;
  description: string;
  testId?: string;
}) {
  return (
    <div data-testid={props.testId} style={sectionLeadWrapStyle}>
      <span style={sectionEyebrowStyle}>{props.eyebrow}</span>
      <h2 style={sectionTitleStyle}>{props.title}</h2>
      <p style={sectionDescriptionStyle}>{props.description}</p>
    </div>
  );
}

function formatMetaDateLabel(
  activeTab: Tab,
  options: {
    volumeRateData: VolumeRateAttributionPayload | null;
    tplMarketData: TPLMarketCorrelationPayload | null;
    compositionData: PnlCompositionPayload | null;
    advancedSummary: AdvancedAttributionSummary | null;
  },
) {
  if (activeTab === "volume-rate") {
    return {
      label: "当前期间",
      value: options.volumeRateData?.current_period ?? "—",
    };
  }
  if (activeTab === "tpl-market") {
    const start = options.tplMarketData?.start_period;
    const end = options.tplMarketData?.end_period;
    return {
      label: "观察区间",
      value: start && end ? `${start} ~ ${end}` : "—",
    };
  }
  if (activeTab === "composition") {
    return {
      label: "报告日期",
      value: options.compositionData?.report_date ?? options.compositionData?.report_period ?? "—",
    };
  }
  return {
    label: "报告日期",
    value: options.advancedSummary?.report_date ?? "—",
  };
}

type Tab = "volume-rate" | "tpl-market" | "composition" | "advanced";

type Props = {
  reportDate?: string;
};

export function PnlAttributionView({ reportDate }: Props) {
  const client = useApiClient();
  const [activeTab, setActiveTab] = useState<Tab>("volume-rate");
  const [compareType, setCompareType] = useState<"mom" | "yoy">("mom");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [volumeRateData, setVolumeRateData] = useState<VolumeRateAttributionPayload | null>(null);
  const [tplMarketData, setTplMarketData] = useState<TPLMarketCorrelationPayload | null>(null);
  const [compositionData, setCompositionData] = useState<PnlCompositionPayload | null>(null);
  const [summaryData, setSummaryData] = useState<PnlAttributionAnalysisSummary | null>(null);
  const [volumeRateMeta, setVolumeRateMeta] = useState<ResultMeta | null>(null);
  const [tplMarketMeta, setTplMarketMeta] = useState<ResultMeta | null>(null);
  const [compositionMeta, setCompositionMeta] = useState<ResultMeta | null>(null);
  const [advancedSummaryMeta, setAdvancedSummaryMeta] = useState<ResultMeta | null>(null);

  const [carryRollDownData, setCarryRollDownData] = useState<CarryRollDownPayload | null>(null);
  const [spreadData, setSpreadData] = useState<SpreadAttributionPayload | null>(null);
  const [krdData, setKrdData] = useState<KRDAttributionPayload | null>(null);
  const [advancedSummary, setAdvancedSummary] = useState<AdvancedAttributionSummary | null>(null);
  const [campisiData, setCampisiData] = useState<CampisiAttributionPayload | null>(null);
  const [campisiFourEffects, setCampisiFourEffects] = useState<CampisiFourEffectsPayload | null>(null);
  const [campisiEnhanced, setCampisiEnhanced] = useState<CampisiEnhancedPayload | null>(null);
  const [campisiMaturityBuckets, setCampisiMaturityBuckets] = useState<CampisiMaturityBucketsPayload | null>(null);
  const [carryMeta, setCarryMeta] = useState<ResultMeta | null>(null);
  const [spreadMeta, setSpreadMeta] = useState<ResultMeta | null>(null);
  const [krdMeta, setKrdMeta] = useState<ResultMeta | null>(null);
  const [campisiFourMeta, setCampisiFourMeta] = useState<ResultMeta | null>(null);
  const [campisiEnhancedMeta, setCampisiEnhancedMeta] = useState<ResultMeta | null>(null);
  const [campisiMaturityMeta, setCampisiMaturityMeta] = useState<ResultMeta | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeTab === "volume-rate") {
        const [data, summary] = await Promise.all([
          client.getVolumeRateAttribution({ reportDate, compareType }),
          client.getPnlAttributionAnalysisSummary(reportDate),
        ]);
        setVolumeRateData(data.result);
        setVolumeRateMeta(data.result_meta);
        setSummaryData(summary.result);
      } else if (activeTab === "tpl-market") {
        const data = await client.getTplMarketCorrelation({ months: 12 });
        setTplMarketData(data.result);
        setTplMarketMeta(data.result_meta);
      } else if (activeTab === "composition") {
        const data = await client.getPnlCompositionBreakdown({
          reportDate,
          includeTrend: true,
          trendMonths: 6,
        });
        setCompositionData(data.result);
        setCompositionMeta(data.result_meta);
      } else {
        const [carry, spread, krd, summary, campisi, campisiFour, campisiEnhancedData, campisiBuckets] = await Promise.all([
          client.getPnlCarryRollDown(reportDate),
          client.getPnlSpreadAttribution({ reportDate, lookbackDays: 30 }),
          client.getPnlKrdAttribution({ reportDate, lookbackDays: 30 }),
          client.getPnlAdvancedAttributionSummary(reportDate),
          client.getPnlCampisiAttribution({ lookbackDays: 30 }),
          client.getPnlCampisiFourEffects({ endDate: reportDate, lookbackDays: 30 }),
          client.getPnlCampisiEnhanced({ endDate: reportDate, lookbackDays: 30 }),
          client.getPnlCampisiMaturityBuckets({ endDate: reportDate, lookbackDays: 30 }),
        ]);
        setCarryRollDownData(carry.result);
        setCarryMeta(carry.result_meta);
        setSpreadData(spread.result);
        setSpreadMeta(spread.result_meta);
        setKrdData(krd.result);
        setKrdMeta(krd.result_meta);
        setAdvancedSummary(summary.result);
        setAdvancedSummaryMeta(summary.result_meta);
        setCampisiData(campisi.result);
        setCampisiFourEffects(campisiFour.result);
        setCampisiFourMeta(campisiFour.result_meta);
        setCampisiEnhanced(campisiEnhancedData.result);
        setCampisiEnhancedMeta(campisiEnhancedData.result_meta);
        setCampisiMaturityBuckets(campisiBuckets.result);
        setCampisiMaturityMeta(campisiBuckets.result_meta);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "加载失败";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [activeTab, client, compareType, reportDate]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const keyFindings =
    activeTab === "advanced" ? advancedSummary?.key_insights ?? [] : summaryData?.key_findings ?? [];
  const currentViewMeta =
    activeTab === "volume-rate"
      ? volumeRateMeta
      : activeTab === "tpl-market"
        ? tplMarketMeta
        : activeTab === "composition"
          ? compositionMeta
          : advancedSummaryMeta;
  const currentViewDate = formatMetaDateLabel(activeTab, {
    volumeRateData,
    tplMarketData,
    compositionData,
    advancedSummary,
  });
  const advancedMetaRows: [string, ResultMeta | null][] =
    activeTab === "advanced"
      ? [
          ["Carry / Roll-down", carryMeta],
          ["利差归因", spreadMeta],
          ["KRD归因", krdMeta],
          ["高级摘要", advancedSummaryMeta],
          ["Campisi 四效应", campisiFourMeta],
          ["Campisi 六效应", campisiEnhancedMeta],
          ["Campisi 到期桶", campisiMaturityMeta],
        ]
      : [];

  const volumeRateState: DataSectionState = derivePnlDataSectionState({
    meta: volumeRateMeta,
    isLoading: loading && activeTab === "volume-rate",
    isError: error !== null && activeTab === "volume-rate",
    errorMessage: error,
    isEmpty: !volumeRateData || (volumeRateData.items?.length ?? 0) === 0,
  });

  const waterfallState: DataSectionState = derivePnlDataSectionState({
    meta: volumeRateMeta,
    isLoading: loading && activeTab === "volume-rate",
    isError: error !== null && activeTab === "volume-rate",
    errorMessage: error,
    isEmpty: false,
  });

  const tplMarketState: DataSectionState = derivePnlDataSectionState({
    meta: tplMarketMeta,
    isLoading: loading && activeTab === "tpl-market",
    isError: error !== null && activeTab === "tpl-market",
    errorMessage: error,
    isEmpty: !tplMarketData || (tplMarketData.data_points?.length ?? 0) === 0,
  });

  const compositionState: DataSectionState = derivePnlDataSectionState({
    meta: compositionMeta,
    isLoading: loading && activeTab === "composition",
    isError: error !== null && activeTab === "composition",
    errorMessage: error,
    isEmpty: !compositionData,
  });

  const advancedCarryState: DataSectionState = derivePnlDataSectionState({
    meta: carryMeta,
    isLoading: loading && activeTab === "advanced",
    isError: error !== null && activeTab === "advanced",
    errorMessage: error,
    isEmpty: !carryRollDownData || (carryRollDownData.items?.length ?? 0) === 0,
  });

  const campisiFourState: DataSectionState = derivePnlDataSectionState({
    meta: campisiFourMeta,
    isLoading: loading && activeTab === "advanced",
    isError: error !== null && activeTab === "advanced",
    errorMessage: error,
    isEmpty: !(campisiFourEffects ?? campisiData),
  });

  const campisiEnhancedState: DataSectionState = derivePnlDataSectionState({
    meta: campisiEnhancedMeta,
    isLoading: loading && activeTab === "advanced",
    isError: error !== null && activeTab === "advanced",
    errorMessage: error,
    isEmpty: !campisiEnhanced,
  });

  const campisiMaturityState: DataSectionState = derivePnlDataSectionState({
    meta: campisiMaturityMeta,
    isLoading: loading && activeTab === "advanced",
    isError: error !== null && activeTab === "advanced",
    errorMessage: error,
    isEmpty: !campisiMaturityBuckets,
  });

  return (
    <div style={shellStyle}>
      <div style={headerCardStyle}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: designTokens.space[4],
            flexWrap: "wrap",
          }}
        >
          <div>
            <h2
              data-testid="pnl-attribution-page-title"
              style={{
                margin: 0,
                fontSize: designTokens.fontSize[20],
                fontWeight: 700,
                color: designTokens.color.neutral[900],
              }}
            >
              损益归因分析
            </h2>
            <p
              style={{
                margin: `${designTokens.space[2]}px 0 0`,
                fontSize: designTokens.fontSize[13],
                color: designTokens.color.neutral[700],
                maxWidth: 640,
                lineHeight: designTokens.lineHeight.normal,
              }}
            >
              规模/利率一阶与交叉效应、TPL 与市场、损益构成，以及 Carry–Roll、利差、KRD 与 Campisi
              四效应（收入、国债、利差、选择）对照阅读。
            </p>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: designTokens.space[3],
              flexWrap: "wrap",
            }}
          >
            <span
              style={{
                ...modeBadgeStyle,
                background:
                  client.mode === "real" ? designTokens.color.success[50] : designTokens.color.info[50],
                color: client.mode === "real" ? designTokens.color.success[600] : designTokens.color.info[600],
              }}
            >
              {client.mode === "real" ? "正式只读链路" : "本地演示数据"}
            </span>
            <button
              type="button"
              onClick={() => void loadData()}
              disabled={loading}
              style={{
                ...tabStyle(false),
                alignSelf: "flex-start",
                opacity: loading ? 0.6 : 1,
              }}
            >
              {loading ? "刷新中…" : "刷新"}
            </button>
          </div>
        </div>

        {keyFindings.length > 0 && (
          <div
            style={{
              marginTop: designTokens.space[4],
              padding: designTokens.space[4],
              borderRadius: designTokens.radius.md,
              border: "1px solid",
              borderColor:
                activeTab === "advanced"
                  ? designTokens.color.primary[200]
                  : designTokens.color.warning[200],
              background:
                activeTab === "advanced" ? designTokens.color.primary[50] : designTokens.color.warning[50],
            }}
          >
            <div
              style={{
                fontWeight: 700,
                fontSize: designTokens.fontSize[13],
                marginBottom: designTokens.space[2],
                color: designTokens.color.neutral[900],
              }}
            >
              {activeTab === "advanced" ? "高级归因要点" : "关键发现"}
            </div>
            <ul
              style={{
                margin: 0,
                paddingLeft: designTokens.space[6],
                color: designTokens.color.neutral[700],
                fontSize: designTokens.fontSize[13],
                lineHeight: designTokens.lineHeight.normal,
              }}
            >
              {keyFindings.map((t, i) => (
                <li key={i}>{t}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div style={{ ...headerCardStyle, padding: designTokens.space[4] }}>
        <SectionLead
          eyebrow="Workbench"
          title="归因分析工作台"
          description="先选择归因视图，再阅读对应图表和关键发现；本页消费后端归因 read model，不在前端补算正式损益。"
          testId="pnl-attribution-workbench-lead"
        />
        <FilterBar style={{ ...tabBarStyle, marginTop: designTokens.space[4] }}>
          <button type="button" style={tabStyle(activeTab === "volume-rate")} onClick={() => setActiveTab("volume-rate")}>
            规模 / 利率效应
          </button>
          <button type="button" style={tabStyle(activeTab === "tpl-market")} onClick={() => setActiveTab("tpl-market")}>
            TPL 市场相关性
          </button>
          <button type="button" style={tabStyle(activeTab === "composition")} onClick={() => setActiveTab("composition")}>
            损益构成
          </button>
          <button
            type="button"
            style={tabStyle(activeTab === "advanced", "advanced")}
            onClick={() => setActiveTab("advanced")}
          >
            高级归因 + Campisi
          </button>
          {activeTab === "volume-rate" && (
            <div style={{ marginLeft: "auto", display: "flex", gap: designTokens.space[2] }}>
              <button
                type="button"
                style={tabStyle(compareType === "mom")}
                onClick={() => setCompareType("mom")}
              >
                环比
              </button>
              <button
                type="button"
                style={tabStyle(compareType === "yoy")}
                onClick={() => setCompareType("yoy")}
              >
                同比
              </button>
            </div>
          )}
        </FilterBar>
      </div>

      <SectionLead
        eyebrow="Analysis"
        title="当前归因视图"
        description="下方内容随 tab 切换，保留现有 volume-rate、TPL market、composition、advanced + Campisi 数据边界。"
        testId="pnl-attribution-current-view-lead"
      />

      {currentViewMeta ? (
        <div data-testid="pnl-attribution-current-view-meta" style={metaStripStyle}>
          <div style={metaCellStyle}>
            <span style={metaLabelStyle}>{currentViewDate.label}</span>
            <span style={metaValueStyle}>{currentViewDate.value}</span>
          </div>
          <div style={metaCellStyle}>
            <span style={metaLabelStyle}>generated_at</span>
            <span style={metaValueStyle}>{currentViewMeta.generated_at}</span>
          </div>
          <div style={metaCellStyle}>
            <span style={metaLabelStyle}>quality_flag</span>
            <span style={metaValueStyle}>{currentViewMeta.quality_flag}</span>
          </div>
          <div style={metaCellStyle}>
            <span style={metaLabelStyle}>fallback_mode</span>
            <span style={metaValueStyle}>{currentViewMeta.fallback_mode}</span>
          </div>
        </div>
      ) : null}

      {activeTab === "advanced" ? (
        <div data-testid="pnl-attribution-advanced-view-meta" style={metaStripStyle}>
          {advancedMetaRows.map(([title, meta]) => (
            <div key={title} style={metaCellStyle}>
              <span style={metaLabelStyle}>{title}</span>
              <span style={metaValueStyle}>
                {meta
                  ? `${meta.quality_flag} · ${meta.fallback_mode} · ${meta.generated_at}`
                  : loading
                    ? "加载中…"
                    : "—"}
              </span>
            </div>
          ))}
        </div>
      ) : null}

      {activeTab === "volume-rate" && volumeRateData && !loading && !error ? (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: designTokens.space[3],
          }}
        >
          <div style={{ ...headerCardStyle, padding: designTokens.space[4] }}>
            <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.neutral[700] }}>当期损益</div>
            <div
              style={{
                fontSize: designTokens.fontSize[20],
                fontWeight: 700,
                color: designTokens.color.neutral[900],
                ...tabularNumsStyle,
              }}
            >
              {formatYiNumeric(volumeRateData.total_current_pnl)}
            </div>
            <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.neutral[500] }}>
              {volumeRateData.current_period}
            </div>
          </div>
          {volumeRateData.has_previous_data && (
            <>
              <div style={{ ...headerCardStyle, padding: designTokens.space[4] }}>
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.neutral[700] }}>上期损益</div>
                <div
                  style={{
                    fontSize: designTokens.fontSize[20],
                    fontWeight: 700,
                    color: designTokens.color.neutral[900],
                    ...tabularNumsStyle,
                  }}
                >
                  {formatYiNumeric(volumeRateData.total_previous_pnl)}
                </div>
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.neutral[500] }}>
                  {volumeRateData.previous_period}
                </div>
              </div>
              <div
                style={{
                  ...headerCardStyle,
                  padding: designTokens.space[4],
                  background: designTokens.color.success[50],
                  borderColor: designTokens.color.success[200],
                }}
              >
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.semantic.profit }}>
                  规模效应
                </div>
                <div
                  style={{
                    fontSize: designTokens.fontSize[20],
                    fontWeight: 700,
                    color:
                      (numericRaw(volumeRateData.total_volume_effect) ?? 0) >= 0
                        ? designTokens.color.semantic.profit
                        : designTokens.color.semantic.loss,
                    ...tabularNumsStyle,
                  }}
                >
                  {formatYiNumeric(volumeRateData.total_volume_effect)}
                </div>
              </div>
              <div
                style={{
                  ...headerCardStyle,
                  padding: designTokens.space[4],
                  background: designTokens.color.info[50],
                  borderColor: designTokens.color.info[200],
                }}
              >
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.info[600] }}>利率效应</div>
                <div
                  style={{
                    fontSize: designTokens.fontSize[20],
                    fontWeight: 700,
                    color:
                      (numericRaw(volumeRateData.total_rate_effect) ?? 0) >= 0
                        ? designTokens.color.info[600]
                        : designTokens.color.warning[600],
                    ...tabularNumsStyle,
                  }}
                >
                  {formatYiNumeric(volumeRateData.total_rate_effect)}
                </div>
              </div>
              <div
                style={{
                  ...headerCardStyle,
                  padding: designTokens.space[4],
                  background: designTokens.color.primary[100],
                  borderColor: designTokens.color.primary[200],
                }}
              >
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.primary[700] }}>
                  损益变动
                </div>
                <div
                  style={{
                    fontSize: designTokens.fontSize[20],
                    fontWeight: 700,
                    color:
                      (numericRaw(volumeRateData.total_pnl_change) ?? 0) >= 0
                        ? designTokens.color.semantic.profit
                        : designTokens.color.semantic.loss,
                    ...tabularNumsStyle,
                  }}
                >
                  {formatYiNumeric(volumeRateData.total_pnl_change)}
                </div>
              </div>
            </>
          )}
        </div>
      ) : null}

      {activeTab === "volume-rate" ? (
        <>
          <AttributionWaterfallChart
            data={volumeRateData}
            state={waterfallState}
            onRetry={() => void loadData()}
          />
          <VolumeRateAnalysisChart
            data={volumeRateData}
            state={volumeRateState}
            onRetry={() => void loadData()}
          />
        </>
      ) : null}

      {activeTab === "tpl-market" ? (
        <TPLMarketChart
          data={tplMarketData}
          state={tplMarketState}
          onRetry={() => void loadData()}
        />
      ) : null}

      {activeTab === "composition" ? (
        <PnLCompositionChart
          data={compositionData}
          state={compositionState}
          onRetry={() => void loadData()}
        />
      ) : null}

      {activeTab === "advanced" ? (
        <>
          <CampisiAttributionPanel
            data={campisiFourEffects ?? campisiData}
            state={campisiFourState}
            onRetry={() => void loadData()}
          />
          <CampisiEnhancedPanel data={campisiEnhanced} state={campisiEnhancedState} onRetry={() => void loadData()} />
          <CampisiMaturityBucketPanel
            data={campisiMaturityBuckets}
            state={campisiMaturityState}
            onRetry={() => void loadData()}
          />
          <AdvancedAttributionChart
            carryData={carryRollDownData}
            spreadData={spreadData}
            krdData={krdData}
            summaryData={advancedSummary}
            state={advancedCarryState}
            onRetry={() => void loadData()}
          />
        </>
      ) : null}
    </div>
  );
}
