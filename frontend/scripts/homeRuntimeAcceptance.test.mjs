import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm, rmdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";
import { after, before, test } from "node:test";
import { chromium } from "playwright";
import {
  HOME_REQUIRED_REQUESTS, collectHomeFullPage, createHomeRuntimeLog, runtimeReceipt, servedFrontendProbes,
} from "./homeRuntimeAcceptance.mjs";

let browser;
before(async () => { browser = await chromium.launch({ headless: true }); });
after(async () => { await browser?.close(); });

const sectionMarkup = {
  holdings: 'aria-labelledby="option-two-holdings-title"',
  risk: 'data-testid="dashboard-home-risk-exposure"',
  market: 'data-testid="dashboard-home-deferred-matrix"',
  support: 'data-testid="dashboard-home-option-two-support-band"',
  evidence: 'aria-labelledby="dashboard-home-research-evidence-title"',
};

function fixtureHtml(fault) {
  return `<!doctype html><html><head><meta charset="utf-8"><script type="module" src="/assets/fixture.js"></script></head><body>
  <main data-testid="dashboard-home-page"><div data-testid="dashboard-home-scroll-root" style="height:600px;overflow:auto">
  <header data-testid="dashboard-home-hero" style="height:${fault === "settlingtimeout" ? 0 : 650}px">synthetic first screen</header><div data-testid="dashboard-home-work-grid">
  ${Object.entries(sectionMarkup).map(([id, attributes]) => `<section ${fault === "missingmiddle" && id === "risk" ? '' : attributes} data-fixture-section="${id}" style="height:${fault === "settlingtimeout" ? 60 : 450}px">
    <p data-state="loading">读取中</p>${id === "market" ? '<button id="option-two-market-tab-research" role="tab">研究报告</button><div data-testid="dashboard-home-deferred-matrix-research" hidden>暂无数据</div>' : ""}</section>`).join("")}
  </div><aside data-state="backend-gap">数据源未接入</aside></div></main></body></html>`;
}

function fixtureScript(fault) {
  const grouped = Object.fromEntries(["startup", ...Object.keys(sectionMarkup)].map((section) =>
    [section, HOME_REQUIRED_REQUESTS.filter((entry) => entry.section === section).map((entry) => entry.paths[0])]));
  grouped.evidence.push("/ui/news/choice-events/latest-batch?groups=private-value");
  return `const grouped = ${JSON.stringify(grouped)};
  const fault = ${JSON.stringify(fault)};
  const fetchOne = async (path) => { const response = await fetch(path + (path.includes('?') ? '&' : '?') + 'report_date=private-value');
    if (!response.ok) throw Error('synthetic HTTP error'); await response.json(); };
  Promise.all(grouped.startup.map(fetchOne)).catch(() => {});
  const root = document.querySelector('[data-testid="dashboard-home-scroll-root"]');
  const observer = new IntersectionObserver((entries) => { for(const entry of entries) {
    if (!entry.isIntersecting) continue; observer.unobserve(entry.target);
    const section = entry.target.dataset.fixtureSection;
    Promise.all(grouped[section].map(fetchOne)).then(() => {
      if(fault === 'persistentloading' && section === 'support') return;
      entry.target.querySelector('[data-state]').dataset.state = 'empty';
      entry.target.querySelector('p').textContent = '暂无数据';
      if(fault === 'pageerror' && section === 'evidence') setTimeout(() => { throw Error('synthetic page error'); }, 0);
    }).catch(() => { entry.target.querySelector('[data-state]').dataset.state = 'error'; entry.target.querySelector('p').textContent = '加载失败'; });
  } }, {root});
  for(const section of root.querySelectorAll('[data-fixture-section]')) observer.observe(section);
  document.querySelector('#option-two-market-tab-research').onclick = () => {
    document.querySelector('[data-testid="dashboard-home-deferred-matrix-research"]').hidden = false;
  };`;
}

async function openFixture(fault) {
  const html = fixtureHtml(fault);
  const script = fixtureScript(fault);
  const timers = [];
  const server = createServer((request, response) => {
    const path = new URL(request.url, "http://localhost").pathname;
    if (path === "/") { response.writeHead(200, { "content-type": "text/html" }); response.end(html); return; }
    if (path === "/assets/fixture.js") { response.writeHead(200, { "content-type": "text/javascript" }); response.end(script); return; }
    if (path === "/health/ready") {
      response.writeHead(200, { "content-type": "application/json" });
      response.end('{"status":"ready","checks":{"home_snapshot_prewarm":{"status":"ready"}}}'); return;
    }
    const campisi = path === "/api/pnl-attribution/campisi/four-effects";
    const research = path === "/ui/home/research-reports";
    if (fault === "requestfailed" && research) { request.socket.destroy(); return; }
    if (fault === "missingdecision" && path === "/ui/balance-analysis/dates") {
      response.writeHead(200, { "content-type": "application/json" }); response.end('{"result":{"report_dates":["synthetic-date"]}}'); return;
    }
    if (fault === "stalledbody" && campisi) {
      response.writeHead(200, { "content-type": "application/json" }); response.write('{"value":'); return;
    }
    if ((fault === "late500" && campisi) || (fault === "late502" && research)) {
      timers.push(setTimeout(() => { response.writeHead(campisi ? 500 : 502); response.end("synthetic failure"); }, 900)); return;
    }
    response.writeHead(200, { "content-type": "application/json" }); response.end('{"items":[]}');
  });
  await new Promise((resolveListen) => server.listen(0, "127.0.0.1", resolveListen));
  const baseUrl = `http://127.0.0.1:${server.address().port}/`;
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const log = createHomeRuntimeLog(page);
  await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(400);
  return { page, log, baseUrl, html, script, close: async () => {
    timers.forEach(clearTimeout); await context.close(); server.closeAllConnections();
    await new Promise((resolveClose) => server.close(resolveClose));
  } };
}

async function sample(fixture) {
  return collectHomeFullPage(fixture.page, fixture.log, { timeoutMs: 4_000, pollMs: 40, quietMs: 150 });
}

test("healthy empty and unavailable states pass, with five observed sections and exact served hashes", async () => {
  const fixture = await openFixture("healthy");
  try {
    const fullPage = await sample(fixture);
    assert.deepEqual(fullPage.failures, []);
    assert.equal(fullPage.sections.length, 5);
    assert.ok(fullPage.sections.every((section) => section.seen));
    assert.equal(fullPage.research_tab, true);
    assert.ok(fullPage.states.unavailable > 0);
    assert.ok(fullPage.requests.every((request) => request.finished && request.status === 200));
    const probes = await servedFrontendProbes(fixture.page, fixture.log, fixture.baseUrl);
    assert.deepEqual(probes, [
      { path: "index.html", sha256: createHash("sha256").update(fixture.html).digest("hex") },
      { path: "assets/fixture.js", sha256: createHash("sha256").update(fixture.script).digest("hex") },
    ]);
    const receipt = runtimeReceipt({ baseUrl: fixture.baseUrl, startedAt: new Date().toISOString(), home: { fullPage }, failures: [], frontendProbes: probes });
    assert.equal(receipt.status, "passed");
    assert.equal(receipt.receipt_kind, "dashboard_home_runtime");
    assert.equal(receipt.schema_version, 1);
    assert.equal(receipt.scope, "dashboard-home-desktop");
    assert.equal(JSON.stringify(receipt).includes("private-value"), false);
  } finally { await fixture.close(); }
});

for (const [fault, path, status] of [["late500", "/api/pnl-attribution/campisi/four-effects", 500], ["late502", "/ui/home/research-reports", 502]]) {
  test(`${fault} fails after the legacy start-only checkpoint would have passed`, async () => {
    const fixture = await openFixture(fault);
    try {
      const completion = sample(fixture);
      const legacyPaths = ["/ui/market-data/rates", "/ui/calendar/supply-auctions", "/ui/news/choice-events/latest-batch", "/ui/home/income-trend", "/api/bond-dashboard/home-summary"];
      const deadline = Date.now() + 1_500;
      while (!legacyPaths.every((required) => fixture.log.requestLog.some((request) => request.path === required)) && Date.now() < deadline) {
        await fixture.page.waitForTimeout(20);
      }
      assert.ok(legacyPaths.every((required) => fixture.log.requestLog.some((request) => request.path === required)));
      assert.equal(fixture.log.responseLog.filter((response) => response.status >= 400).length, 0);
      const fullPage = await completion;
      assert.ok(fullPage.failures.includes(`home HTTP ${status}: ${path}`));
    } finally { await fixture.close(); }
  });
}

for (const [fault, expected] of [
  ["stalledbody", "home unfinished request: /api/pnl-attribution/campisi/four-effects"],
  ["persistentloading", "home persistent loading states:"],
  ["missingmiddle", "home section not observed: risk"],
  ["missingdecision", "home required request did not finish (risk): /ui/balance-analysis/decision-items"],
  ["pageerror", "home pageerror"],
  ["requestfailed", "home requestfailed: /ui/home/research-reports"],
]) {
  test(`${fault} is rejected by the actual Chromium full-page traversal`, async () => {
    const fixture = await openFixture(fault);
    try {
      const fullPage = await sample(fixture);
      assert.ok(fullPage.failures.some((failure) => failure.startsWith(expected)), JSON.stringify(fullPage.failures));
      if (fault === "stalledbody") {
        const request = fullPage.requests.find((entry) => entry.path === "/api/pnl-attribution/campisi/four-effects");
        assert.equal(request.status, 200);
        assert.equal(request.finished, false);
      }
    } finally { await fixture.close(); }
  });
}

for (const [fault, exitCode] of [["healthy", 0], ["late500", 1]]) {
  test(`live CLI writes its ${fault} receipt and correct exit code`, async () => {
    const fixture = await openFixture(fault);
    const outputDirectory = await mkdtemp(join(tmpdir(), "moss-home-runtime-"));
    const output = join(outputDirectory, "receipt.json");
    try {
      let actualCode = 0;
      let stdout;
      try {
        ({ stdout } = await promisify(execFile)(process.execPath, ["scripts/sampleHomeStartupLive.mjs", "--output", output], {
          cwd: process.cwd(), timeout: 30_000,
          env: { ...process.env, MOSS_HOME_STARTUP_BASE_URL: fixture.baseUrl, MOSS_HOME_STARTUP_READY_URL: new URL("/health/ready", fixture.baseUrl).toString() },
        }));
      } catch (error) { actualCode = error.code; stdout = error.stdout; }
      assert.equal(actualCode, exitCode);
      const receipt = JSON.parse(await readFile(output, "utf8"));
      assert.equal(receipt.status, exitCode === 0 ? "passed" : "failed");
      assert.deepEqual(JSON.parse(stdout), receipt);
      assert.equal(receipt.frontend_probes.length, 2);
      assert.equal(JSON.stringify(receipt).includes("private-value"), false);
      if (exitCode !== 0) assert.ok(receipt.home.fullPage.failures.some((failure) => failure.includes("home HTTP 500")));
    } finally {
      await fixture.close(); await rm(output, { force: true }); await rmdir(outputDirectory);
    }
  });
}

test("finishing all reads just before the deadline cannot bypass the settling window", async () => {
  const fixture = await openFixture("settlingtimeout");
  try {
    const fullPage = await collectHomeFullPage(fixture.page, fixture.log, { timeoutMs: 1_000, pollMs: 20, quietMs: 2_000 });
    assert.ok(fullPage.sections.every((section) => section.seen));
    assert.ok(fullPage.requests.every((request) => request.finished && request.status === 200));
    assert.deepEqual(fullPage.failures, ["home full-page settling deadline exceeded"]);
  } finally { await fixture.close(); }
});
