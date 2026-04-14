import { useCallback, useEffect, useState } from "react";

import { useApiClient } from "../../../api/client";
import type {
  AdvancedAttributionSummary,
  CampisiAttributionPayload,
  CarryRollDownPayload,
  KRDAttributionPayload,
  PnlAttributionAnalysisSummary,
  PnlCompositionPayload,
  SpreadAttributionPayload,
  TPLMarketCorrelationPayload,
  VolumeRateAttributionPayload,
} from "../../../api/contracts";
import { AdvancedAttributionChart } from "./AdvancedAttributionChart";
import { AttributionWaterfallChart } from "./AttributionWaterfallChart";
import { CampisiAttributionPanel } from "./CampisiAttributionPanel";
import { PnLCompositionChart } from "./PnLCompositionChart";
import { TPLMarketChart } from "./TPLMarketChart";
import { VolumeRateAnalysisChart } from "./VolumeRateAnalysisChart";

const shellStyle = {
  display: "flex",
  flexDirection: "column" as const,
  gap: 20,
};

const headerCardStyle = {
  padding: 20,
  borderRadius: 16,
  border: "1px solid #e4ebf5",
  background: "#ffffff",
  boxShadow: "0 8px 24px rgba(19, 37, 70, 0.06)",
} as const;

const tabBarStyle = {
  display: "flex",
  flexWrap: "wrap" as const,
  gap: 8,
  alignItems: "center",
};

function tabStyle(active: boolean, variant: "default" | "advanced" = "default") {
  const base = {
    padding: "10px 16px",
    borderRadius: 12,
    fontWeight: 600,
    fontSize: 14,
    cursor: "pointer",
    border: "1px solid",
  } as const;
  if (variant === "advanced") {
    return {
      ...base,
      borderColor: active ? "#6d3bb3" : "#e4d6fb",
      background: active ? "#6d3bb3" : "#f6f0ff",
      color: active ? "#ffffff" : "#6d3bb3",
    };
  }
  return {
    ...base,
    borderColor: active ? "#1f5eff" : "#d7dfea",
    background: active ? "#edf3ff" : "#ffffff",
    color: active ? "#1f5eff" : "#162033",
  };
}

function formatYi(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const yi = value / 100_000_000;
  return `${yi >= 0 ? "+" : ""}${yi.toFixed(2)} 亿`;
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

  const [carryRollDownData, setCarryRollDownData] = useState<CarryRollDownPayload | null>(null);
  const [spreadData, setSpreadData] = useState<SpreadAttributionPayload | null>(null);
  const [krdData, setKrdData] = useState<KRDAttributionPayload | null>(null);
  const [advancedSummary, setAdvancedSummary] = useState<AdvancedAttributionSummary | null>(null);
  const [campisiData, setCampisiData] = useState<CampisiAttributionPayload | null>(null);

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
        setSummaryData(summary.result);
      } else if (activeTab === "tpl-market") {
        const data = await client.getTplMarketCorrelation({ months: 12 });
        setTplMarketData(data.result);
      } else if (activeTab === "composition") {
        const data = await client.getPnlCompositionBreakdown({
          reportDate,
          includeTrend: true,
          trendMonths: 6,
        });
        setCompositionData(data.result);
      } else {
        const [carry, spread, krd, summary, campisi] = await Promise.all([
          client.getPnlCarryRollDown(reportDate),
          client.getPnlSpreadAttribution({ reportDate, lookbackDays: 30 }),
          client.getPnlKrdAttribution({ reportDate, lookbackDays: 30 }),
          client.getPnlAdvancedAttributionSummary(reportDate),
          client.getPnlCampisiAttribution({ lookbackDays: 30 }),
        ]);
        setCarryRollDownData(carry.result);
        setSpreadData(spread.result);
        setKrdData(krd.result);
        setAdvancedSummary(summary.result);
        setCampisiData(campisi.result);
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

  return (
    <div style={shellStyle}>
      <div style={headerCardStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "#162033" }}>损益归因分析</h2>
            <p style={{ margin: "8px 0 0", fontSize: 13, color: "#5c6b82", maxWidth: 640, lineHeight: 1.6 }}>
              规模/利率一阶与交叉效应、TPL 与市场、损益构成，以及 Carry–Roll、利差、KRD 与 Campisi
              四效应（收入、国债、利差、选择）对照阅读。
            </p>
          </div>
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

        {keyFindings.length > 0 && (
          <div
            style={{
              marginTop: 16,
              padding: 16,
              borderRadius: 12,
              border: "1px solid",
              borderColor: activeTab === "advanced" ? "#e4d6fb" : "#f1d3b5",
              background: activeTab === "advanced" ? "#f6f0ff" : "#fff4e8",
            }}
          >
            <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 8, color: "#162033" }}>
              {activeTab === "advanced" ? "高级归因要点" : "关键发现"}
            </div>
            <ul style={{ margin: 0, paddingLeft: 18, color: "#5c6b82", fontSize: 13, lineHeight: 1.6 }}>
              {keyFindings.map((t, i) => (
                <li key={i}>{t}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div style={{ ...headerCardStyle, padding: 16 }}>
        <div style={tabBarStyle}>
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
            <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
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
        </div>
      </div>

      {error && (
        <div
          style={{
            ...headerCardStyle,
            borderColor: "#f5c2c2",
            background: "#fef2f2",
            color: "#b91c1c",
          }}
        >
          加载失败：{error}
        </div>
      )}

      {loading && (
        <div style={{ ...headerCardStyle, textAlign: "center", color: "#5c6b82" }}>加载中…</div>
      )}

      {!loading && !error && activeTab === "volume-rate" && volumeRateData ? (
        <>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: 12,
            }}
          >
            <div style={{ ...headerCardStyle, padding: 16 }}>
              <div style={{ fontSize: 12, color: "#5c6b82" }}>当期损益</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: "#162033" }}>{formatYi(volumeRateData.total_current_pnl)}</div>
              <div style={{ fontSize: 12, color: "#94a3b8" }}>{volumeRateData.current_period}</div>
            </div>
            {volumeRateData.has_previous_data && (
              <>
                <div style={{ ...headerCardStyle, padding: 16 }}>
                  <div style={{ fontSize: 12, color: "#5c6b82" }}>上期损益</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: "#162033" }}>
                    {formatYi(volumeRateData.total_previous_pnl)}
                  </div>
                  <div style={{ fontSize: 12, color: "#94a3b8" }}>{volumeRateData.previous_period}</div>
                </div>
                <div style={{ ...headerCardStyle, padding: 16, background: "#e8f6ee", borderColor: "#c8e8d5" }}>
                  <div style={{ fontSize: 12, color: "#15803d" }}>规模效应</div>
                  <div
                    style={{
                      fontSize: 20,
                      fontWeight: 700,
                      color: (volumeRateData.total_volume_effect ?? 0) >= 0 ? "#15803d" : "#b91c1c",
                    }}
                  >
                    {formatYi(volumeRateData.total_volume_effect)}
                  </div>
                </div>
                <div style={{ ...headerCardStyle, padding: 16, background: "#edf3ff", borderColor: "#cddcff" }}>
                  <div style={{ fontSize: 12, color: "#1f5eff" }}>利率效应</div>
                  <div
                    style={{
                      fontSize: 20,
                      fontWeight: 700,
                      color: (volumeRateData.total_rate_effect ?? 0) >= 0 ? "#1f5eff" : "#b35a16",
                    }}
                  >
                    {formatYi(volumeRateData.total_rate_effect)}
                  </div>
                </div>
                <div style={{ ...headerCardStyle, padding: 16, background: "#f6f0ff", borderColor: "#e4d6fb" }}>
                  <div style={{ fontSize: 12, color: "#6d3bb3" }}>损益变动</div>
                  <div
                    style={{
                      fontSize: 20,
                      fontWeight: 700,
                      color: (volumeRateData.total_pnl_change ?? 0) >= 0 ? "#15803d" : "#b91c1c",
                    }}
                  >
                    {formatYi(volumeRateData.total_pnl_change)}
                  </div>
                </div>
              </>
            )}
          </div>
          <AttributionWaterfallChart data={volumeRateData} />
          <VolumeRateAnalysisChart data={volumeRateData} />
        </>
      ) : null}

      {!loading && !error && activeTab === "volume-rate" && !volumeRateData && (
        <div style={{ ...headerCardStyle, color: "#5c6b82" }}>暂无规模/利率归因数据。</div>
      )}

      {!loading && !error && activeTab === "tpl-market" && (
        <TPLMarketChart data={tplMarketData} />
      )}

      {!loading && !error && activeTab === "composition" && (
        <PnLCompositionChart data={compositionData} />
      )}

      {!loading && !error && activeTab === "advanced" && (
        <>
          <CampisiAttributionPanel data={campisiData} />
          <AdvancedAttributionChart
            carryData={carryRollDownData}
            spreadData={spreadData}
            krdData={krdData}
          />
        </>
      )}
    </div>
  );
}
