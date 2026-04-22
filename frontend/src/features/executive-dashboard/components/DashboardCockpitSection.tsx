import type { CSSProperties, ReactNode } from "react";

import type { DataSectionState } from "../../../components/DataSection.types";
import { shellTokens } from "../../../theme/tokens";
import {
  cockpitBodyStyle,
  cockpitEyebrowStyle,
  cockpitSectionShellStyle,
  cockpitTitleStyle,
} from "./DashboardCockpitSection.styles";

const retryButtonStyle: CSSProperties = {
  width: "fit-content",
  border: `1px solid ${shellTokens.colorBorder}`,
  background: "#ffffff",
  borderRadius: 999,
  padding: "9px 14px",
  color: shellTokens.colorTextPrimary,
  fontWeight: 700,
  cursor: "pointer",
};

export function DashboardCockpitSection(props: {
  title: string;
  eyebrow: string;
  extra?: ReactNode;
  /** Rendered below the empty-state hint (e.g. a secondary action button). */
  emptyFooter?: ReactNode;
  state: DataSectionState;
  onRetry: () => void;
  children: ReactNode;
  testId?: string;
}) {
  return (
    <section data-testid={props.testId} style={cockpitSectionShellStyle}>
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 12,
          marginBottom: 16,
        }}
      >
        <div style={{ display: "grid", gap: 6 }}>
          <span style={cockpitEyebrowStyle}>{props.eyebrow}</span>
          <h2 style={cockpitTitleStyle}>{props.title}</h2>
        </div>
        {props.extra}
      </div>
      {renderSectionBody(props.state, props.onRetry, props.children, props.emptyFooter)}
    </section>
  );
}

function renderSectionBody(
  state: DataSectionState,
  onRetry: () => void,
  children: ReactNode,
  emptyFooter?: ReactNode,
) {
  if (state.kind === "loading") {
    return (
      <div style={{ display: "grid", gap: 10 }}>
        <span style={{ ...cockpitBodyStyle, color: shellTokens.colorTextMuted }}>正在加载</span>
        <div style={{ display: "grid", gap: 10 }}>
          {Array.from({ length: 4 }).map((_, index) => (
            <div
              key={index}
              style={{
                height: 12,
                borderRadius: 999,
                background: index === 0 ? "#e8edf4" : "#eff3f7",
                width: index === 0 ? "74%" : index === 3 ? "58%" : "100%",
              }}
            />
          ))}
        </div>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div style={{ display: "grid", gap: 12 }}>
        <span style={{ color: shellTokens.colorDanger, fontWeight: 700 }}>数据加载失败</span>
        <p style={cockpitBodyStyle}>
          {state.message ?? "当前区块暂时不可用，请稍后重试。"}
        </p>
        <button type="button" onClick={onRetry} style={retryButtonStyle}>
          重试
        </button>
      </div>
    );
  }

  if (state.kind === "empty") {
    return (
      <div style={{ display: "grid", gap: 12 }}>
        <p style={cockpitBodyStyle}>{state.hint ?? "当前暂无可展示内容。"}</p>
        {emptyFooter}
      </div>
    );
  }

  if (state.kind === "vendor_unavailable") {
    return (
      <div style={{ display: "grid", gap: 8 }}>
        <span style={{ color: shellTokens.colorWarning, fontWeight: 700 }}>供应商数据暂不可用</span>
        {state.details ? <p style={cockpitBodyStyle}>{state.details}</p> : null}
      </div>
    );
  }

  if (state.kind === "explicit_miss") {
    return (
      <div style={{ display: "grid", gap: 8 }}>
        <span style={{ color: shellTokens.colorWarning, fontWeight: 700 }}>
          指定日期{state.requested_date ? ` ${state.requested_date}` : ""}暂无数据
        </span>
        {state.details ? <p style={cockpitBodyStyle}>{state.details}</p> : null}
      </div>
    );
  }

  if (state.kind === "stale" || state.kind === "fallback") {
    const label = state.kind === "stale" ? "数据可能已过期" : "已回退至最近可用日期";
    const accent = state.kind === "stale" ? shellTokens.colorWarning : shellTokens.colorAccent;
    return (
      <div style={{ display: "grid", gap: 14 }}>
        <div
          style={{
            display: "grid",
            gap: 4,
            padding: "10px 14px",
            borderRadius: 14,
            background: `${accent}12`,
            border: `1px solid ${accent}33`,
          }}
        >
          <strong style={{ color: accent }}>{label}</strong>
          <span style={{ ...cockpitBodyStyle, color: shellTokens.colorTextSecondary }}>
            {state.effective_date ? `生效日期 ${state.effective_date}` : ""}
            {state.effective_date && state.details ? " / " : ""}
            {state.details ?? ""}
          </span>
        </div>
        {children}
      </div>
    );
  }

  return children;
}
