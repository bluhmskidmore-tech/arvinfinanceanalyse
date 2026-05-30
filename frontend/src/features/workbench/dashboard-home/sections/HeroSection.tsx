import type { DashboardHomeView } from "../dashboardHomeView";
import { resolveDeltaClass } from "../dashboardHomeView";
import { HomeSparkline } from "../HomeSparkline";
import styles from "../dashboardHome.module.css";

type HeroSectionProps = {
  aiJudge: DashboardHomeView["aiJudge"];
  coreKpis: DashboardHomeView["coreKpis"];
  riskMinis: DashboardHomeView["riskMinis"];
};

export function HeroSection({ aiJudge, coreKpis, riskMinis }: HeroSectionProps) {
  return (
    <section data-testid="dashboard-home-hero" className={styles.dhHero}>
      <article className={`${styles.dhCard} ${styles.dhAiJudge}`}>
        <div className={styles.dhAiHead}>
          <span className={styles.dhAiMark}>AI</span>
          <span className={styles.dhAiTitle}>今日经营判断</span>
        </div>
        <p className={styles.dhJudgeCopy}>{aiJudge.conclusion}</p>
        <div className={styles.dhHealth}>
          <span>经营健康度</span>
          <span className={styles.dhPillGreen}>{aiJudge.healthLabel}</span>
          <span className={styles.dhBar} aria-hidden="true">
            <i
              className={styles.dhBarFill}
              style={{ width: `${Math.min(100, Math.max(0, aiJudge.healthScore))}%` }}
            />
          </span>
          <b className={styles.dhNum}>{aiJudge.healthScore}</b>
          <span>/ 100</span>
        </div>
        <p className={styles.dhImpact}>{aiJudge.impact}</p>
        <HomeSparkline
          values={aiJudge.sparkline}
          width={460}
          height={56}
          stroke="#2f68b8"
          area
          className={styles.dhJudgeSpark}
        />
      </article>

      <article className={`${styles.dhCard} ${styles.dhCoreBox}`}>
        {coreKpis.map((kpi) => (
          <div key={kpi.id} data-testid={`dashboard-home-kpi-${kpi.id}`} className={styles.dhMetricTile}>
            <div className={styles.dhMetricLabel}>{kpi.label}</div>
            <div className={`${styles.dhMetricValue} ${styles.dhNum}`}>
              {kpi.value}
              {kpi.unit ? <small>{kpi.unit}</small> : null}
            </div>
            <div className={styles.dhChange}>
              <span className={resolveDeltaClass(kpi.deltaTone, styles)}>{kpi.delta}</span>
            </div>
            <HomeSparkline
              values={kpi.sparkline}
              area
              stroke={
                kpi.deltaTone === "down"
                  ? "#2d8a5e"
                  : kpi.deltaTone === "up"
                    ? "#c5162e"
                    : "#1d5fa7"
              }
            />
          </div>
        ))}
      </article>

      <article className={`${styles.dhCard} ${styles.dhRiskConstraint}`}>
        <div className={styles.dhRiskTitle}>风险约束</div>
        <div className={styles.dhRiskGrid}>
          {riskMinis.map((mini) => (
            <div key={mini.id} className={styles.dhRiskMini}>
              <div className={styles.dhRiskMiniLabel}>{mini.label}</div>
              <div className={`${styles.dhRiskMiniValue} ${styles.dhNum}`}>
                {mini.value}
                {mini.unit ? <small> {mini.unit}</small> : null}
              </div>
              <div
                className={`${styles.dhRiskMiniFoot} ${resolveDeltaClass(mini.footTone, styles)}`}
              >
                {mini.foot}
              </div>
            </div>
          ))}
        </div>
      </article>
    </section>
  );
}
