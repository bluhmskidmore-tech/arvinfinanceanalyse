import type { CSSProperties, ReactNode } from "react";

import { shellTokens } from "../../theme/tokens";
import {
  PAGE_V2_CONTRACT,
  pageInsetCardStyle,
  pageSurfacePanelStyle,
} from "./PagePrimitiveStyles";

type HeaderBadgeTone = "positive" | "accent" | "neutral";
type SurfaceElement = "div" | "section" | "article";

export type PageHeaderProps = {
  title: string;
  description: string;
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

function headerBadgeStyle(tone: HeaderBadgeTone) {
  if (tone === "positive") {
    return {
      background: shellTokens.colorBgSuccessSoft,
      color: shellTokens.colorSuccess,
    } as const;
  }

  if (tone === "accent") {
    return {
      background: shellTokens.colorAccentSoft,
      color: shellTokens.colorAccent,
    } as const;
  }

  return {
    background: shellTokens.colorBgMuted,
    color: shellTokens.colorTextSecondary,
  } as const;
}

export function PageHeader({
  title,
  description,
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
  return (
    <section
      data-testid={testId}
      className={className}
      style={{
        display: "grid",
        gap: 18,
        marginBottom: 28,
        ...style,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "grid", gap: 10, maxWidth: 920 }}>
          <span
            style={{
              color: shellTokens.colorTextMuted,
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            {eyebrow}
          </span>
          <h1
            data-testid={titleTestId}
            style={{
              margin: 0,
              fontSize: 32,
              fontWeight: 700,
              letterSpacing: "-0.03em",
              color: shellTokens.colorTextPrimary,
            }}
          >
            {title}
          </h1>
          <p
            data-testid={descriptionTestId}
            style={{
              margin: 0,
              color: shellTokens.colorTextSecondary,
              fontSize: 15,
              lineHeight: 1.8,
            }}
          >
            {description}
          </p>
        </div>

        <div
          style={{
            display: "grid",
            justifyItems: "end",
            gap: 12,
          }}
        >
          {badgeLabel ? (
            <span
              style={{
                ...headerBadgeStyle(badgeTone),
                display: "inline-flex",
                alignItems: "center",
                padding: "8px 14px",
                borderRadius: 999,
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: "0.04em",
              }}
            >
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
    <div
      style={{
        display: "grid",
        gap: 6,
        marginTop: 28,
        ...style,
      }}
    >
      <span
        style={{
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: shellTokens.colorTextMuted,
        }}
      >
        {eyebrow}
      </span>
      <h2
        style={{
          margin: 0,
          fontSize: 18,
          fontWeight: 700,
          color: shellTokens.colorTextPrimary,
        }}
      >
        {title}
      </h2>
      <p
        style={{
          margin: 0,
          maxWidth: 860,
          color: shellTokens.colorTextSecondary,
          fontSize: 13,
          lineHeight: 1.7,
        }}
      >
        {description}
      </p>
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

export function PageV2Shell({ children, testId, style }: PageV2ShellProps) {
  return (
    <div data-testid={testId} className="moss-page-v2-shell" style={style}>
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
