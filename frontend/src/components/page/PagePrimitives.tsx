import type { CSSProperties, ReactNode } from "react";

import { shellTokens } from "../../theme/tokens";
import {
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
  style,
}: PageHeaderProps) {
  return (
    <section
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
