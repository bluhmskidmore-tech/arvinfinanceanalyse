import type { EnvFactorDetailRow, EnvFactorTone } from "../lib/envScoreFactorDetail";
import styles from "./EnvScoreFactorDetailPanel.module.css";

const UI = {
  eyebrow: "环境评分",
  title: "贡献因子明细",
  methodPrefix: "评分方法",
  defaultMethod: "待定",
  hintNote: "正值偏紧（不利债市），负值偏松；Δ 为窗口内序列变化量。",
  loading: "加载中…",
  empty: "当前没有可用的环境评分贡献因子明细。",
  columns: {
    category: "类别",
    series: "序列",
    window: "窗口",
    delta: "Δ",
    score: "评分",
    weight: "权重",
  },
} as const;

const CHIP_CLASS_BY_CATEGORY: Record<string, string> = {
  rate: styles.chipRate,
  liquidity: styles.chipLiquidity,
  growth: styles.chipGrowth,
  inflation: styles.chipInflation,
};

function toneValueClass(tone: EnvFactorTone): string {
  if (tone === "pos") return styles.valuePos;
  if (tone === "neg") return styles.valueNeg;
  return styles.valueNeu;
}

function deltaTone(delta: number | null): EnvFactorTone {
  if (delta == null || delta === 0) return "neu";
  return delta > 0 ? "pos" : "neg";
}

function formatWeight(weight: number | null): string {
  return weight == null ? "—" : weight.toFixed(1);
}

export function EnvScoreFactorDetailPanel({
  rows,
  scoringMethod,
  loading = false,
}: {
  rows: EnvFactorDetailRow[];
  scoringMethod?: string;
  loading?: boolean;
}) {
  const methodLabel = scoringMethod?.trim() || UI.defaultMethod;

  return (
    <section className={styles.panel} data-testid="env-score-factor-detail-panel" aria-label="环境评分贡献因子明细">
      <div className={styles.head}>
        <div>
          <div className={styles.eyebrow}>{UI.eyebrow}</div>
          <h2 className={styles.title}>{UI.title}</h2>
        </div>
        <span className={styles.method} title={methodLabel}>
          {UI.methodPrefix} {methodLabel}
        </span>
      </div>
      <p className={styles.hint}>
        {UI.methodPrefix} {methodLabel}；{UI.hintNote}
      </p>
      {loading && rows.length === 0 ? (
        <div className={styles.empty} data-testid="env-score-factor-detail-loading">{UI.loading}</div>
      ) : rows.length === 0 ? (
        <div className={styles.empty} data-testid="env-score-factor-detail-empty">{UI.empty}</div>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>{UI.columns.category}</th>
                <th>{UI.columns.series}</th>
                <th className={styles.num}>{UI.columns.window}</th>
                <th className={styles.num}>{UI.columns.delta}</th>
                <th className={styles.num}>{UI.columns.score}</th>
                <th className={styles.num}>{UI.columns.weight}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${row.category}-${row.seriesName}-${index}`} data-testid="env-score-factor-detail-row">
                  <td>
                    <span className={`${styles.chip} ${CHIP_CLASS_BY_CATEGORY[row.category] ?? ""}`}>
                      {row.categoryLabel}
                    </span>
                  </td>
                  <td className={styles.series} title={row.seriesName}>{row.seriesName}</td>
                  <td className={styles.num}>{row.windowLabel}</td>
                  <td className={`${styles.num} ${toneValueClass(deltaTone(row.delta))}`}>{row.deltaLabel}</td>
                  <td
                    className={`${styles.num} ${toneValueClass(row.tone)}`}
                    title={row.observationCount != null ? `样本数 ${row.observationCount}` : undefined}
                  >
                    {row.scoreLabel}
                  </td>
                  <td className={styles.num}>{formatWeight(row.weight)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
