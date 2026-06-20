import type {
  CellClassParams,
  ColDef,
  HeaderClassParams,
  ValueFormatterParams,
} from "ag-grid-community";

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

type GridClassInput<TData, TValue> =
  | string
  | string[]
  | ((params: CellClassParams<TData, TValue> | HeaderClassParams<TData>) => string | string[] | null | undefined)
  | null
  | undefined;

function normalizeClassValue(value: string | string[] | null | undefined): string[] {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

function mergeGridClass<TData, TValue>(
  existing: GridClassInput<TData, TValue>,
  classNames: string[],
): GridClassInput<TData, TValue> {
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
    return value == null ? "—" : String(value);
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
    headerClass: mergeGridClass(colDef.headerClass, [
      "ag-right-aligned-header",
      mossGridNumericHeaderClass,
    ]),
    cellClass: mergeGridClass(colDef.cellClass, [
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
        return formatted === "—" ? formatted : `${formatted}%`;
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
        return formatted === "—" ? formatted : `${formatted} bp`;
      }),
    ...colDef,
  });
}
