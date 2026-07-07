import { Link } from "react-router-dom";

import { LightIcon, type LightIconName } from "../../../components/LightIcon";
import type { DashboardHomeBodyView } from "./dashboardHomeBodyView";
import { BondNewsSection } from "./sections/BondNewsSection";
import { ResearchCalendarSection } from "./sections/ResearchCalendarSection";
import styles from "./dashboardHome.module.css";

type TerminalHomeDeferredSectionsProps = {
  view: DashboardHomeBodyView;
  focusPolicyFunding?: boolean;
};

function buildReportDatePath(path: string, reportDate: string): string {
  const trimmed = reportDate.trim();
  return trimmed && trimmed !== "—" ? `${path}?report_date=${encodeURIComponent(trimmed)}` : path;
}

function QuickDrilldowns({ view }: { view: DashboardHomeBodyView }) {
  const icons: LightIconName[] = ["bar-chart", "line-chart", "safety-certificate", "fund-projection", "database", "star"];
  return (
    <section data-testid="dashboard-home-bottom-grid" className={styles.dhTerminalBottom}>
      {view.quickDrilldowns.slice(0, 6).map((item, index) => {
        const iconName = icons[index] ?? "arrow-right";
        return (
          <Link key={item.id} to={item.path} className={`${styles.dhCard} ${styles.dhTerminalQuick}`}>
            <span>
              <LightIcon name={iconName} />
            </span>
            <b>{item.label}</b>
            <em>进入</em>
          </Link>
        );
      })}
    </section>
  );
}

function MarketCalendarContextPanel({ view }: { view: DashboardHomeBodyView }) {
  const context = view.marketContext;
  const sourceRows = [
    ["市场利率", "补充", "自然日"],
    ["供给/招标", view.macroBriefing.supplyItems.length > 0 ? "可用" : "可能为空", "窗口"],
    ["债券新闻", view.bondNews.statusLabel.replace(/^来源状态：/, "") || "部分可用", "事件流"],
    ["宏观新闻", view.macroBriefing.newsStatusLabel.replace(/^来源状态：/, "") || "部分/延迟", "新闻流"],
  ];

  return (
    <article
      data-testid="dashboard-home-market-context"
      className={`${styles.dhApiModule} ${styles.dhApiMarketContext}`}
    >
      <div className={styles.dhApiModuleHead}>
        <h3>市场 / 日历上下文</h3>
        <span>自然日补充信息，不参与严格 KPI 核验</span>
      </div>
      <p>今日市场解释：{context.temperatureLabel}</p>
      <p>{context.aiSummary[0] ?? "市场利率、债券新闻、供给日历和曲线解释由延迟查询补充加载。"}</p>
      <Link
        to={buildReportDatePath("/bond-analysis", view.reportDate)}
        className={styles.dhPanelDrillLink}
      >
        曲线/利差 →
      </Link>
      <div className={styles.dhApiMarketRows}>
        {sourceRows.map(([label, state, basis]) => (
          <div key={label}>
            <span>{label}</span>
            <b>{state}</b>
            <code>{basis}</code>
          </div>
        ))}
      </div>
      <div className={styles.dhCompatibilityProbe}>
        {context.contextBlocks.map((block) => (
          <span key={block.id}>{block.label}</span>
        ))}
      </div>
    </article>
  );
}

export function TerminalHomeDeferredSections({
  view,
  focusPolicyFunding = false,
}: TerminalHomeDeferredSectionsProps) {
  return (
    <>
      <ResearchCalendarSection
        macroBriefing={view.macroBriefing}
        focusPolicyFunding={focusPolicyFunding}
      />
      <MarketCalendarContextPanel view={view} />
      <BondNewsSection bondNews={view.bondNews} />
      <QuickDrilldowns view={view} />
    </>
  );
}
