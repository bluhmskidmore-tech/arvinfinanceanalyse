import { designTokens } from "../../../theme/designSystem";
import { shellTokens } from "../../../theme/tokens";
import type { BalanceAnalysisSeverity } from "../../../api/contracts";

export interface PrioritySignal {
  key: string;
  title: string;
  eyebrow: string;
  highlight: string;
  detail: string;
  tone: "danger" | "warning" | "info";
}

export function heroMetaChipStyle(
  tone: "accent" | "positive" | "warning" | "neutral" = "neutral",
) {
  if (tone === "accent") {
    return {
      background: shellTokens.colorAccentSoft,
      color: shellTokens.colorAccent,
      border: `1px solid ${shellTokens.colorBorderSoft}`,
    } as const;
  }
  if (tone === "positive") {
    return {
      background: shellTokens.colorBgSuccessSoft,
      color: shellTokens.colorSuccess,
      border: `1px solid ${shellTokens.colorBorderSoft}`,
    } as const;
  }
  if (tone === "warning") {
    return {
      background: shellTokens.colorBgWarningSoft,
      color: shellTokens.colorWarning,
      border: `1px solid ${shellTokens.colorBorderWarning}`,
    } as const;
  }
  return {
    background: shellTokens.colorBgMuted,
    color: shellTokens.colorTextSecondary,
    border: `1px solid ${shellTokens.colorBorderSoft}`,
  } as const;
}

export function signalAccentStyle(tone: "danger" | "warning" | "info") {
  if (tone === "danger") {
    return {
      background: designTokens.color.danger[50],
      color: shellTokens.colorDanger,
      border: `1px solid ${designTokens.color.danger[200]}`,
    } as const;
  }
  if (tone === "warning") {
    return {
      background: shellTokens.colorBgWarningSoft,
      color: shellTokens.colorWarning,
      border: `1px solid ${shellTokens.colorBorderWarning}`,
    } as const;
  }
  return {
    background: shellTokens.colorAccentSoft,
    color: shellTokens.colorAccent,
    border: `1px solid ${shellTokens.colorBorderSoft}`,
  } as const;
}

export function severityTone(severity: BalanceAnalysisSeverity | undefined) {
  if (severity === "high") return "danger" as const;
  if (severity === "medium") return "warning" as const;
  return "info" as const;
}
