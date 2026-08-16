import { createServer } from "node:http";
import { existsSync, statSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { extname, join, normalize, relative } from "node:path";
import { resolve } from "node:path";
import { chromium } from "playwright";

const FIRST_SCREEN_OBSERVATION_MS = 400;
const HOME_POST_FIRST_SCREEN_MAX_WAIT_MS = 18_000;
const REQUEST_POLL_INTERVAL_MS = 250;
const NON_HOME_SETTLE_MS = 2_000;
const frontendRoot = process.cwd();
const distRoot = resolve(frontendRoot, "dist");
const distIndexPath = resolve(frontendRoot, "dist/index.html");
const apiTarget = process.env.MOSS_HOME_STARTUP_API_TARGET ?? process.env.MOSS_VITE_API_PROXY ?? "http://127.0.0.1:7888";
const productionBundleInputs = [
  "package.json",
  "vite.config.ts",
  "src/app/App.tsx",
  "src/router/routes.tsx",
  "src/api/clientContext.ts",
  "src/layouts/WorkbenchShell.tsx",
  "src/layouts/WorkbenchShellMarketTicker.tsx",
  "src/layouts/workbenchShellTicker.ts",
  "src/features/workbench/dashboard-home/DashboardHomePage.tsx",
  "src/features/workbench/dashboard-home/DashboardHomeOptionTwoOverview.tsx",
  "src/features/workbench/dashboard-home/DashboardHomeOptionTwoLayout.tsx",
  "src/features/workbench/dashboard-home/dashboardHomeOptionTwoShared.ts",
  "src/features/workbench/dashboard-home/dashboardHomeFirstScreenView.ts",
  "src/features/workbench/dashboard-home/dashboardHomeFirstScreenMockView.ts",
  "src/features/workbench/dashboard-home/DeferredTerminalHomeContent.tsx",
  "src/features/workbench/dashboard-home/DeferredTerminalHomeBody.tsx",
  "src/features/workbench/dashboard-home/useDashboardHomeFirstScreenViewModel.ts",
  "src/features/workbench/dashboard-home/useDashboardHomeSupplementalHydration.ts",
  "src/features/workbench/dashboard-home/useMockHomeFirstScreenView.ts",
  "src/features/workbench/dashboard-home/useDashboardHomeViewModel.ts",
  "src/features/workbench/dashboard-home/useDashboardHomeBodyData.ts",
  "src/features/workbench/dashboard-home/dashboardHomeShell.module.css",
  "src/features/workbench/dashboard-home/dashboardHomeOptionTwo.module.css",
  "src/features/workbench/dashboard-home/dashboardHomeHoldingDrawer.module.css",
  "src/styles/global.css",
  "src/styles/workbenchInstitutionalConsole.css",
  "src/styles/workbenchDeferredChrome.css",
].map((path) => resolve(frontendRoot, path));

const failures = [];

function addFailure(message) {
  failures.push(message);
}

function count(urls, needle) {
  return urls.filter((requestUrl) => requestUrl.includes(needle)).length;
}

function countAny(urls, needles) {
  return urls.filter((requestUrl) => needles.some((needle) => requestUrl.includes(needle))).length;
}

function firstRequestAt(requests, needles) {
  const match = requests.find((entry) => needles.some((needle) => entry.url.includes(needle)));
  return match?.t ?? null;
}

async function waitForTrackedRequest(page, requestLog, needles, timeoutMs) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (firstRequestAt(requestLog, needles) != null) {
      return true;
    }
    await page.waitForTimeout(REQUEST_POLL_INTERVAL_MS);
  }
  return firstRequestAt(requestLog, needles) != null;
}

async function waitForTrackedRequests(page, requestLog, needleGroups, timeoutMs) {
  if (needleGroups.length === 1) {
    return waitForTrackedRequest(page, requestLog, needleGroups[0], timeoutMs);
  }

  const startedAt = Date.now();
  const allRequestsStarted = () =>
    needleGroups.every((needles) => firstRequestAt(requestLog, needles) != null);

  while (Date.now() - startedAt < timeoutMs) {
    if (allRequestsStarted()) {
      return true;
    }
    await page.waitForTimeout(REQUEST_POLL_INTERVAL_MS);
  }
  return allRequestsStarted();
}

function normalizeRequest(entry) {
  return {
    t: entry.t,
    type: entry.type,
    url: entry.url.replace(/^https?:\/\/[^/]+/, ""),
  };
}

function trackUrl(requestUrl) {
  return (
    requestUrl.includes("/ui/") ||
    requestUrl.includes("/api/") ||
    requestUrl.includes("/assets/")
  );
}

function assertFreshProductionBundle() {
  if (!existsSync(distIndexPath)) {
    addFailure("Production preview bundle is missing. Run `npm run build` before this guard.");
    return;
  }

  const builtAt = statSync(distIndexPath).mtimeMs;
  const staleInputs = productionBundleInputs
    .filter((path) => existsSync(path))
    .filter((path) => statSync(path).mtimeMs > builtAt + 1)
    .map((path) => path.replace(`${frontendRoot}\\`, "").replaceAll("\\", "/"));

  if (staleInputs.length > 0) {
    addFailure(
      `Production preview bundle is older than source inputs: ${staleInputs.slice(0, 8).join(", ")}. Run npm run build first.`,
    );
  }
}

function contentTypeForPath(path) {
  switch (extname(path)) {
    case ".css":
      return "text/css; charset=utf-8";
    case ".html":
      return "text/html; charset=utf-8";
    case ".js":
      return "text/javascript; charset=utf-8";
    case ".json":
      return "application/json; charset=utf-8";
    case ".svg":
      return "image/svg+xml";
    case ".wasm":
      return "application/wasm";
    default:
      return "application/octet-stream";
  }
}

function distFilePathForRequest(pathname) {
  const decodedPath = decodeURIComponent(pathname);
  const normalizedPath = normalize(decodedPath).replace(/^(\.\.[/\\])+/, "");
  const relativePath = normalizedPath === "/" || normalizedPath === "." ? "index.html" : normalizedPath.replace(/^[/\\]/, "");
  const filePath = join(distRoot, relativePath);
  const relativeToDist = relative(distRoot, filePath);
  if (relativeToDist.startsWith("..") || relativeToDist === "" || /^[A-Za-z]:/.test(relativeToDist)) {
    return distIndexPath;
  }
  return filePath;
}

async function proxyApiRequest(request, response, requestUrl) {
  const targetUrl = new URL(`${requestUrl.pathname}${requestUrl.search}`, apiTarget);
  const headers = new Headers(request.headers);
  headers.set("host", targetUrl.host);
  const init = {
    method: request.method,
    headers,
    redirect: "manual",
  };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request;
    init.duplex = "half";
  }

  const upstream = await fetch(targetUrl, init);
  const responseHeaders = Object.fromEntries(upstream.headers.entries());
  delete responseHeaders["content-encoding"];
  delete responseHeaders["content-length"];
  delete responseHeaders["transfer-encoding"];
  if (!upstream.body) {
    response.writeHead(upstream.status, responseHeaders);
    response.end();
    return;
  }
  const body = Buffer.from(await upstream.arrayBuffer());
  response.writeHead(upstream.status, responseHeaders);
  response.end(body);
}

async function serveDistRequest(request, response) {
  const requestUrl = new URL(request.url ?? "/", "http://127.0.0.1");
  if (
    requestUrl.pathname.startsWith("/ui/") ||
    requestUrl.pathname.startsWith("/api/") ||
    requestUrl.pathname.startsWith("/health/")
  ) {
    await proxyApiRequest(request, response, requestUrl);
    return;
  }

  let filePath = distFilePathForRequest(requestUrl.pathname);
  if (!existsSync(filePath) || statSync(filePath).isDirectory()) {
    filePath = distIndexPath;
  }
  try {
    const body = await readFile(filePath);
    response.writeHead(200, {
      "content-type": contentTypeForPath(filePath),
      "cache-control": "no-store",
    });
    response.end(body);
  } catch {
    response.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    response.end("not found");
  }
}

async function createProductionStaticServer() {
  const server = createServer((request, response) => {
    void serveDistRequest(request, response).catch((error) => {
      response.writeHead(502, { "content-type": "text/plain; charset=utf-8" });
      response.end(error instanceof Error ? error.message : String(error));
    });
  });

  await new Promise((resolveListen, rejectListen) => {
    server.once("error", rejectListen);
    server.listen(0, "127.0.0.1", () => {
      server.off("error", rejectListen);
      resolveListen(undefined);
    });
  });

  const address = server.address();
  if (!address || typeof address === "string") {
    throw new Error("Production static server did not expose a TCP address.");
  }
  return {
    baseUrl: `http://127.0.0.1:${address.port}/`,
    close: () => new Promise((resolveClose, rejectClose) => {
      server.close((error) => {
        if (error) {
          rejectClose(error);
          return;
        }
        resolveClose(undefined);
      });
    }),
  };
}

function createRuntimeLog(page) {
  const startedAt = Date.now();
  const requestLog = [];
  const responseLog = [];
  const browserMessages = [];

  page.on("request", (request) => {
    const requestUrl = request.url();
    if (!trackUrl(requestUrl)) {
      return;
    }
    requestLog.push({
      t: Date.now() - startedAt,
      method: request.method(),
      type: request.resourceType(),
      url: requestUrl,
    });
  });

  page.on("response", (response) => {
    const responseUrl = response.url();
    if (!trackUrl(responseUrl)) {
      return;
    }
    responseLog.push({
      t: Date.now() - startedAt,
      status: response.status(),
      url: responseUrl,
    });
  });

  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") {
      browserMessages.push({
        t: Date.now() - startedAt,
        type: message.type(),
        text: message.text(),
      });
    }
  });

  page.on("pageerror", (error) => {
    browserMessages.push({
      t: Date.now() - startedAt,
      type: "pageerror",
      text: error.message,
    });
  });

  return { requestLog, responseLog, browserMessages };
}

async function createIsolatedPage(browser) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  // Any routing disables the HTTP cache in Playwright, keeping route samples independent.
  await context.route("**/*", (route) => route.continue());
  const page = await context.newPage();

  return { context, page };
}

function failOnUnexpectedResponses(scope, responseLog) {
  const failedResponses = responseLog.filter((entry) => entry.status >= 400);
  if (failedResponses.length > 0) {
    addFailure(
      `${scope} saw ${failedResponses.length} failed responses: ${failedResponses
        .slice(0, 5)
        .map((entry) => `${entry.status} ${entry.url.replace(/^https?:\/\/[^/]+/, "")}`)
        .join(", ")}`,
    );
  }
  return failedResponses.length;
}

async function sampleHome(page, baseUrl) {
  const { requestLog, responseLog, browserMessages } = createRuntimeLog(page);

  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 30_000 });
  await page.waitForSelector('[data-testid="dashboard-home-page"]', { timeout: 30_000 });
  await page.waitForSelector('[data-testid="dashboard-home-hero"]', { timeout: 30_000 });
  await page.waitForTimeout(FIRST_SCREEN_OBSERVATION_MS);

  const initialUrls = requestLog.map((entry) => entry.url);
  await page.locator('[data-testid="dashboard-home-scroll-root"]').evaluate((node) => {
    node.scrollTop = node.scrollHeight;
  });
  const trackedRequestsArrived = await waitForTrackedRequests(
    page,
    requestLog,
    [
      ["/ui/market-data/rates"],
      ["/ui/calendar/supply-auctions"],
      ["/ui/news/choice-events/latest"],
      ["/ui/home/income-trend"],
      ["/ui/bond-dashboard/home-summary", "/api/bond-dashboard/home-summary"],
    ],
    HOME_POST_FIRST_SCREEN_MAX_WAIT_MS,
  );
  if (!trackedRequestsArrived) {
    addFailure(
      `home tracked data requests did not all arrive within ${HOME_POST_FIRST_SCREEN_MAX_WAIT_MS}ms.`,
    );
  }

  const allUrls = requestLog.map((entry) => entry.url);
  const formalNeedles = [
    "/ui/bond-analytics/credit-spread-migration",
    "/ui/bond-analytics/return-decomposition",
    "/ui/pnl-attribution/campisi-four-effects",
    "/ui/bond-analytics/yield-curve-term-structure",
    "/api/bond-analytics/credit-spread-migration",
    "/api/bond-analytics/return-decomposition",
    "/api/pnl-attribution/campisi/four-effects",
    "/api/bond-analytics/yield-curve-term-structure",
    "/ui/home/income-trend",
  ];
  const fullDashboardHomeStyleNeedles = [
    "/assets/dashboardHome-",
  ];
  const firstScreenHomeStyleNeedles = [
    "/assets/dashboardHomeFirstScreenView-",
    "/assets/dashboardHomeShell-",
    "/assets/useMockHomeFirstScreenView-",
  ];
  const fullClientNeedles = [
    "/assets/client-",
  ];
  const marketDataClientNeedles = [
    "/assets/marketDataClient-",
  ];
  const marketTickerMockNeedles = [
    "/assets/homeMarketTickerMockClient-",
    "/assets/mockApiEnvelope-",
  ];
  const firstScreenMockNeedles = [
    "/assets/dashboardHomeFirstScreenMockView-",
  ];
  const echartsNeedles = [
    "/assets/echarts-",
    "/assets/echarts-for-react-",
    "/assets/echarts-misc-",
    "/assets/zrender-",
  ];
  const workbenchShellMarketTickerNeedles = [
    "/assets/WorkbenchShellMarketTicker-",
    "/assets/workbenchShellTicker-",
  ];
  const antdVendorNeedles = ["/assets/antd-vendor-"];

  const ready = {
    page: await page.locator('[data-testid="dashboard-home-page"]').count(),
    hero: await page.locator('[data-testid="dashboard-home-hero"]').count(),
    workGrid: await page.locator('[data-testid="dashboard-home-work-grid"]').count(),
  };
  const initialCounts = {
    snapshot: count(initialUrls, "/ui/home/snapshot"),
    homeSummary: countAny(initialUrls, [
      "/ui/bond-dashboard/home-summary",
      "/api/bond-dashboard/home-summary",
    ]),
    marketRates: count(initialUrls, "/ui/market-data/rates"),
    calendar: count(initialUrls, "/ui/calendar/supply-auctions"),
    choiceNews: count(initialUrls, "/ui/news/choice-events/latest"),
    formal: countAny(initialUrls, formalNeedles),
    clientChunk: countAny(initialUrls, fullClientNeedles),
    marketDataClientChunk: countAny(initialUrls, marketDataClientNeedles),
    marketTickerMockChunk: countAny(initialUrls, marketTickerMockNeedles),
    firstScreenMockChunk: countAny(initialUrls, firstScreenMockNeedles),
    workbenchShellMarketTickerChunk: countAny(initialUrls, workbenchShellMarketTickerNeedles),
    antdVendorChunk: countAny(initialUrls, antdVendorNeedles),
    echarts: countAny(initialUrls, echartsNeedles),
    fullDashboardHomeStylesheet: countAny(initialUrls, fullDashboardHomeStyleNeedles),
    firstScreenHomeStylesheet: countAny(initialUrls, firstScreenHomeStyleNeedles),
  };
  const allCounts = {
    snapshot: count(allUrls, "/ui/home/snapshot"),
    homeSummary: countAny(allUrls, [
      "/ui/bond-dashboard/home-summary",
      "/api/bond-dashboard/home-summary",
    ]),
    marketRates: count(allUrls, "/ui/market-data/rates"),
    calendar: count(allUrls, "/ui/calendar/supply-auctions"),
    choiceNews: count(allUrls, "/ui/news/choice-events/latest"),
    incomeTrend: count(allUrls, "/ui/home/income-trend"),
    institutionalStylesheet: countAny(allUrls, ["/assets/workbenchInstitutionalConsole-"]),
    workbenchChromeStylesheet: countAny(allUrls, ["/assets/workbenchDeferredChrome-"]),
    marketTickerMockChunk: countAny(allUrls, marketTickerMockNeedles),
    firstScreenMockChunk: countAny(allUrls, firstScreenMockNeedles),
    workbenchShellMarketTickerChunk: countAny(allUrls, workbenchShellMarketTickerNeedles),
    antdVendorChunk: countAny(allUrls, antdVendorNeedles),
    fullDashboardHomeStylesheet: countAny(allUrls, fullDashboardHomeStyleNeedles),
    failedResponses: failOnUnexpectedResponses("home", responseLog),
  };

  if (ready.page !== 1 || ready.hero !== 1) {
    addFailure(`home first screen did not render: page=${ready.page}, hero=${ready.hero}`);
  }
  if (initialCounts.snapshot !== 1) {
    addFailure(`expected exactly one snapshot request in the first-screen window, got ${initialCounts.snapshot}`);
  }
  if (initialCounts.homeSummary !== 0) {
    addFailure(`home summary should stay out of the first-screen window, got ${initialCounts.homeSummary}`);
  }
  if (initialCounts.marketRates !== 0) {
    addFailure(`market rates should stay out of the first-screen window, got ${initialCounts.marketRates}`);
  }
  if (initialCounts.calendar !== 0 || initialCounts.choiceNews !== 0) {
    addFailure(
      `news/calendar should stay out of the first-screen window, got calendar=${initialCounts.calendar}, choiceNews=${initialCounts.choiceNews}`,
    );
  }
  if (initialCounts.formal !== 0) {
    addFailure(`formal supplemental APIs should stay out of the first-screen window, got ${initialCounts.formal}`);
  }
  if (initialCounts.clientChunk !== 0 || initialCounts.marketDataClientChunk !== 0) {
    addFailure(
      `full client/market data client should stay out of the first-screen window, got client=${initialCounts.clientChunk}, marketDataClient=${initialCounts.marketDataClientChunk}`,
    );
  }
  if (initialCounts.workbenchShellMarketTickerChunk !== 0) {
    addFailure(
      `workbench shell market ticker should stay out of the first-screen window, got ${initialCounts.workbenchShellMarketTickerChunk}`,
    );
  }
  if (initialCounts.marketTickerMockChunk !== 0) {
    addFailure(
      `market ticker mock chunk should stay out of the first-screen window, got ${initialCounts.marketTickerMockChunk}`,
    );
  }
  if (initialCounts.firstScreenMockChunk !== 0) {
    addFailure(
      `first-screen mock view chunk should stay out of the first-screen window, got ${initialCounts.firstScreenMockChunk}`,
    );
  }
  if (initialCounts.echarts !== 0) {
    addFailure(`ECharts should stay out of the first-screen window, got ${initialCounts.echarts}`);
  }
  if (initialCounts.antdVendorChunk !== 0) {
    addFailure(
      `Ant Design should stay out of the first-screen window, got ${initialCounts.antdVendorChunk}`,
    );
  }
  if (initialCounts.fullDashboardHomeStylesheet !== 0) {
    addFailure(
      `full dashboard home stylesheet should stay out of the first-screen window, got ${initialCounts.fullDashboardHomeStylesheet}`,
    );
  }
  if (initialCounts.firstScreenHomeStylesheet < 1) {
    addFailure("lightweight dashboard home shell stylesheet was not requested for the first screen.");
  }
  if (allCounts.snapshot !== 1) {
    addFailure(`snapshot should be requested once overall, got ${allCounts.snapshot}`);
  }
  if (allCounts.marketRates !== 1) {
    addFailure(`market rates should be requested once overall, got ${allCounts.marketRates}`);
  }
  if (allCounts.homeSummary < 1) {
    addFailure(`home summary should load after the first-screen window, got ${allCounts.homeSummary}`);
  }
  if (allCounts.calendar < 1 || allCounts.choiceNews < 1) {
    addFailure(
      `news/calendar should load after the first-screen window, got calendar=${allCounts.calendar}, choiceNews=${allCounts.choiceNews}`,
    );
  }
  if (allCounts.incomeTrend < 1) {
    addFailure(`income trend should load after the first-screen window, got ${allCounts.incomeTrend}`);
  }
  if (allCounts.institutionalStylesheet !== 0) {
    addFailure(
      `home should not load the institutional console stylesheet, got ${allCounts.institutionalStylesheet}`,
    );
  }
  if (allCounts.workbenchChromeStylesheet !== 0) {
    addFailure(
      `home should not load the non-home workbench chrome stylesheet, got ${allCounts.workbenchChromeStylesheet}`,
    );
  }
  if (allCounts.workbenchShellMarketTickerChunk !== 0) {
    addFailure(
      `home should not load the workbench shell market ticker chunk, got ${allCounts.workbenchShellMarketTickerChunk}`,
    );
  }
  if (allCounts.marketTickerMockChunk !== 0) {
    addFailure(
      `home should not load the market ticker mock chunk, got ${allCounts.marketTickerMockChunk}`,
    );
  }
  if (allCounts.firstScreenMockChunk !== 0) {
    addFailure(
      `home should not load the first-screen mock view chunk, got ${allCounts.firstScreenMockChunk}`,
    );
  }
  if (allCounts.antdVendorChunk !== 0) {
    addFailure(
      `home should not load the Ant Design vendor chunk, got ${allCounts.antdVendorChunk}`,
    );
  }

  return {
    route: "/",
    ready,
    initialCounts,
    allCounts,
    firstWorkbenchCssAt: null,
    firstTwentyRequests: requestLog.slice(0, 20).map(normalizeRequest),
    uiRequests: requestLog
      .filter((entry) => entry.url.includes("/ui/") || entry.url.includes("/api/"))
      .map((entry) => ({
        t: entry.t,
        url: entry.url.replace(/^https?:\/\/[^/]+/, ""),
      })),
    browserMessages,
  };
}

async function sampleNonHomeShell(page, baseUrl) {
  const { requestLog, responseLog, browserMessages } = createRuntimeLog(page);
  const url = new URL("/cross-asset", baseUrl).toString();

  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30_000 });
  await page.waitForSelector('[data-testid="cross-asset-drivers-page"]', { timeout: 30_000 });
  await page.waitForTimeout(FIRST_SCREEN_OBSERVATION_MS);

  const initialUrls = requestLog.map((entry) => entry.url);
  const ready = {
    page: await page.locator('[data-testid="cross-asset-drivers-page"]').count(),
    shellRoot: await page.locator(".workbench-shell-grid--institutional-console").count(),
  };
  await page.waitForTimeout(NON_HOME_SETTLE_MS);
  const allUrls = requestLog.map((entry) => entry.url);
  const workbenchStyleNeedles = [
    "/assets/workbenchInstitutionalConsole-",
    "/assets/workbenchDeferredChrome-",
  ];
  const firstWorkbenchCssAt = firstRequestAt(requestLog, workbenchStyleNeedles);
  const initialCounts = {
    institutionalStylesheet: countAny(initialUrls, ["/assets/workbenchInstitutionalConsole-"]),
    workbenchChromeStylesheet: countAny(initialUrls, ["/assets/workbenchDeferredChrome-"]),
    antdVendorChunk: countAny(initialUrls, ["/assets/antd-vendor-"]),
  };
  const failedResponses = failOnUnexpectedResponses("cross-asset", responseLog);
  const allCounts = {
    institutionalStylesheet: countAny(allUrls, ["/assets/workbenchInstitutionalConsole-"]),
    workbenchChromeStylesheet: countAny(allUrls, ["/assets/workbenchDeferredChrome-"]),
    workbenchShellMarketTickerChunk: countAny(allUrls, [
      "/assets/WorkbenchShellMarketTicker-",
      "/assets/workbenchShellTicker-",
    ]),
    antdVendorChunk: countAny(allUrls, ["/assets/antd-vendor-"]),
    failedResponses,
  };

  if (ready.page !== 1 || ready.shellRoot !== 1) {
    addFailure(`cross-asset shell did not render with institutional scope: page=${ready.page}, shellRoot=${ready.shellRoot}`);
  }
  if (initialCounts.institutionalStylesheet < 1) {
    addFailure(
      `cross-asset institutional console stylesheet did not load in the first-screen window, got ${initialCounts.institutionalStylesheet}.`,
    );
  }
  if (initialCounts.workbenchChromeStylesheet < 1) {
    addFailure(
      `cross-asset workbench chrome stylesheet did not load in the first-screen window, got ${initialCounts.workbenchChromeStylesheet}.`,
    );
  }
  if (initialCounts.antdVendorChunk < 1) {
    addFailure(
      `cross-asset Ant Design vendor chunk should load in the first-screen window, got ${initialCounts.antdVendorChunk}.`,
    );
  }
  if (allCounts.workbenchShellMarketTickerChunk < 1) {
    addFailure("cross-asset workbench shell market ticker chunk did not load.");
  }

  const crossAssetSummary = {
    route: "/cross-asset",
    ready,
    initialCounts,
    allCounts,
    firstWorkbenchCssAt,
    firstTwentyRequests: requestLog.slice(0, 20).map(normalizeRequest),
    browserMessages,
  };

  await page.locator('[data-testid="workbench-group-nav"] a[href="/"]').click();
  await page.waitForSelector('[data-testid="dashboard-home-page"]', { timeout: 30_000 });
  await page.waitForSelector('[data-testid="dashboard-home-hero"]', { timeout: 30_000 });
  await page.waitForTimeout(FIRST_SCREEN_OBSERVATION_MS);

  const homeReturnReady = {
    page: await page.locator('[data-testid="dashboard-home-page"]').count(),
    hero: await page.locator('[data-testid="dashboard-home-hero"]').count(),
    cockpitShellRoot: await page.locator(".workbench-shell-grid--cockpit").count(),
    institutionalShellRoot: await page.locator(".workbench-shell-grid--institutional-console").count(),
  };
  const returnedPath = new URL(page.url()).pathname;

  if (returnedPath !== "/") {
    addFailure(`home return from cross-asset landed on ${returnedPath}, expected /`);
  }
  if (homeReturnReady.page !== 1 || homeReturnReady.hero !== 1) {
    addFailure(
      `home return from cross-asset did not render the first screen: page=${homeReturnReady.page}, hero=${homeReturnReady.hero}`,
    );
  }
  if (homeReturnReady.cockpitShellRoot !== 1) {
    addFailure(
      `home return from cross-asset should use the cockpit shell scope, got ${homeReturnReady.cockpitShellRoot}`,
    );
  }
  if (homeReturnReady.institutionalShellRoot !== 0) {
    addFailure(
      `home return should leave the institutional console scope after deferred CSS has loaded, got ${homeReturnReady.institutionalShellRoot}`,
    );
  }

  return {
    ...crossAssetSummary,
    homeReturn: {
      route: "/",
      path: returnedPath,
      ready: homeReturnReady,
    },
  };
}

const server = await createProductionStaticServer();
const baseUrl = server.baseUrl;
const browser = await chromium.launch({ headless: true });

try {
  assertFreshProductionBundle();

  const { context: homeContext, page: homePage } = await createIsolatedPage(browser);
  const homeSummary = await sampleHome(homePage, baseUrl);
  await homeContext.close();

  const { context: nonHomeContext, page: nonHomePage } = await createIsolatedPage(browser);
  const nonHomeSummary = await sampleNonHomeShell(nonHomePage, baseUrl);
  await nonHomeContext.close();

  const summary = {
    baseUrl,
    mode: "production-preview",
    thresholds: {
      firstScreenObservationMs: FIRST_SCREEN_OBSERVATION_MS,
      homePostFirstScreenMaxWaitMs: HOME_POST_FIRST_SCREEN_MAX_WAIT_MS,
    },
    samples: [homeSummary, nonHomeSummary],
    failures,
  };

  if (failures.length > 0) {
    console.error("[home-startup-runtime] Runtime guard failed.");
    console.error(JSON.stringify(summary, null, 2));
    process.exitCode = 1;
  } else {
    console.log("[home-startup-runtime] Runtime guard passed.");
    console.log(JSON.stringify(summary, null, 2));
  }
} finally {
  await browser.close();
  await server.close();
}
