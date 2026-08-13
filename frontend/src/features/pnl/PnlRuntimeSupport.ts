import { designTokens } from "../../theme/designSystem";

export type PnlSectionState = "loading" | "error" | "empty" | "ready";

export function resolvePnlSectionState({
  isLoading,
  isError,
  isEmpty,
}: {
  isLoading: boolean;
  isError: boolean;
  isEmpty: boolean;
}): PnlSectionState {
  if (isLoading) {
    return "loading";
  }
  if (isError) {
    return "error";
  }
  if (isEmpty) {
    return "empty";
  }
  return "ready";
}

export const pnlActionButtonStyle = {
  padding: "10px 16px",
  borderRadius: 12,
  border: `1px solid ${designTokens.color.cockpit.border225}`, // 近似替换（原值 #d7dfea）
  background: designTokens.color.institutional.surfaceRaised,
  color: designTokens.color.institutional.text, // 近似替换（原值 #162033）
  fontWeight: 600,
  cursor: "pointer",
} as const;
