import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { BalanceCurrencyBasis, BalancePositionScope } from "../../../api/contracts";

function normalizePositionScopeParam(value: string | null): BalancePositionScope {
  return value === "asset" || value === "liability" || value === "all" ? value : "all";
}

function normalizeCurrencyBasisParam(value: string | null): BalanceCurrencyBasis {
  return value === "native" || value === "CNY" ? value : "CNY";
}

export interface BalanceAnalysisFilters {
  selectedReportDate: string;
  positionScope: BalancePositionScope;
  currencyBasis: BalanceCurrencyBasis;
  setSelectedReportDate: (date: string) => void;
  setPositionScope: (scope: BalancePositionScope) => void;
  setCurrencyBasis: (basis: BalanceCurrencyBasis) => void;
}

export function useBalanceAnalysisFilters(
  availableDates: string[],
): BalanceAnalysisFilters {
  const [searchParams] = useSearchParams();
  const queryReportDate = searchParams.get("report_date")?.trim() || "";
  const queryPositionScope = searchParams.get("position_scope");
  const queryCurrencyBasis = searchParams.get("currency_basis");

  const [selectedReportDate, setSelectedReportDate] = useState("");
  const [positionScope, setPositionScope] = useState<BalancePositionScope>(
    normalizePositionScopeParam(queryPositionScope),
  );
  const [currencyBasis, setCurrencyBasis] = useState<BalanceCurrencyBasis>(
    normalizeCurrencyBasisParam(queryCurrencyBasis),
  );

  // Sync report date from URL param and available dates
  useEffect(() => {
    const firstDate = availableDates[0];
    if (!availableDates.length) {
      return;
    }
    if (queryReportDate && availableDates.includes(queryReportDate)) {
      if (selectedReportDate !== queryReportDate) {
        setSelectedReportDate(queryReportDate);
      }
      return;
    }
    if ((!selectedReportDate || !availableDates.includes(selectedReportDate)) && firstDate) {
      setSelectedReportDate(firstDate);
    }
  }, [availableDates, queryReportDate, selectedReportDate]);

  // Sync scope/basis from URL params
  useEffect(() => {
    if (queryPositionScope !== null) {
      const next = normalizePositionScopeParam(queryPositionScope);
      if (positionScope !== next) setPositionScope(next);
    }
    if (queryCurrencyBasis !== null) {
      const next = normalizeCurrencyBasisParam(queryCurrencyBasis);
      if (currencyBasis !== next) setCurrencyBasis(next);
    }
  }, [queryPositionScope, queryCurrencyBasis, positionScope, currencyBasis]);

  return {
    selectedReportDate,
    positionScope,
    currencyBasis,
    setSelectedReportDate,
    setPositionScope,
    setCurrencyBasis,
  };
}
