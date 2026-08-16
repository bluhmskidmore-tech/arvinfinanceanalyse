import type { ReactNode } from "react";
import { Link, useInRouterContext } from "react-router-dom";

import { getMarketWorkbenchNav } from "./marketWorkbenchNav";
import styles from "./MarketWorkbenchFrame.module.css";
import type { MarketWorkbenchFrameProps } from "./types";

function classNames(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

function defaultAuditContent({
  metaItems,
  statusLabel,
}: {
  metaItems: MarketWorkbenchFrameProps["metaItems"];
  statusLabel: string;
}) {
  return (
    <div className={styles.auditDefaultGrid}>
      <span>状态 {statusLabel}</span>
      {metaItems.map((item) => (
        <span key={`${item.label}-${item.value}`}>
          {item.label} {item.value}
        </span>
      ))}
    </div>
  );
}

export function MarketWorkbenchFrame({
  pageKey,
  title,
  question,
  status,
  metaItems,
  navDensity = "default",
  actions,
  children,
  auditContent,
  themeScope,
}: MarketWorkbenchFrameProps) {
  const inRouter = useInRouterContext();
  const navItems = getMarketWorkbenchNav();
  const visibleMetaItems = metaItems.filter((item) => item.value.trim().length > 0);
  const isCompactNav = navDensity === "compact";

  return (
    <section
      className={styles.frame}
      data-testid="market-workbench-frame"
      data-page-key={pageKey}
      data-moss-theme-scope={themeScope}
    >
      <header className={styles.topbar} data-testid="market-workbench-topbar">
        <div className={styles.topbarMain}>
          <div className={styles.titleRow}>
            <div className={styles.title}>{title}</div>
            <span className={styles.statusPill} data-tone={status.tone}>
              状态 {status.label}
            </span>
          </div>
          <p className={styles.question}>{question}</p>
          {status.detail ? <p className={styles.question}>口径 {status.detail}</p> : null}
        </div>
        <div className={styles.topbarAside}>
          <div className={styles.topbarMetaRow}>
            {visibleMetaItems.map((item) => (
              <span
                className={styles.metaPill}
                key={`${item.label}-${item.value}`}
                title={item.hint ?? (item.value.length > 48 ? item.value : undefined)}
              >
                <strong>{item.label}</strong>
                <span className={styles.metaPillValue}>{item.value}</span>
              </span>
            ))}
          </div>
          {actions ? <div className={styles.actions}>{actions}</div> : null}
        </div>
      </header>

      <section
        className={classNames(styles.navWrap, isCompactNav && styles.navWrapCompact)}
        aria-label="市场工作台子页面入口"
        data-density={navDensity}
      >
        <nav
          className={classNames(styles.nav, isCompactNav && styles.navCompact)}
          data-density={navDensity}
          data-testid="market-workbench-nav"
          tabIndex={0}
        >
          {navItems.map((item) => {
            const isCurrent = item.key === pageKey;
            const className = classNames(styles.navItem, isCompactNav && styles.navItemCompact);
            const content = (
              <>
                <span className={styles.navIcon} aria-hidden="true">
                  {item.iconLabel}
                </span>
                <span className={styles.navLabel}>{item.label}</span>
                <em className={styles.navStatus}>{isCurrent ? "当前页" : item.statusLabel}</em>
              </>
            );

            if (inRouter) {
              return (
                <Link
                  aria-current={isCurrent ? "page" : undefined}
                  className={className}
                  data-testid={`market-workbench-nav-${item.key}`}
                  key={item.key}
                  title={item.description}
                  to={item.path}
                >
                  {content}
                </Link>
              );
            }

            return (
              <a
                aria-current={isCurrent ? "page" : undefined}
                className={className}
                data-testid={`market-workbench-nav-${item.key}`}
                href={item.path}
                key={item.key}
                title={item.description}
              >
                {content}
              </a>
            );
          })}
        </nav>
        <p className={classNames(styles.navNote, isCompactNav && styles.navNoteCompact)}>
          市场首页只引用行情/事件接口的返回状态，不把观察口径提升为正式经营结论。
        </p>
      </section>

      <div className={styles.body} data-testid="market-workbench-body">
        <MarketWorkbenchPanel className={styles.contentPanel}>{children}</MarketWorkbenchPanel>
      </div>

      <details className={styles.auditFooter} data-testid="market-workbench-audit-footer">
        <summary>
          数据核验与下钻
          <span>
            {visibleMetaItems.map((item) => `${item.label} ${item.value}`).join(" · ") || status.label}
          </span>
        </summary>
        <div className={styles.auditBody}>
          {auditContent ?? defaultAuditContent({ metaItems: visibleMetaItems, statusLabel: status.label })}
        </div>
      </details>
    </section>
  );
}

export function MarketWorkbenchPanel({
  children,
  className,
  title,
  eyebrow,
  description,
  testId = "market-workbench-panel",
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  eyebrow?: string;
  description?: string;
  testId?: string;
}) {
  return (
    <section className={classNames(styles.panel, className)} data-testid={testId}>
      {title || eyebrow || description ? (
        <header className={styles.panelHeader}>
          {eyebrow ? <span className={styles.panelEyebrow}>{eyebrow}</span> : null}
          {title ? <h2 className={styles.panelTitle}>{title}</h2> : null}
          {description ? <p className={styles.panelDescription}>{description}</p> : null}
        </header>
      ) : null}
      {children}
    </section>
  );
}

export function MarketWorkbenchMetricGrid({
  children,
  className,
  testId = "market-workbench-metric-grid",
}: {
  children: ReactNode;
  className?: string;
  testId?: string;
}) {
  return (
    <div className={classNames(styles.metricGrid, className)} data-testid={testId}>
      {children}
    </div>
  );
}

export function MarketWorkbenchTableShell({
  children,
  className,
  title,
  description,
  testId = "market-workbench-table-shell",
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  description?: string;
  testId?: string;
}) {
  return (
    <section className={classNames(styles.tableShell, className)} data-testid={testId}>
      {title || description ? (
        <header className={styles.panelHeader}>
          {title ? <h2 className={styles.panelTitle}>{title}</h2> : null}
          {description ? <p className={styles.panelDescription}>{description}</p> : null}
        </header>
      ) : null}
      <div className={styles.tableViewport}>{children}</div>
    </section>
  );
}
