import { Link } from "react-router-dom";

import dhStyles from "../dashboard-home/dashboardHome.module.css";
import { MarketHomeKpiSparkline } from "./MarketHomeKpiSparkline";
import type { MarketChangeDirection } from "./marketHomeChangeTone";
import type { MarketCrisisExplainComponent, MarketCrisisExplainView, MarketCrisisHistoryPoint } from "./moduleHomeModel";
import marketStyles from "./marketHome.module.css";

type MarketCrisisExplainBandProps = {
  explain: MarketCrisisExplainView | null | undefined;
};

const Z_SCORE_BAR_SCALE = 3;

function zScoreBarWidth(zScore: number | null): number {
  if (zScore === null || !Number.isFinite(zScore)) {
    return 0;
  }
  return Math.min(100, Math.round((Math.abs(zScore) / Z_SCORE_BAR_SCALE) * 100));
}

function formatSignedDelta(value: number | null, digits = 2): string | null {
  if (value === null || !Number.isFinite(value)) {
    return null;
  }
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(digits)}`;
}

function CrisisComponentBar({ component }: { component: MarketCrisisExplainComponent }) {
  const width = zScoreBarWidth(component.zScore);
  const direction = component.zScore === null ? "neutral" : component.zScore >= 0 ? "up" : "down";
  const weightLabel =
    component.weight !== null ? `${Math.round(component.weight * 100)}%` : null;
  const rawLabel =
    component.rawValue !== null ? `raw ${component.rawValue.toFixed(2)}` : null;

  return (
    <div className={marketStyles.marketCrisisZBarRow} data-testid={`module-home-market-crisis-component-${component.key}`}>
      <div className={marketStyles.marketCrisisZBarLabelCol}>
        <span className={marketStyles.marketCrisisZBarLabel}>{component.label}</span>
        {weightLabel || rawLabel ? (
          <em className={marketStyles.marketCrisisZBarMeta}>
            {[weightLabel ? `权重 ${weightLabel}` : null, rawLabel].filter(Boolean).join(" · ")}
          </em>
        ) : null}
      </div>
      <div className={marketStyles.marketCrisisZBarTrack} aria-hidden="true">
        <span
          className={marketStyles.marketCrisisZBarFill}
          data-direction={direction}
          style={{ width: `${width}%` }}
        />
      </div>
      <strong className={`${dhStyles.dhNum} ${marketStyles.marketCrisisZBarValue}`}>
        {component.zScore === null ? "—" : component.zScore.toFixed(2)}
      </strong>
    </div>
  );
}

function trendChangeDirection(values: readonly number[]): MarketChangeDirection | undefined {
  if (values.length < 2) {
    return undefined;
  }
  const first = values[0];
  const last = values[values.length - 1];
  if (first === undefined || last === undefined) {
    return undefined;
  }
  if (last > first) {
    return "up";
  }
  if (last < first) {
    return "down";
  }
  return "flat";
}

function CrisisTrendPanel({
  title,
  history,
  tone,
  valueKey,
  testId,
}: {
  title: string;
  history: MarketCrisisHistoryPoint[];
  tone: MarketCrisisExplainView["tone"];
  valueKey: "crisisScore" | "percentile";
  testId: string;
}) {
  const values = history
    .map((point) => point[valueKey])
    .filter((value): value is number => value !== null && Number.isFinite(value));
  const changeDirection = trendChangeDirection(values);
  const firstDate = history[0]?.date ?? "—";
  const lastDate = history[history.length - 1]?.date ?? "—";
  const latest = values[values.length - 1];

  return (
    <div className={marketStyles.marketCrisisTrendBlock} data-testid={testId}>
      <div className={marketStyles.marketCrisisTrendHead}>
        <span>{title}</span>
        <em>
          {firstDate} → {lastDate} · {history.length} 点
        </em>
        {latest !== undefined ? (
          <strong className={`${dhStyles.dhNum} ${marketStyles.marketCrisisTrendLatest}`}>
            {valueKey === "percentile" ? `P${latest.toFixed(1)}` : latest.toFixed(2)}
          </strong>
        ) : null}
      </div>
      {values.length >= 2 ? (
        <MarketHomeKpiSparkline
          changeDirection={changeDirection}
          className={marketStyles.marketCrisisTrendSparkline}
          tone={tone}
          values={values}
          variant="ticker"
        />
      ) : (
        <p className={marketStyles.panelEmpty}>历史样本不足。</p>
      )}
    </div>
  );
}

function CrisisPercentileTrack({ percentile }: { percentile: number }) {
  const clamped = Math.max(0, Math.min(100, percentile));

  return (
    <div className={marketStyles.marketCrisisPercentileBlock} data-testid="module-home-market-crisis-percentile">
      <div className={marketStyles.marketCrisisPercentileHead}>
        <span>历史分位</span>
        <strong className={`${dhStyles.dhNum} ${marketStyles.marketCrisisPercentileValue}`}>P{clamped.toFixed(1)}</strong>
      </div>
      <div aria-hidden="true" className={marketStyles.marketCrisisPercentileTrack}>
        <span className={marketStyles.marketCrisisPercentileFill} style={{ width: `${clamped}%` }} />
        <span className={marketStyles.marketCrisisPercentileMarker} style={{ left: `${clamped}%` }} />
      </div>
      <div className={marketStyles.marketCrisisPercentileScale} aria-hidden="true">
        <span>0</span>
        <span>50</span>
        <span>100</span>
      </div>
    </div>
  );
}

function CrisisStatChips({ explain }: { explain: MarketCrisisExplainView }) {
  const chips = [
    explain.crisisScore !== null ? { label: "Score", value: explain.crisisScore.toFixed(2) } : null,
    explain.regime ? { label: "Regime", value: explain.regime } : null,
    explain.percentile !== null ? { label: "分位", value: `P${explain.percentile.toFixed(1)}` } : null,
    explain.availableComponentCount !== null && explain.componentCount !== null
      ? { label: "组件", value: `${explain.availableComponentCount}/${explain.componentCount}` }
      : null,
    formatSignedDelta(explain.scoreDelta) ? { label: "区间ΔScore", value: formatSignedDelta(explain.scoreDelta)! } : null,
    formatSignedDelta(explain.percentileDelta) ? { label: "区间Δ分位", value: formatSignedDelta(explain.percentileDelta)! } : null,
  ].filter(Boolean) as Array<{ label: string; value: string }>;

  if (chips.length === 0) {
    return null;
  }

  return (
    <div className={marketStyles.marketCrisisStatGrid} data-testid="module-home-market-crisis-stat-chips">
      {chips.map((chip) => (
        <div className={marketStyles.marketCrisisStatChip} key={chip.label}>
          <span>{chip.label}</span>
          <strong className={dhStyles.dhNum}>{chip.value}</strong>
        </div>
      ))}
    </div>
  );
}

export function MarketCrisisExplainBand({ explain }: MarketCrisisExplainBandProps) {
  if (!explain) {
    return null;
  }

  const percentileHistory = explain.scoreHistory.filter((point) => point.percentile !== null);

  return (
    <section
      className={`${marketStyles.marketCrisisExplainBand} ${marketStyles.marketDeskPanel}`}
      data-testid="module-home-market-crisis-explain-band"
      data-tone={explain.tone}
    >
      <header className={marketStyles.marketCrisisExplainBandHead}>
        <div>
          <span className={marketStyles.marketSummaryKicker}>MACRO</span>
          <h3 className={marketStyles.marketCrisisExplainBandTitle}>宏观解释 · Crisis Score</h3>
          <p className={marketStyles.marketCrisisExplainSummary}>
            {explain.headline ?? "Crisis Score 组件待返回。"}
          </p>
        </div>
        <Link to="/macro-toolkit" className={marketStyles.marketIbLink}>
          宏观工具 →
        </Link>
      </header>
      <CrisisStatChips explain={explain} />
      {explain.recommendation ? (
        <p className={marketStyles.marketCrisisRecommendation} data-testid="module-home-market-crisis-recommendation">
          {explain.recommendation}
        </p>
      ) : null}
      {explain.percentile !== null ? <CrisisPercentileTrack percentile={explain.percentile} /> : null}
      {explain.scoreHistory.length >= 2 ? (
        <div className={marketStyles.marketCrisisTrendDualGrid}>
          <CrisisTrendPanel
            history={explain.scoreHistory}
            testId="module-home-market-crisis-score-trend"
            title="Score 趋势"
            tone={explain.tone}
            valueKey="crisisScore"
          />
          {percentileHistory.length >= 2 ? (
            <CrisisTrendPanel
              history={percentileHistory}
              testId="module-home-market-crisis-percentile-trend"
              title="分位趋势"
              tone={explain.tone}
              valueKey="percentile"
            />
          ) : null}
        </div>
      ) : null}
      {explain.components.length > 0 ? (
        <div className={marketStyles.marketCrisisZBarGrid}>
          {explain.components.map((component) => (
            <CrisisComponentBar component={component} key={component.key} />
          ))}
        </div>
      ) : (
        <p className={marketStyles.panelEmpty}>Crisis Score 组件尚未返回。</p>
      )}
      {explain.warnings.length > 0 ? (
        <div className={marketStyles.marketCrisisWarnings} data-testid="module-home-market-crisis-warnings">
          {explain.warnings.map(w => {
            const warningText = w === "CREDIT_SPREAD_UNAVAILABLE" ? "信用利差数据不足，已降级降波" :
                               w === "COMMODITY_VOL_UNAVAILABLE" ? "商品降波数据待接入" : w;
            return <span key={w} className={marketStyles.marketCrisisWarningItem}>{warningText}</span>;
          })}
        </div>
      ) : null}
      <p className={marketStyles.marketCrisisExplainMeta} data-testid="module-home-market-commodity-shadow-link">
        商品旁证与影子评估仅供研究，完整口径见{" "}
        <Link to="/macro-toolkit#macro-toolkit-crisis-detail">宏观工具 · Crisis Score</Link>。
      </p>
      {explain.dataStatus ? (
        <footer className={marketStyles.marketCrisisExplainMeta}>数据状态: {explain.dataStatus === "degraded" ? "部分因子降级" : explain.dataStatus === "stale" ? "结果非最新" : explain.dataStatus}</footer>
      ) : null}
    </section>
  );
}
