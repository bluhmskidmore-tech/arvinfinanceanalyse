import type { MacroBondLinkageEnvironmentScore } from "../../../api/contracts";
import type { WaterfallBar } from "../lib/crossAssetAnalytics";
import {
  formatWaterfallContributingFactorName,
  formatWaterfallContributingFactorSummary,
} from "../lib/crossAssetLinkageLabels";

type WaterfallEvidenceStatus = "ready" | "neutral" | "missing" | "total";

const WATERFALL_FACTOR_CATEGORY: Record<string, string> = {
  liquidity: "liquidity",
  rate: "rate",
  growth: "growth",
  inflation: "inflation",
};

const WATERFALL_MISSING_REASON: Record<string, string> = {
  liquidity: "SHIBOR/回购等流动性序列历史样本不足，后端未形成流动性贡献。",
  growth: "工业增加值/GDP 等增长序列历史样本不足，后端未形成增长贡献。",
  inflation: "通胀序列缺少可用最新点，后端未形成通胀贡献。",
  rate: "利率期限序列历史样本不足，后端未形成利率贡献。",
};

function factorTextValue(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : null;
}

function waterfallFactorEvidence(
  bar: WaterfallBar,
  env: Partial<MacroBondLinkageEnvironmentScore>,
): { status: WaterfallEvidenceStatus; label: string; reason: string } {
  if (bar.kind === "total") {
    return {
      status: "total",
      label: "综合",
      reason: "综合分由后端按利率、流动性、增长、通胀权重汇总；正值代表债券不利压力。",
    };
  }

  const category = WATERFALL_FACTOR_CATEGORY[bar.key] ?? bar.key;
  const factors = (env.contributing_factors ?? []).filter((factor) => String(factor.category ?? "") === category);
  const hasEvidence = factors.length > 0;
  const isFlat = Math.abs(bar.value) < 0.005;

  if (!hasEvidence && isFlat) {
    return {
      status: "missing",
      label: "样本不足",
      reason: WATERFALL_MISSING_REASON[category] ?? "该因子暂无贡献明细，当前按 0 展示。",
    };
  }

  if (isFlat) {
    const factor = factors[0];
    const latestValue = factorTextValue(factor?.latest_value);
    const factorSeriesName = typeof factor?.series_name === "string" ? factor.series_name : null;
    const seriesName = formatWaterfallContributingFactorName(factorSeriesName, category);
    return {
      status: "neutral",
      label: "中性",
      reason: latestValue
        ? `${seriesName} 最新值 ${latestValue}，规则判为中性贡献 0。`
        : `${bar.label} 有有效输入，但标准化后贡献接近 0。`,
    };
  }

  const factorCount = factors.length;
  const factorSummary = formatWaterfallContributingFactorSummary(factors);
  return {
    status: "ready",
    label: factorCount > 0 ? `${factorCount} 项证据` : "有分值",
    reason:
      factorCount > 0
        ? `${factorSummary} 已进入环境评分，${bar.label} 贡献 ${bar.value.toFixed(2)}。`
        : `${bar.label} 接口返回了分值，但未展开贡献因子明细。`,
  };
}

export function DriverWaterfallPanel({
  bars,
  env,
}: {
  bars: WaterfallBar[];
  env: Partial<MacroBondLinkageEnvironmentScore>;
}) {
  if (bars.length === 0) return null;

  const maxAbs = Math.max(...bars.map((b) => Math.abs(b.value)), 0.01);
  const evidenceRows = bars.map((bar) => ({ bar, evidence: waterfallFactorEvidence(bar, env) }));
  const factorRows = evidenceRows.filter(({ bar }) => bar.kind !== "total");
  const activeRows = factorRows.filter(({ evidence }) => evidence.status === "ready");
  const gapRows = factorRows.filter(({ evidence }) => evidence.status === "missing" || evidence.status === "neutral");
  const totalRow = evidenceRows.find(({ evidence }) => evidence.status === "total");
  const compactGapMode = factorRows.length > 0 && gapRows.length >= Math.min(factorRows.length, 3) && activeRows.length <= 1;
  const chartHeight = compactGapMode ? 72 : 120;
  const gapStripClassName = `ca-waterfall__evidence-strip ${
    gapRows.length <= 2 ? "ca-waterfall__evidence-strip--compact" : "ca-waterfall__evidence-strip--grid"
  }`;
  const dominantRow = activeRows.reduce<(typeof activeRows)[number] | null>((winner, row) => {
    if (!winner) return row;
    return Math.abs(row.bar.value) > Math.abs(winner.bar.value) ? row : winner;
  }, null);
  const netValue = totalRow?.bar.value ?? 0;
  const netSign = netValue > 0 ? "+" : "";
  const netTone = netValue > 0.005 ? "positive" : netValue < -0.005 ? "negative" : "neutral";

  return (
    <section className="ca-waterfall" data-testid="cross-asset-driver-waterfall">
      <h2 className="ca-waterfall__title">驱动力归因瀑布</h2>
      <p className="ca-waterfall__subtitle">
        环境综合评分由后端贡献项累加构成，正值偏紧，负值偏松。
      </p>
      <div className="ca-waterfall__decision" data-testid="cross-asset-driver-waterfall-decision">
        <div className={`ca-waterfall__decision-card ca-waterfall__decision-card--${netTone}`}>
          <span>综合方向</span>
          <strong>{`${netSign}${netValue.toFixed(2)}`}</strong>
          <small>{netTone === "positive" ? "偏紧/不利债市" : netTone === "negative" ? "偏松/利好债市" : "方向中性"}</small>
        </div>
        <div className="ca-waterfall__decision-card">
          <span>主导因子</span>
          <strong>{dominantRow?.bar.label ?? "暂无"}</strong>
          <small>{dominantRow ? `${dominantRow.bar.value > 0 ? "+" : ""}${dominantRow.bar.value.toFixed(2)}` : "等待有效贡献"}</small>
        </div>
        <div className="ca-waterfall__decision-card">
          <span>证据状态</span>
          <strong>{`${activeRows.length}/${factorRows.length}`}</strong>
          <small>{gapRows.length > 0 ? `${gapRows.length} 项中性或待补` : "因子已形成贡献"}</small>
        </div>
      </div>
      {compactGapMode ? (
        <div className="ca-waterfall__gap-summary" data-testid="cross-asset-driver-waterfall-gap-summary">
          <span>证据缺口</span>
          <strong>{`${gapRows.length} 项待补`}</strong>
          <p>{gapRows.map(({ bar }) => bar.label).join("、")} 当前按 0 参与汇总，明细保留在下方证据条。</p>
        </div>
      ) : null}
      <div className={`ca-waterfall__chart${compactGapMode ? " ca-waterfall__chart--compact-gaps" : ""}`}>
        <div className="ca-waterfall__zero-line" />
        {evidenceRows.map(({ bar, evidence }) => {
          const barHeight = Math.max(4, (Math.abs(bar.value) / maxAbs) * (chartHeight / 2));
          const isNeg = bar.value < 0;
          const isTotal = bar.kind === "total";
          const sign = bar.value > 0 ? "+" : "";
          const valueLabel = evidence.status === "missing" ? "缺数据" : `${sign}${bar.value.toFixed(2)}`;
          const suppressGapBarMeta =
            compactGapMode && !isTotal && (evidence.status === "missing" || evidence.status === "neutral");

          return (
            <div key={bar.key} className={`ca-waterfall__bar-group ca-waterfall__bar-group--${evidence.status}`}>
              <div
                className={`ca-waterfall__bar${isNeg ? " ca-waterfall__bar--negative" : ""}${isTotal ? " ca-waterfall__bar--total" : ""}`}
                style={{
                  height: `${barHeight}px`,
                  background: bar.color,
                  marginBottom: isNeg ? "auto" : undefined,
                  marginTop: isNeg ? undefined : "auto",
                }}
                title={`${bar.label}: ${valueLabel}；${evidence.reason}`}
              >
                {!suppressGapBarMeta ? (
                  <span className={`ca-waterfall__bar-value ${isNeg ? "ca-waterfall__bar-value--below" : "ca-waterfall__bar-value--above"}`}>
                    {valueLabel}
                  </span>
                ) : null}
                <span className="ca-waterfall__bar-label">{bar.label}</span>
                {!suppressGapBarMeta ? (
                  <span className={`ca-waterfall__bar-status ca-waterfall__bar-status--${evidence.status}`}>
                    {evidence.label}
                  </span>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
      <div className="ca-waterfall__evidence" data-testid="cross-asset-driver-waterfall-evidence">
        {evidenceRows
          .filter(({ evidence }) => evidence.status === "ready" || evidence.status === "total")
          .map(({ bar, evidence }) => (
            <div key={`evidence-${bar.key}`} className={`ca-waterfall__evidence-item ca-waterfall__evidence-item--${evidence.status}`}>
              <span>{bar.label}</span>
              <strong>{evidence.label}</strong>
              <p>{evidence.reason}</p>
            </div>
          ))}
        {gapRows.length > 0 ? (
          <div className={gapStripClassName} data-testid="cross-asset-driver-waterfall-gap-strip">
            {gapRows.map(({ bar, evidence }) => (
              <span key={`gap-${bar.key}`} className={`ca-waterfall__evidence-chip ca-waterfall__evidence-chip--${evidence.status}`} title={evidence.reason}>
                <strong>{bar.label}</strong>
                {evidence.label}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}
