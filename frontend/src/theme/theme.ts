import type { ThemeConfig } from "antd";

import { shellTokens } from "./tokens";

export const workbenchTheme: ThemeConfig = {
  token: {
    colorPrimary: shellTokens.colorAccent,
    colorSuccess: shellTokens.colorSuccess,
    colorWarning: shellTokens.colorWarning,
    colorError: shellTokens.colorDanger,
    colorText: shellTokens.colorTextPrimary,
    colorTextSecondary: shellTokens.colorTextSecondary,
    colorBorder: shellTokens.colorBorder,
    colorBgBase: shellTokens.colorBgSurface,
    colorBgContainer: shellTokens.colorBgSurface,
    colorFillAlter: shellTokens.colorBgMuted,
    borderRadius: shellTokens.radiusCard,
    fontFamily:
      '"PingFang SC", "Microsoft YaHei UI", "Noto Sans SC", sans-serif',
  },
  components: {
    Card: {
      borderRadiusLG: shellTokens.radiusCard,
    },
    Layout: {
      bodyBg: shellTokens.colorBgApp,
      siderBg: shellTokens.colorBgSurface,
      headerBg: "transparent",
    },
  },
};
