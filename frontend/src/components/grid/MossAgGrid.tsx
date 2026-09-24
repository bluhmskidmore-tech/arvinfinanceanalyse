import type { CSSProperties } from "react";
import { useMemo } from "react";
import { AgGridReact, type AgGridReactProps } from "ag-grid-react";
import type { ColDef } from "ag-grid-community";

import "../../lib/agGridSetup";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";
import "../../styles/agGridInstitutional.css";
import {
  mossGridDefaultColDef,
  mossGridHeaderHeight,
  mossGridLocaleText,
  mossGridRowHeight,
} from "./gridDefaults";

type MossGridHeight = number | string;

export type MossAgGridProps<TData = unknown> = Omit<
  AgGridReactProps<TData>,
  "theme" | "defaultColDef" | "localeText" | "rowHeight" | "headerHeight"
> & {
  className?: string;
  defaultColDef?: ColDef<TData>;
  empty?: boolean;
  emptyText?: string;
  height?: MossGridHeight;
  headerHeight?: number;
  loadingText?: string;
  localeText?: AgGridReactProps<TData>["localeText"];
  rowHeight?: number;
  style?: CSSProperties;
  "data-testid"?: string;
};

function toCssHeight(height: MossGridHeight | undefined): string | undefined {
  if (height === undefined) {
    return undefined;
  }
  return typeof height === "number" ? `${height}px` : height;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function overlayTemplate(text: string): string {
  return `<span class="moss-ag-grid__overlay-text">${escapeHtml(text)}</span>`;
}

export function MossAgGrid<TData = unknown>({
  className,
  defaultColDef,
  empty = false,
  emptyText = mossGridLocaleText.noRowsToShow,
  height,
  headerHeight = mossGridHeaderHeight,
  loadingText = mossGridLocaleText.loadingOoo,
  localeText,
  rowData,
  rowHeight = mossGridRowHeight,
  style,
  "data-testid": testId,
  ...gridProps
}: MossAgGridProps<TData>) {
  const mergedDefaultColDef = useMemo<ColDef<TData>>(
    () => ({
      ...(mossGridDefaultColDef as ColDef<TData>),
      ...defaultColDef,
    }),
    [defaultColDef],
  );
  const mergedLocaleText = useMemo(
    () => ({
      ...mossGridLocaleText,
      ...localeText,
    }),
    [localeText],
  );
  const wrapperStyle = useMemo<CSSProperties>(
    () => ({
      ...style,
      height: toCssHeight(height) ?? style?.height,
    }),
    [height, style],
  );
  const wrapperClassName = ["moss-ag-grid", "ag-theme-alpine", className]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={wrapperClassName} data-testid={testId ?? "moss-ag-grid"} style={wrapperStyle}>
      <AgGridReact<TData>
        {...gridProps}
        theme="legacy"
        rowData={empty ? [] : rowData}
        defaultColDef={mergedDefaultColDef}
        localeText={mergedLocaleText}
        rowHeight={rowHeight}
        headerHeight={headerHeight}
        overlayNoRowsTemplate={overlayTemplate(emptyText)}
        overlayLoadingTemplate={overlayTemplate(loadingText)}
      />
    </div>
  );
}
