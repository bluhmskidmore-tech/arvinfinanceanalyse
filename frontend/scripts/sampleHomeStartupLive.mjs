import { chromium } from "playwright";
import {
  collectHomeFullPage, createHomeRuntimeLog, runtimeReceipt,
  safeRequestUrl, servedFrontendProbes, writeRuntimeReceipt,
} from "./homeRuntimeAcceptance.mjs";

const baseUrl = process.env.MOSS_HOME_STARTUP_BASE_URL ?? "http://localhost:5888/";
const apiReadyUrl = process.env.MOSS_HOME_STARTUP_READY_URL ?? "http://127.0.0.1:7888/health/ready";
const firstScreenObservationMs = 400;
const postFirstScreenMaxWaitMs = 18_000;
// Request budget: the 2026-08-12 batched-news baseline was 18 reads. The governed
// macro-release context and parent-bank operating-revenue candidate added one
// bounded read each, while first-screen hydration now reuses the bundled home
// summary instead of a separate headline-kpis read: 18 + 2 - 1 = 19 business reads.
// The mandatory publication handshake is checked separately (exactly once),
// so it cannot conceal a repeated business read or a repeated handshake.
const MAX_UI_REQUESTS = 19;
// The risk section now reads its own balance-date basis and, when dates exist,
// decision items. Keep the established 19-read budget for the original modules
// and bound these two explicit additions separately instead of raising it.
const BALANCE_RISK_REQUEST_PATHS = ["/ui/balance-analysis/dates", "/ui/balance-analysis/decision-items"];
const MAX_CANDIDATE_FINANCIAL_INDICATOR_REQUESTS = 1;
const MAX_MACRO_RELEASE_CONTEXT_REQUESTS = 1;
const MAX_SEPARATE_HEADLINE_KPI_REQUESTS = 0;
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

async function fetchReadyStatus() {
  const response = await fetch(apiReadyUrl, { signal: AbortSignal.timeout(30_000) });
  const payload = await response.json();
  const homePrewarm = payload?.checks?.home_snapshot_prewarm ?? null;
  if (!response.ok) addFailure(`API readiness returned HTTP ${response.status}.`);
  if (!homePrewarm) {
    addFailure("API readiness is missing checks.home_snapshot_prewarm; restart the API before live startup sampling.");
  } else if (homePrewarm.status !== "ready") {
    addFailure(
      `home snapshot prewarm is not ready before live sample: status=${homePrewarm.status} error_present=${Boolean(homePrewarm.error)}`,
    );
  }
  return {
    statusCode: response.status,
    status: payload?.status,
    homePrewarm: homePrewarm ? { status: homePrewarm.status, error_present: Boolean(homePrewarm.error) } : null,
  };
}

async function sampleHome() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.route("**/*", (route) => route.continue());
  const page = await context.newPage();
  const log = createHomeRuntimeLog(page);
  const { requestLog, responseLog } = log;

  try {
    await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 30_000 });
    await page.waitForSelector('[data-testid="dashboard-home-page"]', { timeout: 30_000 });
    await page.waitForSelector('[data-testid="dashboard-home-hero"]', { timeout: 30_000 });
    await page.waitForTimeout(firstScreenObservationMs);

    const initialUrls = requestLog.map((entry) => entry.url);
    const marketTickerMockNeedles = [
      "/src/mocks/homeMarketTickerMockClient.ts",
      "/src/mocks/mockApiEnvelope.ts",
      "/assets/homeMarketTickerMockClient-",
      "/assets/mockApiEnvelope-",
    ];
    const firstScreenMockNeedles = [
      "/src/features/workbench/dashboard-home/dashboardHomeFirstScreenMockView.ts",
      "/assets/dashboardHomeFirstScreenMockView-",
    ];
    const fullPage = await collectHomeFullPage(page, log, { timeoutMs: postFirstScreenMaxWaitMs });
    failures.push(...fullPage.failures);
    try { frontendProbes = await servedFrontendProbes(page, log, baseUrl); }
    catch { addFailure("home served frontend document and entry hashes could not be bound"); }

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
    const publicationHandshakes = uiRequestUrls.filter(
      (url) => normalizeUrl(url).split("?")[0] === "/api/system-read-publication",
    ).length;
    const allCounts = {
      snapshot: count(allUrls, "/ui/home/snapshot"),
      marketRates: count(allUrls, "/ui/market-data/rates"),
      calendar: count(allUrls, "/ui/calendar/supply-auctions"),
      choiceNews: count(allUrls, "/ui/news/choice-events/latest"),
      choiceNewsBatch: count(allUrls, "/ui/news/choice-events/latest-batch"),
      incomeTrend: count(allUrls, "/ui/home/income-trend"),
      candidateFinancialIndicators: count(
        allUrls,
        "/api/ledger-pnl/candidate-financial-indicators",
      ),
      macroReleaseContext: count(allUrls, "/ui/home/macro-release-context"),
      homeSummary: countAny(allUrls, [
        "/ui/bond-dashboard/home-summary",
        "/api/bond-dashboard/home-summary",
      ]),
      separateHeadlineKpis: count(allUrls, "/api/bond-dashboard/headline-kpis"),
      uiRequestTotal: uiRequestUrls.length,
      publicationHandshakes,
      businessRequestTotal: uiRequestUrls.length - publicationHandshakes,
      balanceRiskRequests: uiRequestUrls.filter((url) => BALANCE_RISK_REQUEST_PATHS.includes(new URL(url).pathname)).length,
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
    if (
      allCounts.candidateFinancialIndicators >
      MAX_CANDIDATE_FINANCIAL_INDICATOR_REQUESTS
    ) {
      addFailure(
        `candidate financial indicators issued ${allCounts.candidateFinancialIndicators} requests; expected at most ${MAX_CANDIDATE_FINANCIAL_INDICATOR_REQUESTS}.`,
      );
    }
    if (allCounts.macroReleaseContext > MAX_MACRO_RELEASE_CONTEXT_REQUESTS) {
      addFailure(
        `macro release context issued ${allCounts.macroReleaseContext} requests; expected at most ${MAX_MACRO_RELEASE_CONTEXT_REQUESTS}.`,
      );
    }
    if (allCounts.separateHeadlineKpis > MAX_SEPARATE_HEADLINE_KPI_REQUESTS) {
      addFailure(
        `home issued ${allCounts.separateHeadlineKpis} separate headline-kpis requests; the bundled home summary must supply that payload.`,
      );
    }
    if (allCounts.calendar < 1 || allCounts.incomeTrend < 1 || allCounts.homeSummary < 1) {
      addFailure(
        `expected calendar/income-trend/home-summary to load, got calendar=${allCounts.calendar}, incomeTrend=${allCounts.incomeTrend}, homeSummary=${allCounts.homeSummary}`,
      );
    }
    if (allCounts.publicationHandshakes !== 1) {
      addFailure(`expected one publication handshake, got ${allCounts.publicationHandshakes}.`);
    }
    for (const path of BALANCE_RISK_REQUEST_PATHS) {
      const requests = uiRequestUrls.filter((url) => new URL(url).pathname === path).length;
      if (requests > 1) addFailure(`home risk section issued ${requests} ${path} requests; expected at most one.`);
    }
    if (allCounts.businessRequestTotal - allCounts.balanceRiskRequests > MAX_UI_REQUESTS) {
      addFailure(
        `home issued ${allCounts.businessRequestTotal - allCounts.balanceRiskRequests} legacy business requests, over the ${MAX_UI_REQUESTS} budget (excluding publication and the two bounded balance-risk reads).`,
      );
    }

    return {
      ready,
      initialCounts,
      allCounts,
      fullPage,
      firstTwentyRequests: requestLog.slice(0, 20).map((entry) => ({
        t: entry.t,
        type: entry.type,
        url: safeRequestUrl(entry.url),
      })),
      uiRequests: requestLog
        .filter((entry) => entry.url.includes("/ui/") || entry.url.includes("/api/"))
        .map((entry) => ({
          t: entry.t,
          url: safeRequestUrl(entry.url),
        })),
    };
  } finally {
    await context.close();
    await browser.close();
  }
}

const startedAt = new Date().toISOString();
let ready = null;
let home = null;
let frontendProbes = [];
try {
  ready = await fetchReadyStatus();
  if (ready.homePrewarm?.status === "ready") home = await sampleHome();
} catch (error) {
  addFailure(`home runtime sampling could not complete: ${error instanceof Error ? error.name : "Error"}`);
}
const summary = runtimeReceipt({ baseUrl, startedAt, apiReadyUrl, mode: "live-dev", ready, home, failures, frontendProbes,
  thresholds: { firstScreenObservationMs, postFirstScreenMaxWaitMs } });
await writeRuntimeReceipt(summary);
if (failures.length) process.exitCode = 1;
