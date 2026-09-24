import { EM_DASH } from "../../../utils/format";
import { FrontendAnalyticsChip } from "./MomentumAndVolatilityPanels";
import "./CrossAssetHeroPanel.css";

export type CrossAssetHeroPanelProps = {
  /** 首屏一句话结论；null 时按 loading 态降级 */
  conclusion: string | null;
  /** 市场体制标签（identifyMarketRegime 的 label） */
  regimeLabel: string;
  regimeDescription?: string;
  /** 利率方向标签（env.rate_direction 的展示文案） */
  rateDirectionLabel: string;
  /** 报告日（crossAssetDataDate || linkageReportDate） */
  reportDate: string;
  /** 环境综合评分（env.composite_score）；null → EM_DASH */
  compositeScore: number | null;
  loading?: boolean;
};

const UI = {
  eyebrow: "跨资产驱动",
  title: "固收组合决策首屏",
  question: "当前宏观因子正沿哪些传导轴影响固收组合，久期与品种是否该调整？",
  reportDateLabel: "报告日",
  regimeChipPrefix: "体制",
  rateChipPrefix: "利率方向",
  scoreLabel: "环境综合评分",
  scoreHint: "正值偏紧（不利债市），负值偏松",
  loadingConclusion: "正在加载联动分析…",
  fallbackConclusion: "暂无首屏结论，等待联动链路或市场体制判断。",
} as const;

function formatCompositeScore(score: number | null): string {
  if (score == null || Number.isNaN(score)) {
    return EM_DASH;
  }
  const sign = score > 0 ? "+" : "";
  return `${sign}${score.toFixed(2)}`;
}

/**
 * 综合分符号语义（backend core_finance/macro_bond_linkage.py::composite_score）：
 * 正值 = 宏观偏紧（bond-unfavorable pressure，警示红），负值 = 偏松（利好债市，绿）。
 * 与贡献因子明细、驱动力瀑布的「正值偏紧」判据一致。
 */
function scoreTone(score: number | null): "tightening" | "easing" | "neutral" {
  if (score == null || Number.isNaN(score) || score === 0) {
    return "neutral";
  }
  return score > 0 ? "tightening" : "easing";
}

export function CrossAssetHeroPanel({
  conclusion,
  regimeLabel,
  regimeDescription,
  rateDirectionLabel,
  reportDate,
  compositeScore,
  loading = false,
}: CrossAssetHeroPanelProps) {
  const conclusionText = conclusion ?? (loading ? UI.loadingConclusion : UI.fallbackConclusion);
  return (
    <section
      className="cross-asset-hero-panel"
      data-testid="cross-asset-hero-panel"
      aria-label="决策首屏"
      aria-busy={loading || undefined}
    >
      <div className="cross-asset-hero-panel__main">
        <div className="cross-asset-hero-panel__eyebrow">{UI.eyebrow}</div>
        <h1 className="cross-asset-hero-panel__title">{UI.title}</h1>
        <p className="cross-asset-hero-panel__question">{UI.question}</p>
        <p className="cross-asset-hero-panel__conclusion">{conclusionText}</p>
        <div className="cross-asset-hero-panel__meta">
          <span className="cross-asset-hero-panel__meta-item">
            {UI.reportDateLabel} {reportDate || EM_DASH}
          </span>
          <span className="cross-asset-hero-panel__chip" title={regimeDescription}>
            {UI.regimeChipPrefix} {regimeLabel}
          </span>
          {/* 体制由前端 identifyMarketRegime 派生：复用同页统一披露章，不再只靠 title 提示。 */}
          <FrontendAnalyticsChip />
          <span className="cross-asset-hero-panel__chip">
            {UI.rateChipPrefix} {rateDirectionLabel}
          </span>
        </div>
      </div>
      <div className="cross-asset-hero-panel__score">
        <div className="cross-asset-hero-panel__score-label">{UI.scoreLabel}</div>
        <div
          className={`cross-asset-hero-panel__score-value cross-asset-hero-panel__score-value--${scoreTone(compositeScore)}`}
          data-testid="cross-asset-hero-panel-score"
        >
          {formatCompositeScore(compositeScore)}
        </div>
        <div className="cross-asset-hero-panel__score-hint">{UI.scoreHint}</div>
      </div>
    </section>
  );
}
