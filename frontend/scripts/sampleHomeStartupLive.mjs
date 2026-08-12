import { chromium } from "playwright";

const baseUrl = process.env.MOSS_HOME_STARTUP_BASE_URL ?? "http://localhost:5888/";
const apiReadyUrl = process.env.MOSS_HOME_STARTUP_READY_URL ?? "http://127.0.0.1:7888/health/ready";
const firstScreenObservationMs = 400;
const postFirstScreenMaxWaitMs = 18_000;
const requestPollIntervalMs = 250;
// Request budgets: the home page issues 18 /ui+/api requests after the news
// batching work (baseline 2026-08-12). News collapses to a macro batch, a bond
// batch, and a data-dependent macro fallback batch.
const MAX_UI_REQUESTS = 18;
const MIN_CHOICE_NEWS_BATCH_REQUESTS = 2;
const MAX_CHOICE_NEWS_BATCH_REQUESTS = 3;

const failures = [];

function addFailure(message) {
  failures.push(message);
}

function count(urls, needle) {
  return urls.filter((url) => url.includes(needle)).length;
}

function countAny(urls, needles) {
  return urls.filter((url) => needles.some((needle) => url.includes(needle))).length;
}

function normalizeUrl(url) {
  return url.replace(/^https?:\/\/[^/]+/, "");
}

function trackUrl(url) {
  return url.includes("/ui/") || url.includes("/api/") || url.includes("/assets/") || url.includes("/src/");
}

function firstRequestAt(requestLog, needles) {
  const match = requestLog.find((entry) => needles.some((needle) => entry.url.includes(needle)));
  return match?.t ?? null;
}

async function waitForTrackedRequests(page, requestLog, needleGroups, timeoutMs) {
  const startedAt = Date.now();
  const allRequestsStarted = () =>
    needleGroups.every((needles) => firstRequestAt(requestLog, needles) != null);

  while (Date.now() - startedAt < timeoutMs) {
    if (allRequestsStarted()) {
      return true;
    }
    await page.waitForTimeout(requestPollIntervalMs);
  }
  return allRequestsStarted();
}

function createRuntimeLog(page) {
  const startedAt = Date.now();
  const requestLog = [];
  const responseLog = [];

  page.on("request", (request) => {
    const url = request.url();
    if (!trackUrl(url)) {
      return;
    }
    requestLog.push({
      t: Date.now() - startedAt,
      method: request.method(),
      type: request.resourceType(),
      url,
    });
  });

  page.on("response", (response) => {
    const url = response.url();
    if (!trackUrl(url)) {
      return;
    }
    responseLog.push({
      t: Date.now() - startedAt,
      status: response.status(),
      url,
    });
  });

  return { requestLog, responseLog };
}

async function fetchReadyStatus() {
  const response = await fetch(apiReadyUrl);
  const payload = await response.json();
  const homePrewarm = payload?.checks?.home_snapshot_prewarm ?? null;
  if (!homePrewarm) {
    addFailure("API readiness is missing checks.home_snapshot_prewarm; restart the API before live startup sampling.");
  } else if (homePrewarm.status !== "ready") {
    addFailure(
      `home snapshot prewarm is not ready before live sample: status=${homePrewarm.status} error=${homePrewarm.error ?? ""}`,
    );
  }
  return {
    statusCode: response.status,
    status: payload?.status,
    homePrewarm,
  };
}

async function sampleHome() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.route("**/*", (route) => route.continue());
  const page = await context.newPage();
  const { requestLog, responseLog } = createRuntimeLog(page);

  try {
    await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 30_000 });
    await page.waitForSelector('[data-testid="dashboard-home-page"]', { timeout: 30_000 });
    await page.waitForSelector('[data-testid="dashboard-home-hero"]', { timeout: 30_000 });
    await page.waitForTimeout(firstScreenObservationMs);

    const initialUrls = requestLog.map((entry) => entry.url);
    const marketTickerMockNeedles = [
      "/src/api/homeMarketTickerMockClient.ts",
      "/src/mocks/mockApiEnvelope.ts",
      "/assets/homeMarketTickerMockClient-",
      "/assets/mockApiEnvelope-",
    ];
    const firstScreenMockNeedles = [
      "/src/features/workbench/dashboard-home/dashboardHomeFirstScreenMockView.ts",
      "/assets/dashboardHomeFirstScreenMockView-",
    ];
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    const trackedRequestsArrived = await waitForTrackedRequests(
      page,
      requestLog,
      [
        ["/ui/market-data/rates"],
        ["/ui/calendar/supply-auctions"],
        ["/ui/news/choice-events/latest"],
        // The bond-news batch sits one idle tier later than the macro batch;
        // without waiting for it the batch-count assertion below races.
        ["/ui/news/choice-events/latest-batch?groups"],
        ["/ui/home/income-trend"],
        ["/ui/bond-dashboard/home-summary", "/api/bond-dashboard/home-summary"],
      ],
      postFirstScreenMaxWaitMs,
    );
    if (!trackedRequestsArrived) {
      addFailure(
        `tracked home data requests did not all arrive within ${postFirstScreenMaxWaitMs}ms.`,
      );
    }

    const allUrls = requestLog.map((entry) => entry.url);
    const ready = {
      page: await page.locator('[data-testid="dashboard-home-page"]').count(),
      hero: await page.locator('[data-testid="dashboard-home-hero"]').count(),
      workGrid: await page.locator('[data-testid="dashboard-home-work-grid"]').count(),
    };
    const initialCounts = {
      snapshot: count(initialUrls, "/ui/home/snapshot"),
      clientSource: count(initialUrls, "/src/api/client.ts"),
      clientChunk: countAny(initialUrls, ["/assets/client-"]),
      marketTickerMock: countAny(initialUrls, marketTickerMockNeedles),
      firstScreenMock: countAny(initialUrls, firstScreenMockNeedles),
      marketRates: count(initialUrls, "/ui/market-data/rates"),
      calendar: count(initialUrls, "/ui/calendar/supply-auctions"),
      choiceNews: count(initialUrls, "/ui/news/choice-events/latest"),
      echarts: countAny(initialUrls, [
        "/assets/echarts-",
        "/assets/echarts-for-react-",
        "/assets/echarts-misc-",
        "/assets/zrender-",
        "/node_modules/.vite/deps/echarts",
        "/node_modules/.vite/deps/zrender",
      ]),
    };
    // Path-anchored: dev-mode module URLs like /src/api/homeExecutiveClient.ts
    // contain "/api/" but are not backend requests.
    const uiRequestUrls = allUrls.filter((requestUrl) => {
      const path = normalizeUrl(requestUrl);
      return path.startsWith("/ui/") || path.startsWith("/api/");
    });
    const allCounts = {
      snapshot: count(allUrls, "/ui/home/snapshot"),
      marketRates: count(allUrls, "/ui/market-data/rates"),
      calendar: count(allUrls, "/ui/calendar/supply-auctions"),
      choiceNews: count(allUrls, "/ui/news/choice-events/latest"),
      choiceNewsBatch: count(allUrls, "/ui/news/choice-events/latest-batch"),
      incomeTrend: count(allUrls, "/ui/home/income-trend"),
      homeSummary: countAny(allUrls, [
        "/ui/bond-dashboard/home-summary",
        "/api/bond-dashboard/home-summary",
      ]),
      uiRequestTotal: uiRequestUrls.length,
      marketTickerMock: countAny(allUrls, marketTickerMockNeedles),
      firstScreenMock: countAny(allUrls, firstScreenMockNeedles),
      failedResponses: responseLog.filter((entry) => entry.status >= 400).length,
    };

    if (ready.page !== 1 || ready.hero !== 1) {
      addFailure(`home first screen did not render: page=${ready.page}, hero=${ready.hero}`);
    }
    if (initialCounts.snapshot !== 1) {
      addFailure(`expected one snapshot request in first-screen window, got ${initialCounts.snapshot}`);
    }
    if (initialCounts.clientSource !== 0 || initialCounts.clientChunk !== 0) {
      addFailure(
        `full API client should stay out of first-screen window, got source=${initialCounts.clientSource}, chunk=${initialCounts.clientChunk}`,
      );
    }
    if (initialCounts.marketTickerMock !== 0) {
      addFailure(`market ticker mock should stay out of live real-data home first screen, got ${initialCounts.marketTickerMock}`);
    }
    if (initialCounts.firstScreenMock !== 0) {
      addFailure(`first-screen mock view should stay out of live real-data home first screen, got ${initialCounts.firstScreenMock}`);
    }
    if (initialCounts.marketRates !== 0 || initialCounts.calendar !== 0 || initialCounts.choiceNews !== 0) {
      addFailure(
        `supplemental APIs should stay out of first-screen window, got rates=${initialCounts.marketRates}, calendar=${initialCounts.calendar}, news=${initialCounts.choiceNews}`,
      );
    }
    if (initialCounts.echarts !== 0) {
      addFailure(`ECharts/zrender should stay out of first-screen window, got ${initialCounts.echarts}`);
    }
    if (allCounts.snapshot !== 1) {
      addFailure(`snapshot should be requested once overall, got ${allCounts.snapshot}`);
    }
    if (allCounts.marketRates !== 1) {
      addFailure(`market rates should be requested once overall, got ${allCounts.marketRates}`);
    }
    if (allCounts.marketTickerMock !== 0) {
      addFailure(`market ticker mock should stay out of live real-data home overall, got ${allCounts.marketTickerMock}`);
    }
    if (allCounts.firstScreenMock !== 0) {
      addFailure(`first-screen mock view should stay out of live real-data home overall, got ${allCounts.firstScreenMock}`);
    }
    if (allCounts.failedResponses !== 0) {
      addFailure(`live sample saw ${allCounts.failedResponses} failed tracked responses.`);
    }
    // News must stay collapsed to batch calls (macro + bond, plus a conditional
    // macro fallback); a regression back to the old 13 per-topic single queries
    // would pass every needle above unnoticed.
    if (
      allCounts.choiceNewsBatch < MIN_CHOICE_NEWS_BATCH_REQUESTS ||
      allCounts.choiceNewsBatch > MAX_CHOICE_NEWS_BATCH_REQUESTS
    ) {
      addFailure(
        `expected ${MIN_CHOICE_NEWS_BATCH_REQUESTS}-${MAX_CHOICE_NEWS_BATCH_REQUESTS} news latest-batch requests, got ${allCounts.choiceNewsBatch}`,
      );
    }
    if (allCounts.choiceNews - allCounts.choiceNewsBatch !== 0) {
      addFailure(
        `home must not fan out single news latest requests, got ${allCounts.choiceNews - allCounts.choiceNewsBatch}`,
      );
    }
    if (allCounts.calendar < 1 || allCounts.incomeTrend < 1 || allCounts.homeSummary < 1) {
      addFailure(
        `expected calendar/income-trend/home-summary to load, got calendar=${allCounts.calendar}, incomeTrend=${allCounts.incomeTrend}, homeSummary=${allCounts.homeSummary}`,
      );
    }
    if (allCounts.uiRequestTotal > MAX_UI_REQUESTS) {
      addFailure(
        `home issued ${allCounts.uiRequestTotal} /ui+/api requests, over the ${MAX_UI_REQUESTS} budget (baseline 2026-08-12: 18).`,
      );
    }

    return {
      ready,
      initialCounts,
      allCounts,
      firstTwentyRequests: requestLog.slice(0, 20).map((entry) => ({
        t: entry.t,
        type: entry.type,
        url: normalizeUrl(entry.url),
      })),
      uiRequests: requestLog
        .filter((entry) => entry.url.includes("/ui/") || entry.url.includes("/api/"))
        .map((entry) => ({
          t: entry.t,
          url: normalizeUrl(entry.url),
        })),
    };
  } finally {
    await context.close();
    await browser.close();
  }
}

const ready = await fetchReadyStatus();
const home = ready.homePrewarm?.status === "ready" ? await sampleHome() : null;
const summary = {
  baseUrl,
  apiReadyUrl,
  mode: "live-dev",
  thresholds: {
    firstScreenObservationMs,
    postFirstScreenMaxWaitMs,
  },
  ready,
  home,
  failures,
};

if (failures.length > 0) {
  console.error("[home-startup-live] Live startup sample failed.");
  console.error(JSON.stringify(summary, null, 2));
  process.exitCode = 1;
} else {
  console.log("[home-startup-live] Live startup sample passed.");
  console.log(JSON.stringify(summary, null, 2));
}
