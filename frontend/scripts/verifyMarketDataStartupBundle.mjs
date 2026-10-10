#!/usr/bin/env node
/**
 * /market-data 路由启动预算守卫(`npm run guard:market-data-startup`)。
 *
 * 作用:读取 `dist/index.html` 与生产入口 chunk 里的 Vite 依赖清单(`__vite__mapDeps`),
 * 还原 `MarketDataPage-*.js` 这个懒加载路由 chunk 被 `import()` 时浏览器会一次性预加载的
 * 完整资源闭包(JS + CSS),并断言闭包里没有不该出现在市场数据页首屏的东西:
 *   - AG Grid 运行时 / 样式(市场数据页不用 ag-grid,ag-grid 只能由用表格的路由自行懒加载);
 *   - 完整 ApiClient 组合(`client-*.js`,含 `createApiClient` 与全部域客户端);
 *   - 任何 API 域客户端 chunk(`*Client-*.js`):这些必须经 `src/api/clientContext.ts` 的按需
 *     `import()` 加载,页面应从 `api/clientContext` 取 `useApiClient`,而不是从 `api/client`
 *     (后者会把整个组合模块及其全部域客户端静态拖进闭包——2026-09-02 修复前正是这个问题);
 *   - 任何 mock 客户端 chunk(real 模式下 mock 数据不该被预取);
 *   - 市场数据页自己的懒加载子视图 `MarketDataExplorerView-*`(?view=explorer 独立分包);
 *   - 非 market-data、非壳层、非共享 primitives 的其它 feature 页面/模型 chunk 与样式表;
 * 并给闭包 JS 总字节、market-data 自身 JS 字节各设一条 ratchet 天花板。
 *
 * 与首页守卫共用 `startupBundleParsing.mjs` 解析 HTML eager 资源和 Vite 依赖清单。
 * 两份脚本分别保留路由断言、预算和失败回执，共享解析模块不执行任何守卫。
 *
 * 运行前必须先在 frontend 目录执行 `npx vite build`(或 `npm run build`)生成 `dist/`。
 */
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { basename, join, resolve } from "node:path";
import {
  parseHtmlJavaScriptResources,
  parseRouteDeps,
  parseViteDependencyManifest,
  stripViteDependencyManifest,
} from "./startupBundleParsing.mjs";

const frontendRoot = process.cwd();
const distDir = resolve(frontendRoot, "dist");
const assetsDir = join(distDir, "assets");
const indexHtmlPath = join(distDir, "index.html");

/**
 * Ratchet 天花板(1 kB = 1024 B)。只降不升;若确有业务需要提高,需技术负责人签核并在此更新实测值。
 *
 * 2026-09-02 实测(修复 market-data 三处 `useApiClient` 改从 `api/clientContext` 引入之后):
 *   - 闭包 JS 总字节(含路由 chunk 自身与壳层已 eager 的 vendor 组):2,490,771 B ≈ 2432.4 kB
 *     → 天花板 = ceil(2,490,771 × 1.10 / 1024) = 2676 kB
 *   - market-data 自身 JS 字节(`MarketDataPage-*` + `marketData*-*`):112,921 B ≈ 110.3 kB
 *     → 天花板 = ceil(112,921 × 1.10 / 1024) = 122 kB
 */
const CLOSURE_JS_CEILING_KB = 2676;
const MARKET_DATA_SELF_JS_CEILING_KB = 122;

const failures = [];

function addFailure(message) {
  failures.push(message);
}

function readText(path) {
  return readFileSync(path, "utf8");
}

function assetSize(assetPath) {
  const absolutePath = join(distDir, assetPath);
  return existsSync(absolutePath) ? statSync(absolutePath).size : 0;
}

function formatKb(bytes) {
  return `${(bytes / 1024).toFixed(1)} kB`;
}

function findAsset(pattern) {
  return assetFiles.filter((file) => pattern.test(file));
}

function isJsAsset(assetPath) {
  return assetPath.endsWith(".js");
}

function isCssAsset(assetPath) {
  return assetPath.endsWith(".css");
}

function isFullClientAsset(assetPath) {
  return /^assets\/client-[^/]+\.js$/.test(assetPath);
}

/** API 域客户端 chunk:`client-`、`marketDataClient-`、`balanceAnalysisClient-`、`*MockClient-` 等。 */
function isApiClientLayerAsset(assetPath) {
  return /^assets\/[A-Za-z]*[cC]lient-[^/]+\.js$/.test(assetPath);
}

function isAgGridAsset(assetPath) {
  return /^assets\/(?:ag-grid-(?:community|react)|ag-theme-alpine|agGridInstitutional|MossAgGrid)[^/]*\.(?:js|css)$/.test(
    assetPath,
  );
}

function isMockClientAsset(assetPath) {
  return /^assets\/(?:[A-Za-z]*MockClient|[A-Za-z]*Mocks|mockApiClient|mockApiEnvelope)-[^/]+\.js$/.test(assetPath);
}

/** ?view=explorer 的序列浏览器视图是市场数据页自己拆出去的懒加载子视图,不该回到驾驶舱首包。 */
function isMarketDataExplorerViewAsset(assetPath) {
  return /^assets\/MarketDataExplorerView-[^/]+\.(?:js|css)$/.test(assetPath);
}

function isMarketDataSelfJsAsset(assetPath) {
  return /^assets\/(?:MarketData|marketData)[A-Za-z]*-[^/]+\.js$/.test(assetPath);
}

/**
 * 允许出现在闭包里的共享 JS chunk 前缀白名单(2026-09-02 实测)。
 * 不在此名单、也不是 market-data 自身的 JS chunk,一律视为其它 feature 的页面/模型泄漏。
 * 新增一个真正跨页共享的 primitive 时才允许扩充此名单;不要为了让某个 feature chunk 通过而加。
 */
const ALLOWED_SHARED_JS_CHUNK_PATTERNS = [
  // Vite/Rolldown 运行时(壳层已 eager)
  /^rolldown-runtime-/,
  /^preload-helper-/,
  // vite.config.ts 手工分包的 vendor 组
  /^react-vendor-/,
  /^query-vendor-/,
  /^antd-vendor-/,
  /^vendor-misc-/,
  /^zrender-/,
  /^echarts-for-react-/,
  /^echarts-misc-/,
  // src/lib/echarts 薄封装与图表基座/主题
  /^echarts-/,
  /^BaseChart-/,
  // Existing src/components/charts/ChartCard and layout/StateSurface become
  // standalone shared chunks after positions/risk stop importing full client.
  /^ChartCard-/,
  /^StateSurface-/,
  /^chartTheme-/,
  // 共享 utils / pageModel / 主题 token / 查询键 / 轮询
  /^format-/,
  /^pageModel-/,
  /^tokens-/,
  /^designSystem-/,
  /^queryKeys-/,
  /^polling-/,
  /^sparklinePath-/,
  /^choiceMacroFormat-/,
  /^StatusContract-/,
  // 共享页面 primitives(components/layout、components/page、StatusPill、SkeletonBars)
  /^layout-/,
  /^KpiStrip-/,
  /^PagePrimitives-/,
  /^PageAsyncSection-/,
  /^StatusPill-/,
  /^SkeletonBars-/,
  // market 壳层(features/workbench/market-shell,与 MarketHomePage / StockAnalysis 共享)
  /^market-shell-/,
  /^marketWorkbenchNav-/,
  /^marketModuleDrilldowns-/,
];

/** 允许出现在闭包里的样式表前缀:market-data 自身、market 壳层、共享 primitives。 */
const ALLOWED_STYLESHEET_PATTERNS = [
  /^ChartCard-/,
  /^StateSurface-/,
  /^MarketDataPage-/,
  /^market-shell-/,
  /^layout-/,
  /^KpiStrip-/,
  /^PagePrimitives-/,
  /^PageAsyncSection-/,
  /^StatusPill-/,
  /^SkeletonBars-/,
];

function isAllowedSharedJsChunk(assetPath) {
  const name = basename(assetPath);
  return ALLOWED_SHARED_JS_CHUNK_PATTERNS.some((pattern) => pattern.test(name));
}

function isAllowedStylesheet(assetPath) {
  const name = basename(assetPath);
  return ALLOWED_STYLESHEET_PATTERNS.some((pattern) => pattern.test(name));
}

function assertNoBlockedAssets(scope, assets, predicate, label, reason) {
  const blocked = assets.filter(predicate);
  if (blocked.length > 0) {
    addFailure(`${scope} includes ${label}: ${blocked.map((asset) => basename(asset)).join(", ")}. ${reason}`);
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

  for (const assetPath of assetPaths.filter(isJsAsset)) {
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
        `${scope} asset ${basename(assetPath)} appears to contain full client endpoint implementations: ${matchedFullClientMarkers.join(", ")}. The composed ApiClient must only be reached through clientContext's deferred import().`,
      );
    }
    if (searchableSource.includes("createApiClient")) {
      addFailure(
        `${scope} asset ${basename(assetPath)} references createApiClient. Pages must take useApiClient from api/clientContext, not api/client.`,
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
        `${scope} asset ${basename(assetPath)} appears to contain AG Grid runtime or styles: ${matchedAgGridMarkers.join(", ")}. The market-data page does not render an AG Grid table; the grid must stay in its own lazily loaded route chunk.`,
      );
    }
  }
}

if (!existsSync(indexHtmlPath) || !existsSync(assetsDir)) {
  addFailure(
    "Production bundle is missing. Run `npx vite build` (or `npm run build`) before `npm run guard:market-data-startup`.",
  );
}

const assetFiles = existsSync(assetsDir) ? readdirSync(assetsDir) : [];
const indexHtml = existsSync(indexHtmlPath) ? readText(indexHtmlPath) : "";
const htmlInitialAssets = parseHtmlJavaScriptResources(indexHtml);
const entryAsset = htmlInitialAssets.find((asset) => /^assets\/index-[^/]+\.js$/.test(asset));
const marketDataPageChunks = findAsset(/^MarketDataPage-[^/]+\.js$/);
const marketDataExplorerChunks = findAsset(/^MarketDataExplorerView-[^/]+\.js$/);

if (!entryAsset) {
  addFailure("Could not locate the production entry script in dist/index.html.");
}
if (marketDataPageChunks.length !== 1) {
  addFailure(`Expected exactly one MarketDataPage chunk, found ${marketDataPageChunks.length}.`);
}
if (marketDataExplorerChunks.length !== 1) {
  addFailure(
    `Expected exactly one lazily split MarketDataExplorerView chunk, found ${marketDataExplorerChunks.length}. The ?view=explorer series browser must stay out of the cockpit first screen.`,
  );
}

let routeAssets = [];
let closureJsBytes = 0;
let marketDataSelfJsBytes = 0;
let closureCssBytes = 0;

if (entryAsset && marketDataPageChunks.length === 1) {
  const scope = "MarketDataPage preload deps";
  const entrySource = readText(join(distDir, entryAsset));
  const manifest = parseViteDependencyManifest(entrySource, addFailure);
  routeAssets = parseRouteDeps(entrySource, manifest, marketDataPageChunks[0], addFailure);

  const routeJsAssets = routeAssets.filter(isJsAsset);
  const routeCssAssets = routeAssets.filter(isCssAsset);

  assertNoBlockedAssets(
    scope,
    routeAssets,
    isAgGridAsset,
    "AG Grid asset",
    "The market-data page does not use AG Grid; the grid runtime must stay in its own lazily loaded route chunk.",
  );
  assertNoBlockedAssets(
    scope,
    routeAssets,
    isFullClientAsset,
    "full ApiClient chunk",
    "client-*.js composes every domain client; it must only be reached through clientContext's deferred import(). Check for `import { useApiClient } from \"../api/client\"` inside features/market-data and switch it to api/clientContext.",
  );
  assertNoBlockedAssets(
    scope,
    routeAssets,
    isMockClientAsset,
    "mock client chunk",
    "Mock payloads must only load behind clientContext's `mode === \"mock\"` dynamic import(), never in the real-mode preload closure.",
  );
  assertNoBlockedAssets(
    scope,
    routeAssets,
    (assetPath) =>
      isApiClientLayerAsset(assetPath) && !isFullClientAsset(assetPath) && !isMockClientAsset(assetPath),
    "API domain client chunk",
    "Domain clients are loaded on demand by clientContext; a static reference means some market-data module imports api/client or a domain client module directly.",
  );
  assertNoBlockedAssets(
    scope,
    routeAssets,
    isMarketDataExplorerViewAsset,
    "MarketDataExplorerView chunk",
    "The ?view=explorer series browser is split on purpose (see MarketDataPage.tsx) and must not be statically imported by the cockpit.",
  );

  const foreignJsAssets = routeJsAssets.filter(
    (assetPath) =>
      !isMarketDataSelfJsAsset(assetPath) &&
      !isAllowedSharedJsChunk(assetPath) &&
      !isAgGridAsset(assetPath) &&
      !isFullClientAsset(assetPath) &&
      !isMockClientAsset(assetPath) &&
      !isApiClientLayerAsset(assetPath),
  );
  if (foreignJsAssets.length > 0) {
    addFailure(
      `${scope} includes JS chunks that are neither market-data nor an allow-listed shared primitive: ${foreignJsAssets
        .map((asset) => `${basename(asset)} (${formatKb(assetSize(asset))})`)
        .join(", ")}. Either another feature's page/model leaked into the market-data import graph, or a genuinely shared primitive needs adding to ALLOWED_SHARED_JS_CHUNK_PATTERNS.`,
    );
  }

  const foreignStylesheets = routeCssAssets.filter((assetPath) => !isAllowedStylesheet(assetPath));
  if (foreignStylesheets.length > 0) {
    addFailure(
      `${scope} includes stylesheets that belong to other pages: ${foreignStylesheets
        .map((asset) => `${basename(asset)} (${formatKb(assetSize(asset))})`)
        .join(", ")}. Only market-data, market-shell and shared primitive stylesheets may be preloaded with this route.`,
    );
  }

  assertNoEagerClientImplementation(scope, routeAssets);
  assertNoAgGridImplementation(scope, routeAssets);

  closureJsBytes = routeJsAssets.reduce((total, asset) => total + assetSize(asset), 0);
  closureCssBytes = routeCssAssets.reduce((total, asset) => total + assetSize(asset), 0);
  marketDataSelfJsBytes = routeJsAssets
    .filter(isMarketDataSelfJsAsset)
    .reduce((total, asset) => total + assetSize(asset), 0);

  const closureCeilingBytes = CLOSURE_JS_CEILING_KB * 1024;
  if (closureJsBytes > closureCeilingBytes) {
    addFailure(
      `${scope} JS closure is ${closureJsBytes} B (${formatKb(closureJsBytes)}), above the ratchet ceiling of ${CLOSURE_JS_CEILING_KB} kB. Find the new dependency instead of raising the ceiling; raising it requires tech-lead sign-off.`,
    );
  }

  const selfCeilingBytes = MARKET_DATA_SELF_JS_CEILING_KB * 1024;
  if (marketDataSelfJsBytes > selfCeilingBytes) {
    addFailure(
      `market-data own JS (MarketDataPage-* + marketData*-*) is ${marketDataSelfJsBytes} B (${formatKb(marketDataSelfJsBytes)}), above the ratchet ceiling of ${MARKET_DATA_SELF_JS_CEILING_KB} kB. Split the new code behind a lazy boundary instead of raising the ceiling; raising it requires tech-lead sign-off.`,
    );
  }
}

if (failures.length > 0) {
  console.error("[market-data-startup] Bundle guard failed:");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

const summarize = (predicate) =>
  routeAssets
    .filter(predicate)
    .map((asset) => basename(asset))
    .join(", ");

console.log("[market-data-startup] Bundle guard passed.");
console.log(`- Route chunk: ${marketDataPageChunks[0]}`);
console.log(
  `- Closure JS: ${closureJsBytes} B (${formatKb(closureJsBytes)}) of ${CLOSURE_JS_CEILING_KB} kB ceiling; ${routeAssets.filter(isJsAsset).length} chunks`,
);
console.log(
  `- market-data own JS: ${marketDataSelfJsBytes} B (${formatKb(marketDataSelfJsBytes)}) of ${MARKET_DATA_SELF_JS_CEILING_KB} kB ceiling`,
);
console.log(`- Closure CSS: ${closureCssBytes} B (${formatKb(closureCssBytes)}); ${routeAssets.filter(isCssAsset).length} stylesheets`);
console.log(`- market-data chunks: ${summarize(isMarketDataSelfJsAsset)}`);
console.log(
  `- Shared chunks: ${summarize((asset) => isJsAsset(asset) && !isMarketDataSelfJsAsset(asset))}`,
);
console.log(`- Stylesheets: ${summarize(isCssAsset)}`);
console.log(`- Deferred explorer view: ${marketDataExplorerChunks.join(", ")}`);
