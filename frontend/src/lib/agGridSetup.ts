import {
  CellStyleModule,
  ClientSideRowModelModule,
  ColumnAutoSizeModule,
  DateFilterModule,
  LocaleModule,
  ModuleRegistry,
  NumberFilterModule,
  PaginationModule,
  RowStyleModule,
  TextFilterModule,
  TooltipModule,
  ValidationModule,
} from "ag-grid-community";

// Register only the community features MOSS grids actually use instead of
// AllCommunityModule; this keeps the ag-grid chunk substantially smaller.
// If a grid needs a new feature, add its module here (dev builds include
// ValidationModule, which reports the exact missing module by name).
ModuleRegistry.registerModules([
  ClientSideRowModelModule,
  TextFilterModule,
  NumberFilterModule,
  DateFilterModule,
  PaginationModule,
  CellStyleModule,
  RowStyleModule,
  ColumnAutoSizeModule,
  TooltipModule,
  LocaleModule,
]);

if (import.meta.env.DEV || import.meta.env.MODE === "test") {
  ModuleRegistry.registerModules([ValidationModule]);
}
