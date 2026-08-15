import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { BalanceCurrencyBasis, BalancePositionScope } from "../../../api/contracts";

function normalizePositionScopeParam(value: string | null): BalancePositionScope {
  return value === "asset" || value === "liability" || value === "all" ? value : "all";
}

function normalizeCurrencyBasisParam(_value: string | null): BalanceCurrencyBasis {
  return "CNY";
}

export interface BalanceAnalysisFilters {
  selectedReportDate: string;
  unavailableRequestedReportDate: string | null;
  isSelectedReportDateAvailable: boolean;
  positionScope: BalancePositionScope;
  currencyBasis: BalanceCurrencyBasis;
  setSelectedReportDate: (date: string) => void;
  setPositionScope: (scope: BalancePositionScope) => void;
  setCurrencyBasis: (basis: BalanceCurrencyBasis) => void;
}

export function useBalanceAnalysisFilters(
  availableDates: string[],
): BalanceAnalysisFilters {
  const [searchParams, setSearchParams] = useSearchParams();
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

  // Preserve an explicit URL date even when unavailable; only default when no date was requested.
  useEffect(() => {
    const firstDate = availableDates[0];
    if (!availableDates.length) {
      return;
    }
    if (queryReportDate) {
      if (selectedReportDate !== queryReportDate) {
        setSelectedReportDate(queryReportDate);
      }
      return;
    }
    if ((!selectedReportDate || !availableDates.includes(selectedReportDate)) && firstDate) {
      setSelectedReportDate(firstDate);
    }
  }, [availableDates, queryReportDate, selectedReportDate]);

  // Sync scope/basis from URL params, but only when the URL value itself changes.
  // The in-page setters commit state first and write the URL through a router
  // transition; a plain value-mismatch check would revert the user's switch
  // during that window (deep links carry these params permanently).
  const lastQueryPositionScopeRef = useRef(queryPositionScope);
  const lastQueryCurrencyBasisRef = useRef(queryCurrencyBasis);
  useEffect(() => {
    if (queryPositionScope !== lastQueryPositionScopeRef.current) {
      lastQueryPositionScopeRef.current = queryPositionScope;
      if (queryPositionScope !== null) {
        setPositionScope(normalizePositionScopeParam(queryPositionScope));
      }
    }
    if (queryCurrencyBasis !== lastQueryCurrencyBasisRef.current) {
      lastQueryCurrencyBasisRef.current = queryCurrencyBasis;
      if (queryCurrencyBasis !== null) {
        setCurrencyBasis(normalizeCurrencyBasisParam(queryCurrencyBasis));
      }
    }
  }, [queryPositionScope, queryCurrencyBasis]);

  // Aggregate page reads are CNY-only. Canonicalize legacy deep links so a
  // bookmarked native state cannot keep issuing cross-currency total requests.
  useEffect(() => {
    if (queryCurrencyBasis === null || queryCurrencyBasis === "CNY") {
      return;
    }
    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.set("currency_basis", "CNY");
    setSearchParams(nextSearchParams, { replace: true });
  }, [queryCurrencyBasis, searchParams, setSearchParams]);

  function handleReportDateChange(date: string) {
    setSelectedReportDate(date);
    const nextSearchParams = new URLSearchParams(searchParams);
    if (date) {
      nextSearchParams.set("report_date", date);
    } else {
      nextSearchParams.delete("report_date");
    }
    setSearchParams(nextSearchParams, { replace: true });
  }

  // Mirror the report-date pattern: keep deep links shareable and keep the URL
  // params in step with in-page switches.
  function handlePositionScopeChange(scope: BalancePositionScope) {
    setPositionScope(scope);
    lastQueryPositionScopeRef.current = scope;
    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.set("position_scope", scope);
    setSearchParams(nextSearchParams, { replace: true });
  }

  function handleCurrencyBasisChange(basis: BalanceCurrencyBasis) {
    const normalizedBasis = normalizeCurrencyBasisParam(basis);
    setCurrencyBasis(normalizedBasis);
    lastQueryCurrencyBasisRef.current = normalizedBasis;
    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.set("currency_basis", normalizedBasis);
    setSearchParams(nextSearchParams, { replace: true });
  }

  const isSelectedReportDateAvailable = Boolean(
    selectedReportDate && availableDates.includes(selectedReportDate),
  );
  const unavailableRequestedReportDate =
    queryReportDate &&
    selectedReportDate === queryReportDate &&
    !isSelectedReportDateAvailable
      ? queryReportDate
      : null;

  return {
    selectedReportDate,
    unavailableRequestedReportDate,
    isSelectedReportDateAvailable,
    positionScope,
    currencyBasis,
    setSelectedReportDate: handleReportDateChange,
    setPositionScope: handlePositionScopeChange,
    setCurrencyBasis: handleCurrencyBasisChange,
  };
}
