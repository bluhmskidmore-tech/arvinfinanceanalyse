import type { CSSProperties, ReactNode } from "react";

import {
  PAGE_V2_CONTRACT,
  pageInsetCardStyle,
  pageSurfacePanelStyle,
} from "./PagePrimitiveStyles";
import styles from "./PagePrimitives.module.css";

type HeaderBadgeTone = "positive" | "accent" | "neutral";
type SurfaceElement = "div" | "section" | "article";

export type PageHeaderProps = {
  title: string;
  description: string;
  density?: "default" | "compact";
  eyebrow?: string;
  titleTestId?: string;
  descriptionTestId?: string;
  badgeLabel?: string;
  badgeTone?: HeaderBadgeTone;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
  testId?: string;
  style?: CSSProperties;
};

const headerBadgeToneClass: Record<HeaderBadgeTone, string> = {
  positive: styles.headerBadgePositive,
  accent: styles.headerBadgeAccent,
  neutral: styles.headerBadgeNeutral,
};

export function PageHeader({
  title,
  description,
  density = "default",
  eyebrow = "总览",
  titleTestId,
  descriptionTestId,
  badgeLabel,
  badgeTone = "neutral",
  actions,
  children,
  className,
  testId,
  style,
}: PageHeaderProps) {
  const isCompact = density === "compact";

  return (
    <section
      data-testid={testId}
      className={cx(styles.pageHeader, isCompact && styles.pageHeaderCompact, className)}
      style={style}
    >
      <div className={styles.headerTop}>
        <div className={styles.headerTitles}>
          <span className={styles.headerEyebrow}>{eyebrow}</span>
          <h1 data-testid={titleTestId} className={styles.headerTitle}>
            {title}
          </h1>
          <p data-testid={descriptionTestId} className={styles.headerDescription}>
            {description}
          </p>
        </div>

        <div className={styles.headerAside}>
          {badgeLabel ? (
            <span className={cx(styles.headerBadge, headerBadgeToneClass[badgeTone])}>
              {badgeLabel}
            </span>
          ) : null}
          {actions}
        </div>
      </div>

      {children ? <div>{children}</div> : null}
    </section>
  );
}

export type PageSectionLeadProps = {
  eyebrow: string;
  title: string;
  description: string;
  style?: CSSProperties;
};

export type PageFilterTrayProps = {
  children: ReactNode;
  testId?: string;
  style?: CSSProperties;
};

export type PageSurfacePanelProps = {
  as?: SurfaceElement;
  children: ReactNode;
  testId?: string;
  style?: CSSProperties;
};

export type PageV2ShellProps = {
  children: ReactNode;
  testId?: string;
  style?: CSSProperties;
  /**
   * Nocturne 换肤 scope 透传（MarketWorkbenchFrame themeScope 同款先例）：
   * PageV2Shell 即页根时 scope 须落在 shell 根元素；不传时零影响。
   */
  themeScope?: string;
};

export type PageV2SurfacePanelProps = {
  as?: SurfaceElement;
  children: ReactNode;
  testId?: string;
  style?: CSSProperties;
};

export function PageSectionLead({
  eyebrow,
  title,
  description,
  style,
}: PageSectionLeadProps) {
  return (
    <div className={styles.sectionLead} style={style}>
      <span className={styles.sectionLeadEyebrow}>{eyebrow}</span>
      <h2 className={styles.sectionLeadTitle}>{title}</h2>
      <p className={styles.sectionLeadDescription}>{description}</p>
    </div>
  );
}

export function PageFilterTray({ children, testId, style }: PageFilterTrayProps) {
  return (
    <div
      data-testid={testId}
      style={{
        ...pageInsetCardStyle,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

export function PageSurfacePanel({
  as = "section",
  children,
  testId,
  style,
}: PageSurfacePanelProps) {
  const Component = as;
  return (
    <Component
      data-testid={testId}
      style={{
        ...pageSurfacePanelStyle,
        ...style,
      }}
    >
      {children}
    </Component>
  );
}

export function PageV2Shell({ children, testId, style, themeScope }: PageV2ShellProps) {
  return (
    <div
      data-testid={testId}
      data-moss-theme-scope={themeScope}
      className="moss-page-v2-shell"
      style={style}
    >
      {children}
    </div>
  );
}

export function PageV2SurfacePanel({
  as = "section",
  children,
  testId,
  style,
}: PageV2SurfacePanelProps) {
  const Component = as;

  return (
    <Component data-testid={testId} className="moss-page-v2-surface" style={style}>
      {children}
    </Component>
  );
}

function cx(...parts: Array<string | undefined | false>) {
  return parts.filter(Boolean).join(" ");
}

export type PageDecisionHeroProps = {
  title: string;
  /** 迁移页必须在首屏显式回应的首要业务问题 */
  businessQuestion: string;
  eyebrow?: string;
  reportDateSlot?: ReactNode;
  conclusion?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  testId?: string;
  titleTestId?: string;
  questionTestId?: string;
  className?: string;
  style?: CSSProperties;
};

/**
 * Phase 1 契约原语（opt-in）：决策首屏区，仅显式使用者会挂载契约类名。
 */
export function PageDecisionHero({
  title,
  businessQuestion,
  eyebrow = "工作台",
  reportDateSlot,
  conclusion,
  actions,
  children,
  testId,
  titleTestId,
  questionTestId,
  className,
  style,
}: PageDecisionHeroProps) {
  return (
    <section
      data-testid={testId}
      className={cx(PAGE_V2_CONTRACT.decisionHeroRoot, className)}
      style={style}
    >
      <div className="moss-page-v2-decision-hero__top">
        <div className="moss-page-v2-decision-hero__titles">
          {eyebrow ? (
            <span className="moss-page-v2-decision-hero__eyebrow">{eyebrow}</span>
          ) : null}
          <h1 className="moss-page-v2-decision-hero__title" data-testid={titleTestId}>
            {title}
          </h1>
          <p
            className="moss-page-v2-decision-hero__question"
            data-testid={questionTestId}
          >
            {businessQuestion}
          </p>
          {reportDateSlot ? (
            <div className="moss-page-v2-decision-hero__report">{reportDateSlot}</div>
          ) : null}
          {conclusion ? (
            <div className="moss-page-v2-decision-hero__conclusion">{conclusion}</div>
          ) : null}
        </div>
        {actions ? (
          <div className="moss-page-v2-decision-hero__actions">{actions}</div>
        ) : null}
      </div>
      {children}
    </section>
  );
}

export type DataStatusStripProps = {
  children: ReactNode;
  testId?: string;
  className?: string;
  style?: CSSProperties;
};

/** 数据状态汇总条，内容由页面拼装 */
export function DataStatusStrip({ children, testId, className, style }: DataStatusStripProps) {
  return (
    <div
      role="region"
      aria-label="数据状态"
      data-testid={testId}
      className={cx(PAGE_V2_CONTRACT.dataStatusRoot, className)}
      style={style}
    >
      {children}
    </div>
  );
}

export type KpiBandProps = {
  children: ReactNode;
  testId?: string;
  className?: string;
  style?: CSSProperties;
};

export function KpiBand({ children, testId, className, style }: KpiBandProps) {
  return (
    <div
      data-testid={testId}
      className={cx(PAGE_V2_CONTRACT.kpiBandRoot, className)}
      style={style}
    >
      {children}
    </div>
  );
}

export type KpiBandMetricProps = {
  label: ReactNode;
  value: ReactNode;
  footer?: ReactNode;
  testId?: string;
};

export function KpiBandMetric({ label, value, footer, testId }: KpiBandMetricProps) {
  return (
    <div data-testid={testId} className={PAGE_V2_CONTRACT.kpiMetricItem}>
      <div className="moss-page-v2-kpi-metric__label">{label}</div>
      <div className="moss-page-v2-kpi-metric__value">{value}</div>
      {footer ? <div className="moss-page-v2-kpi-metric__footer">{footer}</div> : null}
    </div>
  );
}

export type AnalysisGridProps = {
  columns?: 1 | 2 | 3;
  children: ReactNode;
  testId?: string;
  className?: string;
  style?: CSSProperties;
};

export function AnalysisGrid({ columns = 1, children, testId, className, style }: AnalysisGridProps) {
  const colKey = columns === 2 ? "2" : columns === 3 ? "3" : "1";
  return (
    <div
      data-testid={testId}
      className={cx(PAGE_V2_CONTRACT.analysisGridCols[colKey], className)}
      style={style}
    >
      {children}
    </div>
  );
}

export type EvidencePanelProps = {
  heading?: string;
  children: ReactNode;
  testId?: string;
  as?: SurfaceElement;
  className?: string;
  style?: CSSProperties;
};

export function EvidencePanel({
  heading,
  children,
  testId,
  as = "section",
  className,
  style,
}: EvidencePanelProps) {
  const Component = as;
  return (
    <Component
      data-testid={testId}
      className={cx(PAGE_V2_CONTRACT.evidencePanelRoot, className)}
      style={style}
    >
      {heading ? <h2 className="moss-page-v2-evidence-panel__heading">{heading}</h2> : null}
      {children}
    </Component>
  );
}

export type PageStateSurfaceVariant =
  | "neutral"
  | "loading"
  | "empty"
  | "error"
  | "stale"
  | "fallback-date"
  | "mock"
  | "definition-pending";

export type PageStateSurfaceProps = {
  variant?: PageStateSurfaceVariant;
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  testId?: string;
  className?: string;
  style?: CSSProperties;
};

export function PageStateSurface({
  variant = "neutral",
  title,
  description,
  actions,
  children,
  testId,
  className,
  style,
}: PageStateSurfaceProps) {
  return (
    <div
      role="status"
      data-testid={testId}
      data-state-variant={variant}
      className={cx(PAGE_V2_CONTRACT.stateSurfaceRoot, className)}
      style={style}
    >
      {title ? <p className="moss-page-v2-state-surface__title">{title}</p> : null}
      {description ? (
        <p className="moss-page-v2-state-surface__description">{description}</p>
      ) : null}
      {children}
      {actions}
    </div>
  );
}
