import { Link } from "react-router-dom";

import { LightIcon, type LightIconName } from "../../../components/LightIcon";
import type { DashboardHomeBodyView } from "./dashboardHomeBodyView";
import { BondNewsSection } from "./sections/BondNewsSection";
import { ResearchCalendarSection } from "./sections/ResearchCalendarSection";
import styles from "./dashboardHome.module.css";

type TerminalHomeDeferredSectionsProps = {
  view: DashboardHomeBodyView;
};

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

export function TerminalHomeDeferredSections({ view }: TerminalHomeDeferredSectionsProps) {
  return (
    <>
      <BondNewsSection bondNews={view.bondNews} />
      <ResearchCalendarSection macroBriefing={view.macroBriefing} />
      <QuickDrilldowns view={view} />
    </>
  );
}
