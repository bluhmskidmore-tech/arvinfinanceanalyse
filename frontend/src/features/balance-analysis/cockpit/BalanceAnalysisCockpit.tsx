import type { ReactNode } from "react";
import {
  AuditOutlined,
  BarChartOutlined,
  BuildOutlined,
  FileTextOutlined,
  InfoCircleOutlined,
  LineChartOutlined,
  PieChartOutlined,
  SafetyCertificateOutlined,
  TeamOutlined,
} from "@ant-design/icons";

import { BalanceBottomRow } from "../components/BalanceBottomRow";
import { BalanceContributionRow } from "../components/BalanceContributionRow";
import { BalanceSummaryRow } from "../components/BalanceSummaryRow";
import type { BalanceHeadlineCard } from "../pages/balanceAnalysisPageModel";
import type {
  BalanceCockpitViewModel,
  BalanceStageRealDataModel,
} from "../pages/balanceAnalysisPageModel";
import dhStyles from "../../workbench/dashboard-home/dashboardHome.module.css";
import styles from "./balanceAnalysisCockpit.module.css";
import toolbarStyles from "./balanceAnalysisToolbar.module.css";

type BalanceAnalysisCockpitProps = {
  model: BalanceCockpitViewModel;
  stageModel: BalanceStageRealDataModel;
  headlineCards: BalanceHeadlineCard[];
};

const workbookIcons: Record<string, ReactNode> = {
  bond_business_types: <PieChartOutlined aria-hidden />,
  rating_analysis: <SafetyCertificateOutlined aria-hidden />,
  maturity_gap: <BarChartOutlined aria-hidden />,
  issuance_business_types: <FileTextOutlined aria-hidden />,
  industry_distribution: <BuildOutlined aria-hidden />,
  rate_distribution: <LineChartOutlined aria-hidden />,
  counterparty_types: <TeamOutlined aria-hidden />,
  decision_items: <AuditOutlined aria-hidden />,
};

function MiniDonut({ pct }: { pct: number }) {
  const clamped = Math.max(0, Math.min(100, pct));
  const radius = 14;
  const circumference = 2 * Math.PI * radius;
  const dash = (clamped / 100) * circumference;
  return (
    <svg width={36} height={36} viewBox="0 0 36 36" aria-hidden>
      <circle cx={18} cy={18} r={radius} fill="none" stroke="#e2e8f0" strokeWidth={5} />
      <circle
        cx={18}
        cy={18}
        r={radius}
        fill="none"
        stroke="#1850a1"
        strokeWidth={5}
        strokeDasharray={`${dash} ${circumference}`}
        transform="rotate(-90 18 18)"
      />
    </svg>
  );
}

function scrollToPanel(panelId: string) {
  const target =
    document.querySelector(`[data-testid="${panelId}"]`) ?? document.getElementById(panelId);
  target?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function KpiCard({ kpi }: { kpi: BalanceCockpitViewModel["scaleKpis"][number] }) {
  return (
    <article className={`${dhStyles.dhCard} ${dhStyles.dhTerminalKpi}`}>
      <div className={dhStyles.dhTerminalKpiTop}>
        <span>{kpi.label}</span>
      </div>
      {kpi.variant === "donut" ? (
        <div className={toolbarStyles.baKpiDonutWrap}>
          <MiniDonut pct={kpi.donutPct ?? 0} />
          <div className={`${dhStyles.dhTerminalKpiValue} ${dhStyles.dhNum}`}>
            {kpi.value}
            {kpi.unit ? <small>{kpi.unit}</small> : null}
          </div>
        </div>
      ) : (
        <div className={`${dhStyles.dhTerminalKpiValue} ${dhStyles.dhNum}`}>
          {kpi.value}
          {kpi.value !== "—" ? <small>{kpi.unit}</small> : null}
        </div>
      )}
    </article>
  );
}

export default function BalanceAnalysisCockpit({
  model,
  stageModel,
  headlineCards,
}: BalanceAnalysisCockpitProps) {
  return (
    <div className={styles.baCockpitStack} data-testid="balance-workbench">
      <section
        data-testid="balance-analysis-priority-board"
        className={`${dhStyles.dhCard} ${dhStyles.dhTerminalJudgement} ${styles.baJudgementCompact}`}
        aria-label="缺口判断摘要"
      >
        <span className={dhStyles.dhTerminalEyebrow}>首屏结论</span>
        <h2>{model.judgementLine}</h2>
        <div className={styles.baJudgementFoot}>正式口径 · 净头寸与期限缺口</div>
      </section>

      <div data-testid="balance-analysis-cockpit">
        <section className={dhStyles.dhTerminalHero} data-testid="balance-analysis-cockpit-kpis">
          {model.scaleKpis.map((kpi) => (
            <KpiCard key={kpi.key} kpi={kpi} />
          ))}
        </section>

        <section className={styles.baOpsKpiRow} data-testid="balance-analysis-cockpit-ops-kpis">
          {model.opsKpis.map((kpi) => (
            <KpiCard key={kpi.key} kpi={kpi} />
          ))}
        </section>

        <section data-testid="balance-analysis-cockpit-stage" className={styles.baStageSection}>
          <div className={styles.baStageSectionHead}>
            <strong>真实数据读面</strong>
            <span>摘要 · 贡献 · 期限 · 风险</span>
          </div>
          <div className={styles.baStageStack}>
            <BalanceSummaryRow model={stageModel.summary} variant="terminal" />
            <BalanceContributionRow model={stageModel.contribution} variant="terminal" />
            <BalanceBottomRow model={stageModel.bottom} variant="terminal" />
          </div>
        </section>

        <article
          className={`${dhStyles.dhCard} ${dhStyles.dhTerminalPanel}`}
          data-testid="balance-analysis-workbench-grid"
        >
          <div className={dhStyles.dhTerminalPanelHead}>
            <h3>Workbook 分析入口</h3>
            <span className={dhStyles.dhMuted}>{model.workbookSummary}</span>
          </div>
          <div className={styles.baWorkbookBottom}>
            {model.workbookNav.map((item) => (
              <button
                key={item.key}
                type="button"
                className={`${dhStyles.dhCard} ${dhStyles.dhTerminalQuick}`}
                data-testid={`balance-analysis-workbook-nav-${item.key}`}
                onClick={() => scrollToPanel(item.panelId)}
              >
                <span>{workbookIcons[item.key]}</span>
                <b>{item.label}</b>
                <em>跳转</em>
              </button>
            ))}
          </div>
          <p className={styles.baWorkbookNote}>
            <InfoCircleOutlined aria-hidden /> 底稿默认折叠；ADB 预览与高级归因标为「分析面」，不混入正式
            workbook。
          </p>
        </article>
      </div>

      <div data-testid="balance-analysis-overview-cards" className={toolbarStyles.baOverviewCompat} aria-hidden>
        {headlineCards.map((card) => (
          <span key={card.key}>
            {card.label} {card.value}
          </span>
        ))}
      </div>
    </div>
  );
}
