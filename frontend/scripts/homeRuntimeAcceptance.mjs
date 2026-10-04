import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

export const HOME_SECTIONS = [
  { id: "holdings", selector: 'section[aria-labelledby="option-two-holdings-title"]' },
  { id: "risk", selector: '[data-testid="dashboard-home-risk-exposure"]' },
  { id: "market", selector: '[data-testid="dashboard-home-deferred-matrix"]' },
  { id: "support", selector: '[data-testid="dashboard-home-option-two-support-band"]' },
  { id: "evidence", selector: 'section[aria-labelledby="dashboard-home-research-evidence-title"]' },
];

// These are the requests owned by today's section gates, not a fixed observed
// request count. The decision-items read is conditional on balance dates.
export const HOME_REQUIRED_REQUESTS = [
  { section: "startup", paths: ["/api/system-read-publication"] },
  { section: "startup", paths: ["/ui/home/snapshot"] },
  { section: "holdings", paths: ["/ui/home/income-trend"] },
  { section: "holdings", paths: ["/api/bond-dashboard/home-summary", "/ui/bond-dashboard/home-summary"] },
  { section: "holdings", paths: ["/api/bond-analytics/top-holdings"] },
  { section: "holdings", paths: ["/api/bond-analytics/position-changes"] },
  { section: "holdings", paths: ["/api/bond-analytics/portfolio-headlines"] },
  { section: "holdings", paths: ["/api/ledger-pnl/candidate-financial-indicators"] },
  { section: "risk", paths: ["/ui/balance-analysis/dates"] },
  { section: "market", paths: ["/ui/market-data/rates"] },
  { section: "market", paths: ["/ui/home/research-reports"] },
  { section: "support", paths: ["/api/bond-analytics/credit-spread-migration", "/ui/bond-analytics/credit-spread-migration"] },
  { section: "support", paths: ["/api/bond-analytics/return-decomposition", "/ui/bond-analytics/return-decomposition"] },
  { section: "support", paths: ["/api/pnl-attribution/campisi/four-effects", "/ui/pnl-attribution/campisi-four-effects"] },
  { section: "support", paths: ["/api/bond-analytics/yield-curve-term-structure", "/ui/bond-analytics/yield-curve-term-structure"] },
  { section: "support", paths: ["/api/bond-analytics/krd-curve-risk"] },
  { section: "evidence", paths: ["/ui/calendar/supply-auctions"] },
  { section: "evidence", paths: ["/ui/news/choice-events/latest-batch"] },
  { section: "evidence", paths: ["/ui/home/macro-release-context"] },
];

export function normalizeBaseUrl(value) {
  const url = new URL(value);
  url.hash = "";
  url.search = "";
  return url.toString();
}

export function safeRequestUrl(value) {
  const url = new URL(value);
  const keys = [...new Set(url.searchParams.keys())].sort();
  return `${url.pathname}${keys.length ? `?${keys.join("&")}` : ""}`;
}

export function isBusinessRequest(value) {
  const path = new URL(value).pathname;
  return path.startsWith("/ui/") || path.startsWith("/api/");
}

export function createHomeRuntimeLog(page) {
  const startedAt = Date.now();
  const requestLog = [];
  const responseLog = [];
  const browserMessages = [];
  const requests = new Map();
  const frontendResponses = new Map();
  const balanceDates = { inspected: false, requiresDecisionItems: false };

  page.on("request", (request) => {
    const url = request.url();
    const path = new URL(url).pathname;
    if (!isBusinessRequest(url) && !path.startsWith("/assets/") && !path.startsWith("/src/")) return;
    const entry = { t: Date.now() - startedAt, method: request.method(), type: request.resourceType(), url,
      path, query_keys: [...new Set(new URL(url).searchParams.keys())].sort(), status: null, finished: false };
    requests.set(request, entry);
    requestLog.push(entry);
  });
  page.on("response", (response) => {
    const request = response.request();
    const entry = requests.get(request);
    if (entry) {
      entry.status = response.status();
      responseLog.push({ t: Date.now() - startedAt, status: response.status(), url: response.url() });
      if (entry.path === "/ui/balance-analysis/dates") {
        void response.json().then((payload) => {
          balanceDates.requiresDecisionItems = Array.isArray(payload?.result?.report_dates) && payload.result.report_dates.length > 0;
          balanceDates.inspected = true;
        }).catch(() => { balanceDates.inspected = true; });
      }
    }
    if (request.resourceType() === "document" || request.resourceType() === "script") {
      frontendResponses.set(response.url(), response);
    }
  });
  page.on("requestfinished", (request) => {
    const entry = requests.get(request);
    if (entry) {
      entry.finished = true;
      entry.finished_at_ms = Date.now() - startedAt;
    }
  });
  page.on("requestfailed", (request) => {
    const entry = requests.get(request);
    if (entry) entry.failed = true;
    // Do not retain exception text: failed URLs/messages can contain user data.
    browserMessages.push({ type: "requestfailed", path: new URL(request.url()).pathname });
  });
  page.on("pageerror", () => browserMessages.push({ type: "pageerror" }));
  return { requestLog, responseLog, browserMessages, frontendResponses, balanceDates };
}

async function terminalStates(page) {
  return page.locator('[data-testid="dashboard-home-page"]').evaluate((root) => {
    const counts = {};
    for (const node of root.querySelectorAll("[data-state], [data-status-kind]")) {
      const key = node.getAttribute("data-state") ?? node.getAttribute("data-status-kind");
      counts[key] = (counts[key] ?? 0) + 1;
    }
    const text = root.textContent ?? "";
    const loadingText = (text.match(/加载中|正在加载|读取中|查询中|请求中/g) ?? []).length;
    const errorText = (text.match(/加载失败|读取失败|查询失败|请求失败/g) ?? []).length;
    const skeletons = root.querySelectorAll('[data-testid*="skeleton"], [class*="skeleton" i]').length;
    return { counts, loading: (counts.loading ?? 0) + loadingText + skeletons + root.querySelectorAll('[aria-busy="true"]').length,
      errors: (counts.error ?? 0) + errorText,
      unavailable: (text.match(/未接入|暂不可用|暂无数据/g) ?? []).length };
  });
}

async function observeSectionsAndScroll(page, sections, advance = true) {
  return page.locator('[data-testid="dashboard-home-scroll-root"]').evaluate((root, { definitions, advance }) => {
    const viewport = root.getBoundingClientRect();
    const seen = definitions.filter(({ selector }) => {
      const node = root.querySelector(selector);
      if (!node || !node.getClientRects().length) return false;
      const box = node.getBoundingClientRect();
      return box.bottom > viewport.top && box.top < viewport.bottom && box.right > viewport.left && box.left < viewport.right;
    }).map(({ id }) => id);
    const before = root.scrollTop;
    if (advance) root.scrollTop = Math.min(root.scrollTop + Math.max(1, Math.floor(root.clientHeight * 0.6)), root.scrollHeight - root.clientHeight);
    return { seen, moved: root.scrollTop > before, atBottom: root.scrollTop + root.clientHeight >= root.scrollHeight - 1 };
  }, { definitions: sections, advance });
}

export async function collectHomeFullPage(page, log, {
  timeoutMs = 18_000, pollMs = 100, quietMs = 750, requiredRequests = HOME_REQUIRED_REQUESTS,
} = {}) {
  const deadline = Date.now() + timeoutMs;
  const seen = new Set();
  let researchTab = false;
  let settledSince = null;
  let lastRequestActivity = "";
  let states = { counts: {}, loading: 0, errors: 0, unavailable: 0 };
  let reachedBottom = false;
  let settled = false;
  let bodyTraversalStarted = false;
  // Use increments smaller than the viewport, so middle sections cannot be
  // skipped by an instantaneous jump to the bottom. Dynamic lazy content may
  // lengthen this same container while the traversal is in progress.
  while (Date.now() < deadline) {
    if (!bodyTraversalStarted && await page.locator(HOME_SECTIONS[0].selector).count()) {
      // The lazy body may appear after the sentinel was reached. Start its
      // traversal at the top of the same scroll root exactly once.
      await page.locator('[data-testid="dashboard-home-scroll-root"]').evaluate((root) => { root.scrollTop = 0; });
      bodyTraversalStarted = true;
    }
    const progress = await observeSectionsAndScroll(page, HOME_SECTIONS, false);
    // Let the browser deliver intersection notifications for this viewport
    // before advancing again; merely assigning scrollTop can skip callbacks
    // on the first cold Chromium frame even though a rectangle was observed.
    await page.evaluate(() => new Promise((resolveFrame) => {
      const timer = setTimeout(resolveFrame, 100);
      requestAnimationFrame(() => requestAnimationFrame(() => { clearTimeout(timer); resolveFrame(); }));
    }));
    progress.seen.forEach((id) => seen.add(id));
    reachedBottom = progress.atBottom;
    if (seen.has("market") && !researchTab) {
      const tab = page.locator('#option-two-market-tab-research[role="tab"]');
      if (await tab.count()) {
        await tab.click({ timeout: Math.max(1, deadline - Date.now()) });
        researchTab = await page.locator('[data-testid="dashboard-home-deferred-matrix-research"]').count() === 1;
      }
    }
    states = await terminalStates(page);
    const business = log.requestLog.filter((entry) => isBusinessRequest(entry.url));
    const requestActivity = business.map((entry) => `${entry.t}:${entry.status}:${entry.finished}:${Boolean(entry.failed)}`).join("|");
    if (requestActivity !== lastRequestActivity) settledSince = null;
    lastRequestActivity = requestActivity;
    const currentRequired = log.balanceDates.requiresDecisionItems
      ? [...requiredRequests, { section: "risk", paths: ["/ui/balance-analysis/decision-items"] }]
      : requiredRequests;
    // A section that is visually in range must get an opportunity to dispatch
    // its observer-driven reads before we scroll away. Requests may complete
    // later; their bodies are awaited at the final settling stage.
    const sectionReadsStarted = currentRequired.filter((group) => progress.seen.includes(group.section))
      .every(({ paths }) => business.some((entry) => paths.includes(entry.path)));
    if (sectionReadsStarted) reachedBottom = (await observeSectionsAndScroll(page, HOME_SECTIONS)).atBottom;
    const hasRequired = currentRequired.every(({ paths }) => business.some((entry) => paths.includes(entry.path) && entry.finished)) && log.balanceDates.inspected;
    const pending = business.some((entry) => !entry.finished && !entry.failed);
    const complete = seen.size === HOME_SECTIONS.length && researchTab && reachedBottom && hasRequired && !pending && states.loading === 0;
    if (complete) {
      settledSince ??= Date.now();
      if (Date.now() - settledSince >= quietMs) { settled = true; break; }
    } else settledSince = null;
    await page.waitForTimeout(Math.min(pollMs, Math.max(1, deadline - Date.now())));
  }
  const requests = log.requestLog.filter((entry) => isBusinessRequest(entry.url)).map((entry) => ({
    path: entry.path, query_keys: entry.query_keys, status: entry.status, finished: entry.finished,
    elapsed_ms: entry.finished_at_ms == null ? null : entry.finished_at_ms - entry.t,
    ...(entry.failed ? { failed: true } : {}),
  }));
  const failures = [];
  if (!reachedBottom) failures.push("home internal scroll root did not reach its final bottom");
  if (!settled) failures.push("home full-page settling deadline exceeded");
  for (const section of HOME_SECTIONS) if (!seen.has(section.id)) failures.push(`home section not observed: ${section.id}`);
  if (!researchTab) failures.push("home research tab was not exercised");
  const finalRequired = log.balanceDates.requiresDecisionItems
    ? [...requiredRequests, { section: "risk", paths: ["/ui/balance-analysis/decision-items"] }]
    : requiredRequests;
  for (const group of finalRequired) {
    if (!requests.some((entry) => group.paths.includes(entry.path) && entry.finished)) {
      failures.push(`home required request did not finish (${group.section}): ${group.paths[0]}`);
    }
  }
  for (const request of requests) {
    if (request.status >= 400) failures.push(`home HTTP ${request.status}: ${request.path}`);
    if (!request.finished) failures.push(`home unfinished request: ${request.path}`);
    if (request.failed) failures.push(`home request failed: ${request.path}`);
  }
  for (const event of log.browserMessages) failures.push(event.type === "pageerror" ? "home pageerror" : `home requestfailed: ${event.path}`);
  if (states.loading > 0) failures.push(`home persistent loading states: ${states.loading}`);
  if (states.errors > 0) failures.push(`home error states: ${states.errors}`);
  return { sections: HOME_SECTIONS.map(({ id }) => ({ id, seen: seen.has(id) })), research_tab: researchTab,
    requests, states, failures, required_decision_items: log.balanceDates.requiresDecisionItems, deadline_ms: timeoutMs };
}

export async function servedFrontendProbes(page, log, baseUrl) {
  const documentResponse = log.frontendResponses.get(normalizeBaseUrl(baseUrl));
  if (!documentResponse || documentResponse.status() !== 200) throw new Error("served frontend document response is missing");
  const html = await documentResponse.body();
  const moduleSrc = await page.locator('script[type="module"][src]').evaluateAll((scripts) =>
    scripts.map((node) => node.getAttribute("src")).find((src) => src && !src.includes("/@vite/client")));
  if (!moduleSrc) throw new Error("served frontend module entry is missing");
  const entryUrl = new URL(moduleSrc, baseUrl);
  if (entryUrl.origin !== new URL(baseUrl).origin) throw new Error("served frontend module entry must have the same origin");
  const entryResponse = log.frontendResponses.get(entryUrl.toString());
  if (!entryResponse || entryResponse.status() !== 200) throw new Error("served frontend module entry response is missing");
  const entry = await entryResponse.body();
  return [{ path: "index.html", sha256: createHash("sha256").update(html).digest("hex") },
    { path: entryUrl.pathname.replace(/^\//, ""), sha256: createHash("sha256").update(entry).digest("hex") }];
}

export function runtimeReceipt({ baseUrl, startedAt, home, failures, frontendProbes = [], ...extras }) {
  return { receipt_kind: "dashboard_home_runtime", schema_version: 1, scope: "dashboard-home-desktop",
    base_url: normalizeBaseUrl(baseUrl), started_at: startedAt, finished_at: new Date().toISOString(),
    status: failures.length ? "failed" : "passed", failures, frontend_probes: frontendProbes, home, ...extras };
}

export async function writeRuntimeReceipt(receipt, argv = process.argv.slice(2)) {
  const outputIndex = argv.indexOf("--output");
  if (outputIndex >= 0) {
    const output = argv[outputIndex + 1];
    if (!output || output.startsWith("--")) throw new Error("--output requires a file path");
    const outputPath = resolve(output);
    await mkdir(dirname(outputPath), { recursive: true });
    await writeFile(outputPath, `${JSON.stringify(receipt, null, 2)}\n`, "utf8");
  }
  console.log(JSON.stringify(receipt, null, 2));
}
