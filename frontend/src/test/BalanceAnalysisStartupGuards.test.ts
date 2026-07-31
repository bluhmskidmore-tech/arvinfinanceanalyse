import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const FRONTEND_ROOT = process.cwd();
const PACKAGE_JSON_PATH = resolve(FRONTEND_ROOT, "package.json");
const STARTUP_GUARD_PATH = resolve(
  FRONTEND_ROOT,
  "scripts/verifyBalanceAnalysisStartupRuntime.mjs",
);
const CLIENT_CONTEXT_PATH = resolve(FRONTEND_ROOT, "src/api/clientContext.ts");
const HOME_SUPPLEMENTAL_CLIENT_PATH = resolve(
  FRONTEND_ROOT,
  "src/api/homeSupplementalClient.ts",
);
const PAGE_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/balance-analysis/pages/BalanceAnalysisPage.tsx",
);
const CONTRIBUTION_ROW_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/balance-analysis/components/BalanceContributionRow.tsx",
);
const DEFERRED_GRID_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/balance-analysis/components/DeferredBalanceAnalysisGrid.tsx",
);
const DATA_HOOK_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/balance-analysis/hooks/useBalanceAnalysisData.ts",
);

describe("balance-analysis startup guards", () => {
  it("wires the production runtime guard into npm scripts", () => {
    const packageJson = JSON.parse(readFileSync(PACKAGE_JSON_PATH, "utf8")) as {
      scripts?: Record<string, string>;
    };
    const guardSource = readFileSync(STARTUP_GUARD_PATH, "utf8");

    expect(packageJson.scripts?.["guard:balance-startup"]).toBe(
      "node scripts/verifyBalanceAnalysisStartupRuntime.mjs",
    );
    expect(packageJson.scripts?.["guard:balance-startup:runtime"]).toBe(
      "node scripts/verifyBalanceAnalysisStartupRuntime.mjs --build",
    );
    expect(guardSource).toContain("/balance-analysis");
    expect(guardSource).toContain("/ui/balance-movement-analysis/dates");
    expect(guardSource).toContain("/api/analysis/adb/comparison");
    expect(guardSource).toContain("fullClientAssets");
    expect(guardSource).toContain("/^client-");
    expect(guardSource).toContain("startupAgGridAssets");
    expect(guardSource).toContain("expandedAgGridAssets");
    expect(guardSource).toContain("/^agGridInstitutional-");
  });

  it("keeps startup reads on the lightweight API client path", () => {
    const pageSource = readFileSync(PAGE_PATH, "utf8");
    const dataHookSource = readFileSync(DATA_HOOK_PATH, "utf8");
    const clientContextSource = readFileSync(CLIENT_CONTEXT_PATH, "utf8");
    const homeSupplementalSource = readFileSync(
      HOME_SUPPLEMENTAL_CLIENT_PATH,
      "utf8",
    );
    const supplementalMethodSet = clientContextSource.match(
      /const HOME_SUPPLEMENTAL_METHODS[\s\S]*?\]\);/,
    )?.[0];

    for (const source of [pageSource, dataHookSource]) {
      expect(source).toContain("../../../api/clientContext");
      expect(source).not.toContain('from "../../../api/client"');
      expect(source).not.toContain("from '../../../api/client'");
    }
    for (const method of [
      "getBalanceAnalysisDates",
      "getBalanceAnalysisOverview",
      "getBalanceAnalysisSummary",
      "getBalanceAnalysisWorkbook",
      "getBalanceAnalysisCurrentUser",
      "getBalanceAnalysisSummaryByBasis",
      "getBalanceAnalysisDetail",
      "getBalanceAnalysisAdvancedAttribution",
      "getBalanceAnalysisDecisionItems",
      "getBalanceMovementDates",
      "getBalanceMovementAnalysis",
      "getAdbComparison",
    ]) {
      expect(supplementalMethodSet).toContain(method);
      expect(homeSupplementalSource).toContain(method);
    }
    expect(homeSupplementalSource).toContain('import("./balanceMovementClient")');
    expect(homeSupplementalSource).toContain('import("./liabilityAdbClient")');
  });

  it("keeps AG Grid behind closed balance-analysis details", () => {
    const pageSource = readFileSync(PAGE_PATH, "utf8");
    const contributionRowSource = readFileSync(CONTRIBUTION_ROW_PATH, "utf8");
    const deferredGridSource = readFileSync(DEFERRED_GRID_PATH, "utf8");

    expect(pageSource).toContain("DeferredBalanceAnalysisGrid");
    expect(pageSource).not.toContain('import { MossAgGrid }');
    expect(contributionRowSource).toContain("balance-analysis-contribution-table");
    expect(contributionRowSource).not.toContain("ag-grid-react");
    expect(contributionRowSource).not.toContain("agGridSetup");
    expect(deferredGridSource).toContain(
      'import("../../../components/grid/MossAgGrid")',
    );
    expect(deferredGridSource).toContain('closest("details")');
    expect(deferredGridSource).toContain('addEventListener("toggle"');
  });
});
