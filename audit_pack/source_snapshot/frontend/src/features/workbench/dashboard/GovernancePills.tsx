import type { CSSProperties } from "react";

import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { shellTokens } from "../../../theme/tokens";

export type GovernancePillTone = "ok" | "warning" | "info";

export type GovernancePill = {
  id: string;
  label: string;
  value: string;
  tone: GovernancePillTone;
  hint?: string;
};

const TONE_STYLE: Record<GovernancePillTone, { bg: string; fg: string; border: string; dot: string }> = {
  ok: {
    bg: designTokens.color.success[50],
    fg: designTokens.color.success[600],
    border: designTokens.color.success[200],
    dot: designTokens.color.success[500],
  },
  warning: {
    bg: designTokens.color.warning[50],
    fg: designTokens.color.warning[600],
    border: designTokens.color.warning[200],
    dot: designTokens.color.warning[500],
  },
  info: {
    bg: designTokens.color.neutral[50],
    fg: shellTokens.colorTextSecondary,
    border: shellTokens.colorBorderSoft,
    dot: shellTokens.colorTextMuted,
  },
};

const wrapStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 6,
  alignItems: "center",
};

function pillStyle(tone: GovernancePillTone): CSSProperties {
  const palette = TONE_STYLE[tone];
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "3px 10px",
    borderRadius: 4,
    background: palette.bg,
    color: palette.fg,
    border: `1px solid ${palette.border}`,
    fontSize: 11,
    fontWeight: 700,
    lineHeight: 1.4,
    whiteSpace: "nowrap",
  };
}

function dotStyle(tone: GovernancePillTone): CSSProperties {
  return {
    width: 5,
    height: 5,
    borderRadius: 999,
    background: TONE_STYLE[tone].dot,
    flexShrink: 0,
  };
}

const labelStyle: CSSProperties = {
  color: shellTokens.colorTextMuted,
  fontWeight: 600,
};

const valueStyle: CSSProperties = {
  ...tabularNumsStyle,
  fontWeight: 700,
};

/**
 * 顶栏的"治理状态条"——把原本占据 4 张 hero 卡的
 * 报告日 / 快照模式 / 治理关注 / 读链路 折叠成 4 个轻量徽章。
 *
 * 规则：
 * - 默认状态（ok）保持低饱和、安静；
 * - 异常状态（warning）才用更强对比度，避免"告警通胀"；
 * - 每个 pill 都暴露独立 testId 便于稳定断言。
 */
export function GovernancePills({ pills }: { pills: GovernancePill[] }) {
  return (
    <div data-testid="dashboard-governance-pills" style={wrapStyle}>
      {pills.map((pill) => (
        <span
          key={pill.id}
          data-testid={`governance-pill-${pill.id}`}
          title={pill.hint}
          style={pillStyle(pill.tone)}
        >
          <span aria-hidden="true" style={dotStyle(pill.tone)} />
          <span style={labelStyle}>{pill.label}</span>
          <span style={valueStyle}>{pill.value}</span>
        </span>
      ))}
    </div>
  );
}
