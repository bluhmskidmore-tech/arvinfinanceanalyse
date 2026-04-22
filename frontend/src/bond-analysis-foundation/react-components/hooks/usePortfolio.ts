import { useQuery } from "@tanstack/react-query";

import { useBondWorkspace } from "../context/BondContext";
import type { BondApiService } from "../services/api";

export interface UsePortfolioOptions {
  api?: BondApiService;
  enabled?: boolean;
}

export function usePortfolio(options: UsePortfolioOptions = {}) {
  const workspace = useBondWorkspace();
  const api = options.api ?? workspace.api;

  const portfolioListQuery = useQuery({
    queryKey: ["bond-foundation", "portfolio", "list"],
    queryFn: () => api.getPortfolios(),
    enabled: options.enabled !== false,
  });

  const portfolioDetailQuery = useQuery({
    queryKey: ["bond-foundation", "portfolio", workspace.selectedPortfolioId],
    queryFn: () => api.getPortfolio(workspace.selectedPortfolioId as string),
    enabled: Boolean(workspace.selectedPortfolioId) && options.enabled !== false,
  });

  const analyticsQuery = useQuery({
    queryKey: ["bond-foundation", "portfolio-analytics", workspace.selectedPortfolioId],
    queryFn: () => api.getPortfolioAnalytics(workspace.selectedPortfolioId as string),
    enabled: Boolean(workspace.selectedPortfolioId) && options.enabled !== false,
  });

  return {
    portfolios: portfolioListQuery.data?.items ?? [],
    selectedPortfolioId: workspace.selectedPortfolioId,
    selectPortfolio: workspace.selectPortfolio,
    portfolio: portfolioDetailQuery.data,
    analytics: analyticsQuery.data,
    portfolioListQuery,
    portfolioDetailQuery,
    analyticsQuery,
  };
}
