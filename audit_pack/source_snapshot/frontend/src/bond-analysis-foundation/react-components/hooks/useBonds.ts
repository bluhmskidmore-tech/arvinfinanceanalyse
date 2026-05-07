import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import type { BondListQuery } from "../../data-structures/BondModel";
import { useBondWorkspace } from "../context/BondContext";
import type { BondApiService } from "../services/api";

export interface UseBondsOptions {
  api?: BondApiService;
  initialFilters?: BondListQuery;
  autoSelectFirstBond?: boolean;
  enabled?: boolean;
}

export function useBonds(options: UseBondsOptions = {}) {
  const workspace = useBondWorkspace();
  const api = options.api ?? workspace.api;
  const [filters, setFilters] = useState<BondListQuery>(options.initialFilters ?? {});

  const listQuery = useQuery({
    queryKey: ["bond-foundation", "bonds", filters],
    queryFn: () => api.getBonds(filters),
    enabled: options.enabled !== false,
  });

  useEffect(() => {
    if (
      options.autoSelectFirstBond &&
      !workspace.selectedBondId &&
      listQuery.data?.items.length
    ) {
      workspace.selectBond(listQuery.data.items[0]?.bondId ?? null);
    }
  }, [listQuery.data, options.autoSelectFirstBond, workspace]);

  const detailQuery = useQuery({
    queryKey: ["bond-foundation", "bond", workspace.selectedBondId],
    queryFn: () => api.getBond(workspace.selectedBondId as string),
    enabled: Boolean(workspace.selectedBondId) && options.enabled !== false,
  });

  return {
    filters,
    setFilters,
    bonds: listQuery.data?.items ?? [],
    total: listQuery.data?.total ?? 0,
    selectedBondId: workspace.selectedBondId,
    selectBond: workspace.selectBond,
    selectedBond: detailQuery.data,
    listQuery,
    detailQuery,
  };
}
