import type {
  ColDef,
  ValueFormatterParams,
} from "ag-grid-community";

import { EM_DASH } from "../../utils/format";

export const mossGridHeaderHeight = 36;
export const mossGridRowHeight = 36;

export const mossGridDefaultColDef: ColDef = {
  sortable: true,
  filter: true,
  resizable: true,
  flex: 1,
  minWidth: 100,
};

export const mossGridLocaleText = {
  noRowsToShow: "暂无数据",
  loadingOoo: "加载中...",
};

export const mossGridNumericCellClass = "moss-ag-grid__cell--numeric";
export const mossGridNumericHeaderClass = "moss-ag-grid__header--numeric";

function normalizeClassValue(value: string | string[] | null | undefined): string[] {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

function mergeHeaderClass<TData, TValue>(
  existing: ColDef<TData, TValue>["headerClass"],
  classNames: string[],
): ColDef<TData, TValue>["headerClass"] {
  if (!existing) {
    return classNames;
  }
  if (typeof existing === "string") {
    return [existing, ...classNames];
  }
  if (Array.isArray(existing)) {
    return [...existing, ...classNames];
  }
  return (params) => [...normalizeClassValue(existing(params)), ...classNames];
}

function mergeCellClass<TData, TValue>(
  existing: ColDef<TData, TValue>["cellClass"],
  classNames: string[],
): ColDef<TData, TValue>["cellClass"] {
  if (!existing) {
    return classNames;
  }
  if (typeof existing === "string") {
    return [existing, ...classNames];
  }
  if (Array.isArray(existing)) {
    return [...existing, ...classNames];
  }
  return (params) => [...normalizeClassValue(existing(params)), ...classNames];
}

function formatNumber(value: unknown, fractionDigits: number): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return value == null ? EM_DASH : String(value);
  }
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

export function numericCol<TData = unknown, TValue = unknown>(
  colDef: ColDef<TData, TValue>,
): ColDef<TData, TValue> {
  return {
    ...colDef,
    headerClass: mergeHeaderClass(colDef.headerClass, [
      "ag-right-aligned-header",
      mossGridNumericHeaderClass,
    ]),
    cellClass: mergeCellClass(colDef.cellClass, [
      "ag-right-aligned-cell",
      mossGridNumericCellClass,
    ]),
  };
}

export function mossGridCurrencyCol<TData = unknown, TValue = unknown>(
  colDef: ColDef<TData, TValue>,
): ColDef<TData, TValue> {
  return numericCol({
    valueFormatter:
      colDef.valueFormatter ??
      ((params: ValueFormatterParams<TData, TValue>) => formatNumber(params.value, 2)),
    ...colDef,
  });
}

export function mossGridPercentCol<TData = unknown, TValue = unknown>(
  colDef: ColDef<TData, TValue>,
): ColDef<TData, TValue> {
  return numericCol({
    valueFormatter:
      colDef.valueFormatter ??
      ((params: ValueFormatterParams<TData, TValue>) => {
        const formatted = formatNumber(params.value, 2);
        return formatted === EM_DASH ? formatted : `${formatted}%`;
      }),
    ...colDef,
  });
}

export function mossGridBpCol<TData = unknown, TValue = unknown>(
  colDef: ColDef<TData, TValue>,
): ColDef<TData, TValue> {
  return numericCol({
    valueFormatter:
      colDef.valueFormatter ??
      ((params: ValueFormatterParams<TData, TValue>) => {
        const formatted = formatNumber(params.value, 1);
        return formatted === EM_DASH ? formatted : `${formatted} bp`;
      }),
    ...colDef,
  });
}
