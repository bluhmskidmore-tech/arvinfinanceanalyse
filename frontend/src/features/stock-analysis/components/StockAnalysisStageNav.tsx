import { useId } from "react";
import { NavLink } from "react-router-dom";

import styles from "./StockAnalysisStageNav.module.css";

type AvailableStage = {
  key: "research" | "portfolio" | "risk";
  order: string;
  label: string;
  path: string;
};

type DeferredStage = {
  key: "execution" | "attribution";
  order: string;
  label: string;
};

const AVAILABLE_STAGES: AvailableStage[] = [
  { key: "research", order: "01", label: "研究", path: "/stock-analysis" },
  { key: "portfolio", order: "02", label: "组合构建", path: "/stock-analysis/portfolio" },
  { key: "risk", order: "03", label: "组合风险", path: "/stock-analysis/risk" },
];

const DEFERRED_STAGES: DeferredStage[] = [
  { key: "execution", order: "04", label: "交易执行" },
  { key: "attribution", order: "05", label: "绩效归因" },
];

type StockAnalysisStageNavProps = {
  variant?: "bar" | "menu";
};

/** Shared workflow navigation for the staged stock strategy cockpit. */
export function StockAnalysisStageNav({ variant = "bar" }: StockAnalysisStageNavProps) {
  const menuContentId = useId();
  const navigation = (
    <nav
      aria-label="股票策略阶段"
      className={styles.stageNav}
      data-testid="stock-analysis-stage-nav"
    >
      <div className={styles.stageNavViewport}>
        <ol className={styles.stageList}>
          {AVAILABLE_STAGES.map((stage) => (
            <li className={styles.stageItem} key={stage.key}>
              <NavLink className={styles.stageLink} end to={stage.path}>
                {({ isActive }) => (
                  <>
                    <span className={styles.stageOrder} aria-hidden="true">
                      {stage.order}
                    </span>
                    <span className={styles.stageLabel}>{stage.label}</span>
                    <span className={styles.stageStatus}>
                      {isActive ? "当前阶段" : "可进入"}
                    </span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
          {DEFERRED_STAGES.map((stage) => (
            <li className={styles.stageItem} key={stage.key}>
              <span
                className={`${styles.stageLink} ${styles.stageLinkDisabled}`}
                title={`${stage.label}将在后续阶段开放`}
              >
                <span className={styles.stageOrder} aria-hidden="true">
                  {stage.order}
                </span>
                <span className={styles.stageLabel}>{stage.label}</span>
                <span className={styles.stageStatus}>后续阶段</span>
              </span>
            </li>
          ))}
        </ol>
      </div>
    </nav>
  );

  if (variant === "menu") {
    return (
      <details className={styles.stageMenu} data-testid="stock-analysis-stage-menu">
        <summary aria-controls={menuContentId}>策略阶段</summary>
        <div className={styles.stageMenuPopover} id={menuContentId}>
          {navigation}
        </div>
      </details>
    );
  }

  return navigation;
}
