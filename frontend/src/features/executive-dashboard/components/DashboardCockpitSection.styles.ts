import type { CSSProperties } from "react";

import { shellTokens } from "../../../theme/tokens";

const DISPLAY_FONT =
  '"Alibaba PuHuiTi 3.0", "HarmonyOS Sans SC", "PingFang SC", "Microsoft YaHei UI", sans-serif';

export const cockpitSectionShellStyle: CSSProperties = {
  height: "100%",
  padding: 22,
  borderRadius: 26,
  background:
    "linear-gradient(180deg, rgba(252,251,248,0.98) 0%, rgba(247,247,242,0.96) 100%)",
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  boxShadow: "0 22px 52px rgba(22, 35, 46, 0.06)",
};

export const cockpitInsetCardStyle: CSSProperties = {
  display: "grid",
  gap: 8,
  padding: 16,
  borderRadius: 18,
  background: "#ffffff",
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.84)",
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
  fontSize: 20,
  fontWeight: 800,
  letterSpacing: "-0.03em",
  fontFamily: DISPLAY_FONT,
};

export const cockpitBodyStyle: CSSProperties = {
  margin: 0,
  color: shellTokens.colorTextSecondary,
  fontSize: 13,
  lineHeight: 1.7,
};
