/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, type ReactNode } from "react";

import type { UserPreferences } from "../../data-structures/UserPreferences";
import { createBondApiService, type BondApiService } from "../services/api";

const defaultPreferences: UserPreferences = {
  colorMode: "dark",
  language: "zh-CN",
  refreshIntervalSeconds: 15,
  favoriteBondCodes: [],
  customMetrics: ["yieldToMaturity", "creditSpreadBp", "modifiedDuration"],
  dashboardLayout: "trader",
  enableMotion: true,
};

export interface BondWorkspaceValue {
  api: BondApiService;
  preferences: UserPreferences;
  watchlist: string[];
  selectedBondId: string | null;
  selectedPortfolioId: string | null;
  setPreferences: (next: UserPreferences) => void;
  updatePreferences: (patch: Partial<UserPreferences>) => void;
  toggleColorMode: () => void;
  selectBond: (bondId: string | null) => void;
  selectPortfolio: (portfolioId: string | null) => void;
  addToWatchlist: (bondCode: string) => void;
  removeFromWatchlist: (bondCode: string) => void;
}

const BondContext = createContext<BondWorkspaceValue | null>(null);

export interface BondProviderProps {
  children: ReactNode;
  api?: BondApiService;
  initialPreferences?: Partial<UserPreferences>;
}

export function BondProvider({
  children,
  api,
  initialPreferences,
}: BondProviderProps) {
  const [service] = useState(() => api ?? createBondApiService());
  const [preferences, setPreferences] = useState<UserPreferences>({
    ...defaultPreferences,
    ...initialPreferences,
  });
  const [watchlist, setWatchlist] = useState<string[]>(
    initialPreferences?.favoriteBondCodes ?? defaultPreferences.favoriteBondCodes,
  );
  const [selectedBondId, setSelectedBondId] = useState<string | null>(null);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string | null>(
    initialPreferences?.defaultPortfolioId ?? null,
  );

  const value: BondWorkspaceValue = {
    api: service,
    preferences,
    watchlist,
    selectedBondId,
    selectedPortfolioId,
    setPreferences(next) {
      setPreferences(next);
      setWatchlist(next.favoriteBondCodes);
    },
    updatePreferences(patch) {
      setPreferences((current) => {
        const next = { ...current, ...patch };
        if (patch.favoriteBondCodes) {
          setWatchlist(patch.favoriteBondCodes);
        }
        return next;
      });
    },
    toggleColorMode() {
      setPreferences((current) => ({
        ...current,
        colorMode: current.colorMode === "dark" ? "light" : "dark",
      }));
    },
    selectBond(bondId) {
      setSelectedBondId(bondId);
    },
    selectPortfolio(portfolioId) {
      setSelectedPortfolioId(portfolioId);
    },
    addToWatchlist(bondCode) {
      setWatchlist((current) => {
        if (current.includes(bondCode)) {
          return current;
        }
        const next = [...current, bondCode];
        setPreferences((previous) => ({ ...previous, favoriteBondCodes: next }));
        return next;
      });
    },
    removeFromWatchlist(bondCode) {
      setWatchlist((current) => {
        const next = current.filter((item) => item !== bondCode);
        setPreferences((previous) => ({ ...previous, favoriteBondCodes: next }));
        return next;
      });
    },
  };

  return <BondContext.Provider value={value}>{children}</BondContext.Provider>;
}

export function useBondWorkspace() {
  const context = useContext(BondContext);

  if (!context) {
    throw new Error("useBondWorkspace must be used inside BondProvider");
  }

  return context;
}
