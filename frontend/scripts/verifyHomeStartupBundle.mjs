#!/usr/bin/env node
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { basename, join, resolve } from "node:path";

const frontendRoot = process.cwd();
const distDir = resolve(frontendRoot, "dist");
const assetsDir = join(distDir, "assets");
const indexHtmlPath = join(distDir, "index.html");

const failures = [];

function addFailure(message) {
  failures.push(message);
}

function readText(path) {
  return readFileSync(path, "utf8");
}

function readAssetText(assetPath) {
  const absolutePath = join(distDir, assetPath);
  if (!existsSync(absolutePath)) {
    return "";
  }
  return readText(absolutePath);
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function findAsset(pattern) {
  return assetFiles.filter((file) => pattern.test(file));
}

function stripViteDependencyManifest(source) {
  return source.replace(/const __vite__mapDeps=.*?;\s*/s, "");
}

function parseHtmlJavaScriptResources(indexHtml) {
  const resources = new Set();

  for (const match of indexHtml.matchAll(/<script\b[^>]*\bsrc=["']([^"']+)["'][^>]*>/gi)) {
    const tag = match[0];
    const src = match[1];
    if (/type=["']module["']/i.test(tag) && src.startsWith("/assets/") && src.endsWith(".js")) {
      resources.add(src.slice(1));
    }
  }

  for (const match of indexHtml.matchAll(/<link\b[^>]*\bhref=["']([^"']+)["'][^>]*>/gi)) {
    const tag = match[0];
    const href = match[1];
    if (/rel=["']modulepreload["']/i.test(tag) && href.startsWith("/assets/") && href.endsWith(".js")) {
      resources.add(href.slice(1));
    }
  }

  return [...resources];
}

function parseHtmlStylesheetResources(indexHtml) {
  const resources = new Set();

  for (const match of indexHtml.matchAll(/<link\b[^>]*\bhref=["']([^"']+)["'][^>]*>/gi)) {
    const tag = match[0];
    const href = match[1];
    if (/rel=["']stylesheet["']/i.test(tag) && href.startsWith("/assets/")) {
      resources.add(href.slice(1));
    }
  }

  return [...resources];
}

function parseViteDependencyManifest(entrySource) {
  const match = /m\.f\s*=\s*(\[[^\]]*\])/.exec(entrySource);
  if (!match) {
    addFailure("Could not locate Vite dependency manifest in the production entry chunk.");
    return [];
  }

  try {
    return JSON.parse(match[1]);
  } catch (error) {
    addFailure(`Could not parse Vite dependency manifest: ${error.message}`);
    return [];
  }
}

function parseRouteDeps(entrySource, manifest, routeChunk) {
  const routePattern = new RegExp(
    `import\\((["'\`])\\.\\/${escapeRegExp(routeChunk)}\\1\\)[\\s\\S]{0,800}?__vite__mapDeps\\(\\[([^\\]]*)\\]\\)`,
  );
  const match = routePattern.exec(entrySource);
  if (!match) {
    addFailure(`Could not locate dependency preload list for ${routeChunk}.`);
    return [];
  }

  return match[2]
    .split(",")
    .map((value) => Number.parseInt(value.trim(), 10))
    .filter(Number.isInteger)
    .map((index) => manifest[index])
    .filter(Boolean);
}

function isFullClientAsset(assetPath) {
  return /^assets\/client-[^/]+\.js$/.test(assetPath);
}

function isEChartsAsset(assetPath) {
  return /^assets\/(?:echarts|echarts-for-react|echarts-misc|zrender)[^/]*\.js$/.test(assetPath);
}

function isAgGridAsset(assetPath) {
  return /^assets\/(?:ag-grid-(?:community|react)|ag-theme-alpine)[^/]*\.(?:js|css)$/.test(assetPath);
}

function isAntdVendorAsset(assetPath) {
  return /^assets\/antd-vendor-[^/]+\.js$/.test(assetPath);
}

function isHomeSupplementalAsset(assetPath) {
  return /^assets\/homeSupplementalClient-[^/]+\.js$/.test(assetPath);
}

function isHomeMarketTickerAsset(assetPath) {
  return /^assets\/homeMarketTickerClient-[^/]+\.js$/.test(assetPath);
}

function isWorkbenchShellMarketTickerAsset(assetPath) {
  return /^assets\/(?:WorkbenchShellMarketTicker|workbenchShellTicker)-[^/]+\.js$/.test(assetPath);
}

function isFullDashboardHomeStylesheet(assetPath) {
  return /^assets\/dashboardHome-[^/]+\.css$/.test(assetPath);
}

function isHomeShellStylesheet(assetPath) {
  return /^assets\/(?:dashboardHomeFirstScreenView|dashboardHomeShell)-[^/]+\.css$/.test(assetPath);
}

function isLightweightHomeShellStylesheetContent(source) {
  return (
    source.includes("dhTerminalHero") &&
    source.includes("dhTerminalRiskGrid") &&
    source.includes("dhDecisionAction") &&
    !source.includes("dhWorkGrid") &&
    !source.includes("dhTerminalChart") &&
    !source.includes("dhTerminalHoldings")
  );
}

function isInstitutionalConsoleStylesheet(assetPath) {
  return /^assets\/workbenchInstitutionalConsole-[^/]+\.css$/.test(assetPath);
}

function isNonHomeWorkbenchChromeStylesheet(assetPath) {
  return /^assets\/workbenchDeferredChrome-[^/]+\.css$/.test(assetPath);
}

function assertNoBlockedAssets(scope, assets, predicate, label) {
  const blocked = assets.filter(predicate);
  if (blocked.length > 0) {
    addFailure(`${scope} includes ${label}: ${blocked.join(", ")}`);
  }
}

function assertNoEagerClientImplementation(scope, assetPaths) {
  const fullClientEndpointMarkers = [
    "/api/dashboard/core_metrics",
    "/api/bond-analytics/credit-spread-migration",
    "/api/pnl-attribution/campisi/four-effects",
    "/ui/balance-analysis/workbook",
    "/api/positions/bonds?",
  ];

  for (const assetPath of assetPaths) {
    const absolutePath = join(distDir, assetPath);
    if (!existsSync(absolutePath)) {
      addFailure(`${scope} references missing asset ${assetPath}.`);
      continue;
    }

    const searchableSource = stripViteDependencyManifest(readText(absolutePath));
    const matchedFullClientMarkers = fullClientEndpointMarkers.filter((marker) =>
      searchableSource.includes(marker),
    );
    if (matchedFullClientMarkers.length >= 2) {
      addFailure(
        `${scope} asset ${basename(assetPath)} appears to contain full client endpoint implementations: ${matchedFullClientMarkers.join(", ")}`,
      );
    }
  }
}

function assertNoAgGridImplementation(scope, assetPaths) {
  const agGridImplementationMarkers = [
    "ag-grid-community",
    "ag-grid-react",
    "ag-theme-alpine",
    "AgGridReact",
    "AllCommunityModule",
    "ModuleRegistry",
    ".ag-root-wrapper",
  ];

  for (const assetPath of assetPaths) {
    const absolutePath = join(distDir, assetPath);
    if (!existsSync(absolutePath)) {
      addFailure(`${scope} references missing asset ${assetPath}.`);
      continue;
    }

    const searchableSource = stripViteDependencyManifest(readText(absolutePath));
    const matchedAgGridMarkers = agGridImplementationMarkers.filter((marker) =>
      searchableSource.includes(marker),
    );
    if (matchedAgGridMarkers.length > 0) {
      addFailure(
        `${scope} asset ${basename(assetPath)} appears to contain AG Grid runtime or styles: ${matchedAgGridMarkers.join(", ")}`,
      );
    }
  }
}

if (!existsSync(indexHtmlPath) || !existsSync(assetsDir)) {
  addFailure("Production bundle is missing. Run `npm run build` before `npm run guard:home-startup`.");
}

const assetFiles = existsSync(assetsDir) ? readdirSync(assetsDir).filter((file) => file.endsWith(".js")) : [];
const indexHtml = existsSync(indexHtmlPath) ? readText(indexHtmlPath) : "";
const htmlInitialAssets = parseHtmlJavaScriptResources(indexHtml);
const htmlInitialStyleAssets = parseHtmlStylesheetResources(indexHtml);
const entryAsset = htmlInitialAssets.find((asset) => /^assets\/index-[^/]+\.js$/.test(asset));
const dashboardChunks = findAsset(/^DashboardHomePage-[^/]+\.js$/);
const fullClientChunks = findAsset(/^client-[^/]+\.js$/);
const homeSnapshotFetchChunks = findAsset(/^executiveHomeSnapshotFetch-[^/]+\.js$/);
const homeExecutiveChunks = findAsset(/^homeExecutiveClient-[^/]+\.js$/);
const homeMarketTickerChunks = findAsset(/^homeMarketTickerClient-[^/]+\.js$/);
const homeSupplementalChunks = findAsset(/^homeSupplementalClient-[^/]+\.js$/);
const chartChunks = findAsset(/^(?:echarts|echarts-for-react|echarts-misc|zrender)[^/]*\.js$/);

if (!entryAsset) {
  addFailure("Could not locate the production entry script in dist/index.html.");
}
if (dashboardChunks.length !== 1) {
  addFailure(`Expected exactly one DashboardHomePage chunk, found ${dashboardChunks.length}.`);
}
if (fullClientChunks.length !== 1) {
  addFailure(`Expected exactly one deferred full client chunk, found ${fullClientChunks.length}.`);
}
if (homeExecutiveChunks.length !== 1) {
  addFailure(`Expected exactly one home executive fast-path chunk, found ${homeExecutiveChunks.length}.`);
}
if (homeMarketTickerChunks.length !== 1) {
  addFailure(`Expected exactly one home market ticker fast-path chunk, found ${homeMarketTickerChunks.length}.`);
}
if (homeSnapshotFetchChunks.length !== 1) {
  addFailure(`Expected exactly one home snapshot fetch helper chunk, found ${homeSnapshotFetchChunks.length}.`);
}
if (homeSupplementalChunks.length !== 1) {
  addFailure(`Expected exactly one home supplemental fast-path chunk, found ${homeSupplementalChunks.length}.`);
}
if (chartChunks.length === 0) {
  addFailure("Expected ECharts runtime to be split into deferred chart chunks.");
}

assertNoBlockedAssets("dist/index.html eager JS", htmlInitialAssets, isFullClientAsset, "full ApiClient chunk");
assertNoBlockedAssets("dist/index.html eager JS", htmlInitialAssets, isEChartsAsset, "ECharts chunk");
assertNoBlockedAssets("dist/index.html eager JS", htmlInitialAssets, isAgGridAsset, "AG Grid asset");
assertNoBlockedAssets("dist/index.html eager JS", htmlInitialAssets, isAntdVendorAsset, "Ant Design vendor chunk");
assertNoBlockedAssets("dist/index.html eager CSS", htmlInitialStyleAssets, isAgGridAsset, "AG Grid asset");
assertNoBlockedAssets(
  "dist/index.html eager CSS",
  htmlInitialStyleAssets,
  isInstitutionalConsoleStylesheet,
  "institutional console stylesheet",
);
assertNoBlockedAssets(
  "dist/index.html eager CSS",
  htmlInitialStyleAssets,
  isNonHomeWorkbenchChromeStylesheet,
  "non-home workbench chrome stylesheet",
);
assertNoBlockedAssets(
  "dist/index.html eager JS",
  htmlInitialAssets,
  isHomeSupplementalAsset,
  "home supplemental chunk",
);
assertNoBlockedAssets(
  "dist/index.html eager JS",
  htmlInitialAssets,
  isHomeMarketTickerAsset,
  "home market ticker chunk",
);
assertNoBlockedAssets(
  "dist/index.html eager JS",
  htmlInitialAssets,
  isWorkbenchShellMarketTickerAsset,
  "workbench shell market ticker chunk",
);
assertNoEagerClientImplementation("dist/index.html eager JS", htmlInitialAssets);
assertNoAgGridImplementation("dist/index.html eager JS", htmlInitialAssets);
assertNoAgGridImplementation("dist/index.html eager CSS", htmlInitialStyleAssets);

let homeRouteAssets = [];
if (entryAsset && dashboardChunks.length === 1) {
  const entrySource = readText(join(distDir, entryAsset));
  const manifest = parseViteDependencyManifest(entrySource);
  homeRouteAssets = parseRouteDeps(entrySource, manifest, dashboardChunks[0]);

  assertNoBlockedAssets("DashboardHomePage preload deps", homeRouteAssets, isFullClientAsset, "full ApiClient chunk");
  assertNoBlockedAssets("DashboardHomePage preload deps", homeRouteAssets, isEChartsAsset, "ECharts chunk");
  assertNoBlockedAssets("DashboardHomePage preload deps", homeRouteAssets, isAgGridAsset, "AG Grid asset");
  assertNoBlockedAssets(
    "DashboardHomePage preload deps",
    homeRouteAssets,
    isHomeSupplementalAsset,
    "home supplemental chunk",
  );
  assertNoBlockedAssets(
    "DashboardHomePage preload deps",
    homeRouteAssets,
    isHomeMarketTickerAsset,
    "home market ticker chunk",
  );
  assertNoBlockedAssets(
    "DashboardHomePage preload deps",
    homeRouteAssets,
    isWorkbenchShellMarketTickerAsset,
    "workbench shell market ticker chunk",
  );
  assertNoBlockedAssets(
    "DashboardHomePage preload deps",
    homeRouteAssets,
    isFullDashboardHomeStylesheet,
    "full dashboard home stylesheet",
  );
  assertNoBlockedAssets(
    "DashboardHomePage preload deps",
    homeRouteAssets,
    isInstitutionalConsoleStylesheet,
    "institutional console stylesheet",
  );
  assertNoBlockedAssets(
    "DashboardHomePage preload deps",
    homeRouteAssets,
    isNonHomeWorkbenchChromeStylesheet,
    "non-home workbench chrome stylesheet",
  );
  const homeShellStylesheets = homeRouteAssets.filter((assetPath) => assetPath.endsWith(".css"));
  const hasHomeShellStylesheet = homeShellStylesheets.some(
    (assetPath) =>
      isHomeShellStylesheet(assetPath) ||
      isLightweightHomeShellStylesheetContent(readAssetText(assetPath)),
  );
  if (!hasHomeShellStylesheet) {
    addFailure("DashboardHomePage preload deps should include the lightweight home shell stylesheet.");
  }
  assertNoEagerClientImplementation("DashboardHomePage preload deps", homeRouteAssets);
  assertNoAgGridImplementation("DashboardHomePage preload deps", homeRouteAssets);
}

if (homeExecutiveChunks.length === 1) {
  const homeExecutiveSource = readText(join(assetsDir, homeExecutiveChunks[0]));
  if (homeExecutiveSource.includes("createApiClient")) {
    addFailure(`${homeExecutiveChunks[0]} should not import or compose the full ApiClient.`);
  }
  if (homeSnapshotFetchChunks.length === 1 && !homeExecutiveSource.includes(`./${homeSnapshotFetchChunks[0]}`)) {
    addFailure(`${homeExecutiveChunks[0]} should depend on ${homeSnapshotFetchChunks[0]} for snapshot fetches.`);
  }
}

if (homeSnapshotFetchChunks.length === 1) {
  const homeSnapshotFetchSource = readText(join(assetsDir, homeSnapshotFetchChunks[0]));
  if (!homeSnapshotFetchSource.includes("/ui/home/snapshot")) {
    addFailure(`${homeSnapshotFetchChunks[0]} does not contain the home snapshot endpoint.`);
  }
}

if (homeSupplementalChunks.length === 1) {
  const homeSupplementalSource = readText(join(assetsDir, homeSupplementalChunks[0]));
  if (!homeSupplementalSource.includes("/api/dashboard/core_metrics")) {
    addFailure(`${homeSupplementalChunks[0]} does not contain the lightweight home supplemental endpoints.`);
  }
  if (homeSupplementalSource.includes("createApiClient")) {
    addFailure(`${homeSupplementalChunks[0]} should not import or compose the full ApiClient.`);
  }
}

if (homeMarketTickerChunks.length === 1) {
  const homeMarketTickerSource = readText(join(assetsDir, homeMarketTickerChunks[0]));
  const requiredMarkers = [
    "/ui/market-data/rates",
    "/ui/news/choice-events/latest",
    "/ui/calendar/supply-auctions",
  ];
  const missingMarkers = requiredMarkers.filter((marker) => !homeMarketTickerSource.includes(marker));
  if (missingMarkers.length > 0) {
    addFailure(
      `${homeMarketTickerChunks[0]} does not contain the lightweight home market ticker endpoints: ${missingMarkers.join(", ")}`,
    );
  }
  const heavyMarketMarkers = [
    "/ui/preview/source-foundation",
    "/ui/market-data/livermore",
    "/ui/market-data/catalog",
    "/ui/macro/bond-linkage",
  ];
  const matchedHeavyMarkers = heavyMarketMarkers.filter((marker) => homeMarketTickerSource.includes(marker));
  if (matchedHeavyMarkers.length > 0) {
    addFailure(
      `${homeMarketTickerChunks[0]} appears to contain full market-data endpoint implementations: ${matchedHeavyMarkers.join(", ")}`,
    );
  }
  if (homeMarketTickerSource.includes("createApiClient")) {
    addFailure(`${homeMarketTickerChunks[0]} should not import or compose the full ApiClient.`);
  }
}

if (failures.length > 0) {
  console.error("[home-startup] Bundle guard failed:");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

console.log("[home-startup] Bundle guard passed.");
console.log(`- HTML eager JS: ${htmlInitialAssets.map((asset) => basename(asset)).join(", ")}`);
console.log(`- HTML eager CSS: ${htmlInitialStyleAssets.map((asset) => basename(asset)).join(", ")}`);
console.log(`- DashboardHomePage deps: ${homeRouteAssets.map((asset) => basename(asset)).join(", ")}`);
console.log(`- Fast path chunks: ${[...homeSnapshotFetchChunks, ...homeExecutiveChunks, ...homeMarketTickerChunks, ...homeSupplementalChunks].join(", ")}`);
console.log(`- Deferred chart chunks: ${chartChunks.join(", ")}`);
