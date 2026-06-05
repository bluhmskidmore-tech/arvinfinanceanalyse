import type { CSSProperties } from "react";

import { shellTokens } from "../../../theme/tokens";

const DISPLAY_FONT =
  '"Alibaba PuHuiTi 3.0", "HarmonyOS Sans SC", "PingFang SC", "Microsoft YaHei UI", sans-serif';

export const cockpitSectionShellStyle: CSSProperties = {
  height: "100%",
  padding: 16,
  borderRadius: 12,
  background: "#ffffff",
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  boxShadow: "none",
};

export const cockpitInsetCardStyle: CSSProperties = {
  display: "grid",
  gap: 6,
  padding: 12,
  borderRadius: 8,
  background: "#ffffff",
  border: `1px solid ${shellTokens.colorBorderSoft}`,
};

export const cockpitEyebrowStyle: CSSProperties = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: shellTokens.colorTextMuted,
};

export const cockpitTitleStyle: CSSProperties = {
  margin: 0,
  color: shellTokens.colorTextPrimary,
  fontSize: 14,
  fontWeight: 700,
  letterSpacing: "-0.01em",
  fontFamily: DISPLAY_FONT,
};

export const cockpitBodyStyle: CSSProperties = {
  margin: 0,
  color: shellTokens.colorTextSecondary,
  fontSize: 12,
  lineHeight: 1.5,
};
