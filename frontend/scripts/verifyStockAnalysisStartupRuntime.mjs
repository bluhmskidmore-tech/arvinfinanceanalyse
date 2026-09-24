import { createServer } from "node:http";
import { existsSync, readdirSync, statSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { extname, join, normalize, relative, resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { chromium } from "playwright";

const RUNS = Number.parseInt(process.env.STOCK_PERF_RUNS ?? "5", 10);
const INCLUDE_DETAILS = process.env.STOCK_PERF_DETAILS !== "0";
const CAPTURE_CSS_COVERAGE = process.env.STOCK_PERF_CSS_COVERAGE === "1";
const CAPTURE_JS_COVERAGE = process.env.STOCK_PERF_JS_COVERAGE === "1";
const ENFORCE_BUDGETS = process.env.STOCK_PERF_ENFORCE === "1";
const API_TARGET =
  process.env.MOSS_STOCK_ANALYSIS_API_TARGET ??
  process.env.MOSS_VITE_API_PROXY ??
  "http://127.0.0.1:7888";
const OBSERVATION_MS = 400;
const frontendRoot = process.cwd();
const distRoot = resolve(frontendRoot, "dist");
const distIndexPath = resolve(distRoot, "index.html");
const workbenchNeedle = "/ui/market-data/stock-analysis/workbench";
const deferredNeedles = [
  "/ui/market-data/livermore/signal-confluence",
  "/ui/market-data/livermore/strategy-score",
  "/ui/market-data/livermore/strategy-optimization",
  "/ui/market-data/livermore/candidate-history",
  "/ui/market-data/livermore/cycle-proxy-backtest",
  "/ui/market-data/livermore/candidate-history-portfolio-backtest",
  "/ui/market-data/livermore/sector-rank-series",
];
const failures = [];

function addFailure(message) {
  failures.push(message);
}

function percentile(values, percentileValue) {
  if (values.length === 0) return null;
  const sorted = [...values].sort((left, right) => left - right);
  const index = Math.min(
    sorted.length - 1,
    Math.max(0, Math.ceil((percentileValue / 100) * sorted.length) - 1),
  );
  return Math.round(sorted[index] * 100) / 100;
}

function summarize(samples, field) {
  const values = samples
    .map((sample) => sample[field])
    .filter((value) => typeof value === "number" && Number.isFinite(value));
  return {
    min: percentile(values, 0),
    median: percentile(values, 50),
    p95: percentile(values, 95),
    max: percentile(values, 100),
  };
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

function distFilePath(pathname) {
  const decoded = decodeURIComponent(pathname);
  const safePath = normalize(decoded).replace(/^(\.\.[/\\])+/, "");
  const relativePath =
    safePath === "/" || safePath === "."
      ? "index.html"
      : safePath.replace(/^[/\\]/, "");
  const filePath = join(distRoot, relativePath);
  const relativeToDist = relative(distRoot, filePath);
  if (relativeToDist.startsWith("..") || /^[A-Za-z]:/.test(relativeToDist)) {
    return distIndexPath;
  }
  return filePath;
}

async function proxyApiRequest(request, response, requestUrl) {
  const targetUrl = new URL(`${requestUrl.pathname}${requestUrl.search}`, API_TARGET);
  const headers = new Headers(request.headers);
  headers.set("host", targetUrl.host);
  const init = { method: request.method, headers, redirect: "manual" };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request;
    init.duplex = "half";
  }
  const upstream = await fetch(targetUrl, init);
  const responseHeaders = Object.fromEntries(upstream.headers.entries());
  delete responseHeaders["content-encoding"];
  delete responseHeaders["content-length"];
  delete responseHeaders["transfer-encoding"];
  const body = upstream.body ? Buffer.from(await upstream.arrayBuffer()) : Buffer.alloc(0);
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
  let filePath = distFilePath(requestUrl.pathname);
  if (!existsSync(filePath) || statSync(filePath).isDirectory()) {
    filePath = distIndexPath;
  }
  const body = await readFile(filePath);
  response.writeHead(200, {
    "content-type": contentTypeForPath(filePath),
    "cache-control": "no-store",
  });
  response.end(body);
}

async function createProductionServer() {
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
    throw new Error("Stock performance server did not expose a TCP port.");
  }
  return {
    baseUrl: `http://127.0.0.1:${address.port}`,
    close: () =>
      new Promise((resolveClose, rejectClose) => {
        server.close((error) => (error ? rejectClose(error) : resolveClose(undefined)));
      }),
  };
}

function installPerformanceObservers(page) {
  return page.addInitScript(() => {
    window.__stockPerformance = { cls: 0, lcp: 0, longTasks: [] };
    try {
      new PerformanceObserver((list) => {
        const entries = list.getEntries();
        const last = entries.at(-1);
        if (last) window.__stockPerformance.lcp = last.startTime;
      }).observe({ type: "largest-contentful-paint", buffered: true });
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (!entry.hadRecentInput) window.__stockPerformance.cls += entry.value;
        }
      }).observe({ type: "layout-shift", buffered: true });
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          window.__stockPerformance.longTasks.push({
            startTime: entry.startTime,
            duration: entry.duration,
          });
        }
      }).observe({ type: "longtask", buffered: true });
    } catch {
      // Unsupported performance entry types remain visible as null/empty metrics.
    }
  });
}

function createTracker(page) {
  const startedAt = performance.now();
  const requests = [];
  const responses = [];
  const responseBodyTasks = [];
  const messages = [];
  page.on("request", (request) => {
    const url = request.url();
    if (url.includes("/ui/") || url.includes("/api/") || url.includes("/assets/")) {
      requests.push({
        atMs: Math.round((performance.now() - startedAt) * 100) / 100,
        type: request.resourceType(),
        url: url.replace(/^https?:\/\/[^/]+/, ""),
      });
    }
  });
  page.on("response", (response) => {
    const url = response.url();
    if (!(url.includes("/ui/") || url.includes("/api/") || url.includes("/assets/"))) {
      return;
    }
    const entry = {
      atMs: Math.round((performance.now() - startedAt) * 100) / 100,
      status: response.status(),
      url: url.replace(/^https?:\/\/[^/]+/, ""),
      bytes: null,
      serverTiming: response.headers()["server-timing"] ?? null,
    };
    responses.push(entry);
    const bodyTask = response
      .body()
      .then((body) => {
        entry.bytes = body.byteLength;
      })
      .catch(() => undefined);
    responseBodyTasks.push(bodyTask);
  });
  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") {
      messages.push({ type: message.type(), text: message.text() });
    }
  });
  page.on("pageerror", (error) => messages.push({ type: "pageerror", text: error.message }));
  return { startedAt, requests, responses, responseBodyTasks, messages };
}

async function readPageMetrics(page) {
  return page.evaluate(() => {
    const fcp = performance.getEntriesByName("first-contentful-paint")[0];
    const navigation = performance.getEntriesByType("navigation")[0];
    const state = window.__stockPerformance ?? { cls: 0, lcp: 0, longTasks: [] };
    const resources = performance.getEntriesByType("resource");
    return {
      fcpMs: fcp ? Math.round(fcp.startTime * 100) / 100 : null,
      lcpMs: state.lcp ? Math.round(state.lcp * 100) / 100 : null,
      cls: Math.round(state.cls * 10_000) / 10_000,
      domContentLoadedMs: navigation
        ? Math.round(navigation.domContentLoadedEventEnd * 100) / 100
        : null,
      loadMs: navigation ? Math.round(navigation.loadEventEnd * 100) / 100 : null,
      longTaskCount: state.longTasks.length,
      longestTaskMs:
        state.longTasks.length > 0
          ? Math.round(Math.max(...state.longTasks.map((entry) => entry.duration)) * 100) / 100
          : 0,
      transferBytes: Math.round(
        resources.reduce((total, entry) => total + (entry.transferSize || 0), 0),
      ),
      decodedBytes: Math.round(
        resources.reduce((total, entry) => total + (entry.decodedBodySize || 0), 0),
      ),
      horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
    };
  });
}

function countRequests(requests, needle) {
  return requests.filter((entry) => entry.url.includes(needle)).length;
}

async function finalizeSample(page, tracker, mode, readyMs) {
  await page.waitForTimeout(OBSERVATION_MS);
  await Promise.allSettled(tracker.responseBodyTasks);
  const pageMetrics = await readPageMetrics(page);
  const trackedRequestUrls = new Set(tracker.requests.map((entry) => entry.url));
  const apiResponses = tracker.responses.filter(
    (entry) =>
      trackedRequestUrls.has(entry.url) &&
      (entry.url.includes("/ui/") || entry.url.includes("/api/")),
  );
  const workbenchResponses = tracker.responses.filter(
    (entry) => trackedRequestUrls.has(entry.url) && entry.url.includes(workbenchNeedle),
  );
  return {
    mode,
    readyMs: Math.round(readyMs * 100) / 100,
    ...pageMetrics,
    workbenchRequests: countRequests(tracker.requests, workbenchNeedle),
    deferredRequests: deferredNeedles.reduce(
      (total, needle) => total + countRequests(tracker.requests, needle),
      0,
    ),
    deferredRequestUrls: tracker.requests
      .filter((entry) => deferredNeedles.some((needle) => entry.url.includes(needle)))
      .map((entry) => entry.url),
    apiRequests: tracker.requests.filter(
      (entry) => entry.url.includes("/ui/") || entry.url.includes("/api/"),
    ),
    apiRequestCount: tracker.requests.filter(
      (entry) => entry.url.includes("/ui/") || entry.url.includes("/api/"),
    ).length,
    apiBytes: apiResponses.reduce((total, entry) => total + (entry.bytes ?? 0), 0),
    workbenchBytes: workbenchResponses.reduce((total, entry) => total + (entry.bytes ?? 0), 0),
    workbenchServerTiming: workbenchResponses[0]?.serverTiming ?? null,
    failedResponses: tracker.responses.filter((entry) => trackedRequestUrls.has(entry.url) && entry.status >= 400),
    messages: tracker.messages,
    firstRequests: tracker.requests.slice(0, 20),
  };
}

async function sampleCold(browser, baseUrl, mode, mobile = false) {
  const context = await browser.newContext({
    viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 900 },
    deviceScaleFactor: mobile ? 2 : 1,
    isMobile: mobile,
    hasTouch: mobile,
  });
  const page = await context.newPage();
  if (CAPTURE_CSS_COVERAGE && mode === "desktop-cold") {
    await page.coverage.startCSSCoverage({ resetOnNavigation: false });
  }
  if (CAPTURE_JS_COVERAGE && mode === "desktop-cold") {
    await page.coverage.startJSCoverage({ resetOnNavigation: false });
  }
  await installPerformanceObservers(page);
  await page.bringToFront();
  if (mobile) {
    const session = await context.newCDPSession(page);
    await session.send("Network.enable");
    await session.send("Network.emulateNetworkConditions", {
      offline: false,
      latency: 150,
      downloadThroughput: (1.6 * 1024 * 1024) / 8,
      uploadThroughput: (750 * 1024) / 8,
      connectionType: "cellular3g",
    });
    await session.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  }
  const tracker = createTracker(page);
  const startedAt = performance.now();
  await page.goto(`${baseUrl}/stock-analysis`, {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  await page.waitForSelector('[data-testid="stock-analysis-workbench-contract"]', {
    timeout: 60_000,
  });
  await page.waitForSelector('[data-testid="stock-analysis-review-queue"]', {
    timeout: 60_000,
  });
  const sample = await finalizeSample(page, tracker, mode, performance.now() - startedAt);
  if (CAPTURE_CSS_COVERAGE && mode === "desktop-cold") {
    const coverage = await page.coverage.stopCSSCoverage();
    sample.cssCoverage = coverage.map((entry) => {
      const usedBytes = entry.ranges.reduce(
        (total, range) => total + Math.max(0, range.end - range.start),
        0,
      );
      return {
        url: entry.url.replace(/^https?:\/\/[^/]+/, ""),
        totalBytes: entry.text.length,
        usedBytes,
        unusedBytes: Math.max(0, entry.text.length - usedBytes),
        usedPercent:
          entry.text.length > 0
            ? Math.round((usedBytes / entry.text.length) * 10_000) / 100
            : 0,
      };
    });
  }
  if (CAPTURE_JS_COVERAGE && mode === "desktop-cold") {
    const coverage = await page.coverage.stopJSCoverage();
    sample.jsCoverage = coverage
      .filter((entry) => entry.url.includes("/assets/"))
      .map((entry) => {
        const unusedRanges = entry.functions
          .flatMap((fn) => fn.ranges)
          .filter((range) => range.count === 0)
          .sort((left, right) => left.startOffset - right.startOffset);
        let unusedBytes = 0;
        let uncoveredUntil = 0;
        for (const range of unusedRanges) {
          const start = Math.max(uncoveredUntil, range.startOffset);
          const end = Math.max(start, range.endOffset);
          unusedBytes += end - start;
          uncoveredUntil = Math.max(uncoveredUntil, end);
        }
        const totalBytes = entry.source.length;
        const usedBytes = Math.max(0, totalBytes - unusedBytes);
        return {
          url: entry.url.replace(/^https?:\/\/[^/]+/, ""),
          totalBytes,
          usedBytes,
          unusedBytes,
          usedPercent:
            totalBytes > 0 ? Math.round((usedBytes / totalBytes) * 10_000) / 100 : 0,
        };
      })
      .sort((left, right) => right.unusedBytes - left.unusedBytes);
  }
  await context.close();
  return sample;
}

async function sampleWarmRevisit(browser, baseUrl) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await installPerformanceObservers(page);
  await page.bringToFront();
  await page.goto(`${baseUrl}/stock-analysis`, {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  await page.waitForSelector('[data-testid="stock-analysis-workbench-contract"]', {
    timeout: 60_000,
  });
  await page.evaluate(() => {
    history.pushState({}, "", "/");
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  await page.waitForSelector('[data-testid="stock-analysis-workbench-contract"]', {
    state: "detached",
    timeout: 30_000,
  });
  await page.evaluate(() => {
    performance.clearResourceTimings();
    window.__stockPerformance = { cls: 0, lcp: 0, longTasks: [] };
  });
  const tracker = createTracker(page);
  const startedAt = performance.now();
  await page.evaluate(() => {
    history.pushState({}, "", "/stock-analysis");
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  await page.waitForSelector('[data-testid="stock-analysis-workbench-contract"]', {
    timeout: 30_000,
  });
  await page.waitForSelector('[data-testid="stock-analysis-review-queue"]', {
    timeout: 30_000,
  });
  const sample = await finalizeSample(
    page,
    tracker,
    "warm-revisit",
    performance.now() - startedAt,
  );
  await context.close();
  return sample;
}

function bundleSnapshot() {
  const assetsRoot = resolve(distRoot, "assets");
  return readdirSync(assetsRoot)
    .filter((name) =>
      /^(StockAnalysisPage|stockAnalysisPageModel|StockDetailDrawer)-/.test(name),
    )
    .map((name) => ({ name, rawBytes: statSync(resolve(assetsRoot, name)).size }))
    .sort((left, right) => right.rawBytes - left.rawBytes);
}

function validateSamples(samples) {
  for (const sample of samples) {
    if (sample.mode !== "warm-revisit" && sample.workbenchRequests !== 1) {
      addFailure(`${sample.mode} expected one workbench request, got ${sample.workbenchRequests}`);
    }
    if (sample.mode === "warm-revisit" && sample.workbenchRequests > 1) {
      addFailure(`warm revisit requested workbench ${sample.workbenchRequests} times`);
    }
    if (sample.deferredRequests !== 0) {
      addFailure(`${sample.mode} started ${sample.deferredRequests} deferred requests before first-screen settle`);
    }
    if (sample.failedResponses.length > 0) {
      addFailure(`${sample.mode} saw ${sample.failedResponses.length} failed responses`);
    }
    if (sample.messages.length > 0) {
      addFailure(`${sample.mode} saw ${sample.messages.length} console/page messages`);
    }
    if (sample.horizontalOverflow) {
      addFailure(`${sample.mode} has horizontal overflow`);
    }
  }
  if (!ENFORCE_BUDGETS) return;
  const desktop = samples.filter((sample) => sample.mode === "desktop-cold");
  const mobile = samples.filter((sample) => sample.mode === "mobile-cold");
  const warm = samples.filter((sample) => sample.mode === "warm-revisit");
  if ((summarize(desktop, "lcpMs").median ?? Number.POSITIVE_INFINITY) > 2_500) {
    addFailure("desktop cold median LCP exceeds 2500ms");
  }
  if ((summarize(mobile, "cls").p95 ?? Number.POSITIVE_INFINITY) > 0.1) {
    addFailure("mobile cold P95 CLS exceeds 0.1");
  }
  if ((summarize(warm, "readyMs").p95 ?? Number.POSITIVE_INFINITY) > 1_500) {
    addFailure("warm revisit P95 ready exceeds 1500ms");
  }
}

if (!Number.isFinite(RUNS) || RUNS < 1) {
  throw new Error(`STOCK_PERF_RUNS must be a positive integer, got ${RUNS}`);
}
if (!existsSync(distIndexPath)) {
  throw new Error("Production dist is missing. Run `npx vite build` first.");
}

const server = await createProductionServer();
const browser = await chromium.launch({ headless: true });
const samples = [];
try {
  for (let index = 0; index < RUNS; index += 1) {
    samples.push(await sampleCold(browser, server.baseUrl, "desktop-cold", false));
  }
  for (let index = 0; index < RUNS; index += 1) {
    samples.push(await sampleWarmRevisit(browser, server.baseUrl));
  }
  for (let index = 0; index < RUNS; index += 1) {
    samples.push(await sampleCold(browser, server.baseUrl, "mobile-cold", true));
  }
} finally {
  await browser.close();
  await server.close();
}

validateSamples(samples);
const modes = ["desktop-cold", "warm-revisit", "mobile-cold"];
const summary = Object.fromEntries(
  modes.map((mode) => {
    const modeSamples = samples.filter((sample) => sample.mode === mode);
    return [
      mode,
      {
        readyMs: summarize(modeSamples, "readyMs"),
        fcpMs: summarize(modeSamples, "fcpMs"),
        lcpMs: summarize(modeSamples, "lcpMs"),
        cls: summarize(modeSamples, "cls"),
        longestTaskMs: summarize(modeSamples, "longestTaskMs"),
        transferBytes: summarize(modeSamples, "transferBytes"),
        decodedBytes: summarize(modeSamples, "decodedBytes"),
        apiBytes: summarize(modeSamples, "apiBytes"),
        workbenchBytes: summarize(modeSamples, "workbenchBytes"),
        workbenchRequests: modeSamples.map((sample) => sample.workbenchRequests),
        deferredRequests: modeSamples.map((sample) => sample.deferredRequests),
        serverTiming: modeSamples.map((sample) => sample.workbenchServerTiming),
      },
    ];
  }),
);

let commit = "unknown";
try {
  commit = execFileSync("git", ["rev-parse", "HEAD"], {
    cwd: resolve(frontendRoot, ".."),
    encoding: "utf8",
  }).trim();
} catch {
  // The fixed environment remains useful when git metadata is unavailable.
}

const report = {
  capturedAt: new Date().toISOString(),
  commit,
  platform: `${process.platform}-${process.arch}`,
  node: process.version,
  browser: await chromium.launch({ headless: true }).then(async (instance) => {
    const version = instance.version();
    await instance.close();
    return version;
  }),
  apiTarget: API_TARGET,
  route: "/stock-analysis",
  parameters: {
    asOfDate: "default",
    include: "main,evidence_summary",
    sectorWindowDays: 20,
    topK: 10,
    runsPerMode: RUNS,
    observationMs: OBSERVATION_MS,
    mobile: "390x844, 4x CPU, 150ms RTT, 1.6Mbps down, 750Kbps up",
  },
  bundle: bundleSnapshot(),
  summary,
  samples: INCLUDE_DETAILS ? samples : undefined,
  failures,
};

console.log(JSON.stringify(report, null, 2));
if (failures.length > 0) process.exitCode = 1;
