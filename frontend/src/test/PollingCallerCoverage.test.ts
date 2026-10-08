import { readFileSync } from "node:fs";
import ts from "typescript";
import { expect, it } from "vitest";

// This inventory guards the scoped migration, not runtime or publication behavior.
const callers = [
  ["balance-analysis/hooks/useBalanceAnalysisActions.ts", 1],
  ["market-data/hooks/useMarketDataPageData.ts", 2],
  ["macro-toolkit/pages/useMacroToolkitOperationActions.ts", 4],
  ["workbench/module-home/MarketHomePage.tsx", 1],
  ["pnl/PnlBridgePage.tsx", 1],
  ["pnl/FormalPnlV1Page.tsx", 1],
  ["product-category-pnl/pages/MonthlyOperatingAnalysisBranch.tsx", 1],
  ["product-category-pnl/pages/useProductCategoryRefresh.ts", 1],
  ["product-category-pnl/pages/ProductCategoryAdjustmentAuditPage.tsx", 1],
  ["bond-analytics/components/BondAnalyticsViewContent.tsx", 1],
  ["stock-analysis/hooks/useStockSelectionRefresh.ts", 1],
] as const;

it.each(callers)("wires a page lifetime signal into every polling call in %s", (file, count) => {
  const source = ts.createSourceFile(file, readFileSync(`src/features/${file}`, "utf8"), ts.ScriptTarget.Latest, true, file.endsWith("tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  let found = 0;
  const inspect = (node: ts.Node) => {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === "runPollingTask") {
      found += 1;
      const options = node.arguments[0];
      expect(options && ts.isObjectLiteralExpression(options)).toBe(true);
      if (options && ts.isObjectLiteralExpression(options)) {
        expect(options.properties.some((property) => property.name?.getText(source) === "signal")).toBe(true);
      }
    }
    ts.forEachChild(node, inspect);
  };
  inspect(source);
  expect(found).toBe(count);
});
