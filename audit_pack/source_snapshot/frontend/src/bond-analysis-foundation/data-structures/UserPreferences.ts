import type { BondMetricKey } from "./BondModel";

export type ColorMode = "dark" | "light" | "system";
export type DashboardLayout = "trader" | "portfolio" | "risk";

export interface UserPreferences {
  colorMode: ColorMode;
  language: string;
  refreshIntervalSeconds: number;
  favoriteBondCodes: string[];
  customMetrics: BondMetricKey[];
  defaultPortfolioId?: string;
  dashboardLayout: DashboardLayout;
  enableMotion: boolean;
}
