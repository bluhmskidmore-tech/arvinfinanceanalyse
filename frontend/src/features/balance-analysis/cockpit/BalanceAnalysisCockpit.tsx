import type { ReactNode } from "react";
import {
  AuditOutlined,
  BarChartOutlined,
  BuildOutlined,
  FileTextOutlined,
  LineChartOutlined,
  PieChartOutlined,
  SafetyCertificateOutlined,
  TeamOutlined,
} from "@ant-design/icons";

import { BalanceBottomRow } from "../components/BalanceBottomRow";
import { BalanceContributionRow } from "../components/BalanceContributionRow";
import { BalanceSectionHead } from "../components/BalanceSectionHead";
import { BalanceSummaryRow } from "../components/BalanceSummaryRow";
import type { BalanceHeadlineCard } from "../pages/balanceAnalysisPageModel";
import type {
  BalanceCockpitViewModel,
  BalanceStageRealDataModel,
} from "../pages/balanceAnalysisPageModel";

import { EM_DASH } from "../../../utils/format";
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

function scrollToPanel(panelId: string) {
  const target =
    document.querySelector(`[data-testid="${panelId}"]`) ?? document.getElementById(panelId);
  target?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function KpiCell({ kpi }: { kpi: BalanceCockpitViewModel["scaleKpis"][number] }) {
  return (
    <article className="balance-analysis-kpi-cell">
      <span className="balance-analysis-kpi-cell__label" title={kpi.label}>
        {kpi.label}
      </span>
      <strong className="balance-analysis-kpi-cell__value">
        {kpi.value}
        {kpi.value !== EM_DASH && kpi.unit ? <small>{kpi.unit}</small> : null}
      </strong>
    </article>
  );
}

export default function BalanceAnalysisCockpit({
  model,
  stageModel,
  headlineCards,
}: BalanceAnalysisCockpitProps) {
  return (
    <div className="balance-analysis-stack" data-testid="balance-workbench">
      <div data-testid="balance-analysis-cockpit" className="balance-analysis-stack">
        <section className="balance-analysis-sec">
          <BalanceSectionHead title="当日结论" meta="正式口径 · 净头寸与期限缺口" />
          <section
            data-testid="balance-analysis-priority-board"
            className="balance-analysis-conclusion"
            aria-label="缺口判断摘要"
          >
            <p className="balance-analysis-conclusion__body">{model.judgementLine}</p>
          </section>
          <section
            data-testid="balance-analysis-cockpit-kpis"
            className="balance-analysis-kpi-band"
          >
            {model.scaleKpis.map((kpi) => (
              <KpiCell key={kpi.key} kpi={kpi} />
            ))}
          </section>
          <section
            data-testid="balance-analysis-cockpit-ops-kpis"
            className="balance-analysis-ops-strip"
          >
            {model.opsKpis.map((kpi) => (
              <div key={kpi.key} className="balance-analysis-ops-item">
                <span className="balance-analysis-ops-item__label">{kpi.label}</span>
                <strong className="balance-analysis-ops-item__value">
                  {kpi.value}
                  {kpi.value !== EM_DASH && kpi.unit ? <small>{kpi.unit}</small> : null}
                </strong>
              </div>
            ))}
          </section>
        </section>

        <section data-testid="balance-analysis-cockpit-stage" className="balance-analysis-sec">
          <BalanceSectionHead title="资产负债读面" meta="摘要 / 贡献 / 期限 / 风险" />
          <div className="balance-analysis-stage-stack">
            <BalanceSummaryRow model={stageModel.summary} variant="terminal" />
            <BalanceContributionRow model={stageModel.contribution} variant="terminal" />
            <BalanceBottomRow model={stageModel.bottom} variant="terminal" />
          </div>
        </section>

        <section data-testid="balance-analysis-workbench-grid" className="balance-analysis-sec">
          <BalanceSectionHead
            title="工作簿分析入口"
            meta={model.workbookSummary}
            hint="底稿默认折叠；ADB 预览与高级归因标为「分析面」，不混入正式 workbook。"
          />
          <div className="balance-analysis-quicknav">
            {model.workbookNav.map((item) => (
              <button
                key={item.key}
                type="button"
                className="balance-analysis-quicknav__item"
                data-testid={`balance-analysis-workbook-nav-${item.key}`}
                onClick={() => scrollToPanel(item.panelId)}
              >
                <span className="balance-analysis-quicknav__icon">{workbookIcons[item.key]}</span>
                <b>{item.label}</b>
              </button>
            ))}
          </div>
        </section>
      </div>

      <div
        data-testid="balance-analysis-overview-cards"
        className="balance-analysis-visually-hidden"
        aria-hidden
      >
        {headlineCards.map((card) => (
          <span key={card.key}>
            {card.label} {card.value}
          </span>
        ))}
      </div>
    </div>
  );
}
