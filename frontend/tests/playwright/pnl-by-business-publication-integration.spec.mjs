import { closeSync, existsSync, mkdirSync, mkdtempSync, openSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

import { test, expect } from "@playwright/test";

const FORMAL_STATE_BASE_URL =
  process.env.MOSS_PLAYWRIGHT_STATE_BASE_URL ??
  `http://127.0.0.1:${process.env.MOSS_PLAYWRIGHT_STATE_PORT ?? "5889"}`;
const FIXTURE_PORT = process.env.MOSS_PNL_PUBLICATION_FIXTURE_PORT ?? "15990";
const FIXTURE_BASE_URL = `http://127.0.0.1:${FIXTURE_PORT}`;
const REPO_ROOT = fileURLToPath(new URL("../../..", import.meta.url));
const pythonExecutable = process.platform === "win32" ? ["Scripts", "python.exe"] : ["bin", "python"];
const FIXTURE_PYTHON =
  process.env.MOSS_PNL_PUBLICATION_FIXTURE_PYTHON ??
  process.env.MOSS_PYTHON ??
  (process.env.VIRTUAL_ENV ? join(process.env.VIRTUAL_ENV, ...pythonExecutable) : undefined) ??
  [join(REPO_ROOT, "backend", ".venv", ...pythonExecutable),
    join(REPO_ROOT, ".venv", ...pythonExecutable)].find(existsSync);
if (!FIXTURE_PYTHON || !existsSync(FIXTURE_PYTHON)) {
  throw new Error("Prepare a repository Python environment or set MOSS_PNL_PUBLICATION_FIXTURE_PYTHON.");
}
const FIXTURE_SCRIPT = fileURLToPath(
  new URL("./fixtures/pnl-publication-backend.py", import.meta.url),
);

let fixtureProcess;
let fixtureRoot;
let sourceWriterProcess;
let sourceWriterRelease;

test.describe.configure({ mode: "serial" });

async function waitForFixture() {
  let lastError;
  // Real router imports and publication materialization can take over 40 seconds
  // on a cold mounted checkout; fail immediately if the owned child exits.
  for (let attempt = 0; attempt < 600; attempt += 1) {
    if (fixtureProcess.exitCode !== null) {
      throw new Error(`publication fixture exited (${fixtureProcess.exitCode}): ${readFileSync(join(fixtureRoot, "backend.log"), "utf8")}`);
    }
    try {
      const response = await fetch(`${FIXTURE_BASE_URL}/__fixture/health`);
      if (response.ok) return;
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`publication fixture did not start: ${String(lastError ?? "unknown error")}`);
}

async function holdSourceWriter() {
  const readyPath = join(fixtureRoot, "source-writer.ready");
  sourceWriterRelease = join(fixtureRoot, "source-writer.release");
  const writerLogFd = openSync(join(fixtureRoot, "source-writer.log"), "a");
  const writerCode = [
    "import os, time, duckdb",
    "from pathlib import Path",
    "source=Path(os.environ['MOSS_TEST_SOURCE'])",
    "ready=Path(os.environ['MOSS_TEST_READY'])",
    "release=Path(os.environ['MOSS_TEST_RELEASE'])",
    "conn=duckdb.connect(str(source), read_only=False)",
    "conn.execute('BEGIN TRANSACTION')",
    "conn.execute(\"UPDATE fact_pnl_by_business_page_envelope SET dependency_revision=dependency_revision WHERE report_date='2026-02-28'\")",
    "ready.write_text('ready', encoding='utf-8')",
    "deadline=time.monotonic()+60",
    "while not release.exists() and time.monotonic()<deadline: time.sleep(0.02)",
    "conn.execute('ROLLBACK')",
    "conn.close()",
  ].join("\n");
  sourceWriterProcess = spawn(FIXTURE_PYTHON, ["-c", writerCode], {
    cwd: REPO_ROOT,
    env: {
      ...process.env,
      MOSS_TEST_SOURCE: join(fixtureRoot, "source.duckdb"),
      MOSS_TEST_READY: readyPath,
      MOSS_TEST_RELEASE: sourceWriterRelease,
    },
    stdio: ["ignore", writerLogFd, writerLogFd],
    windowsHide: true,
  });
  closeSync(writerLogFd);
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (existsSync(readyPath)) return;
    if (sourceWriterProcess.exitCode !== null) {
      throw new Error(`source writer exited before acquiring the DuckDB lock (${sourceWriterProcess.exitCode})`);
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("source writer did not acquire the DuckDB lock");
}

async function releaseSourceWriter() {
  if (!sourceWriterProcess) return;
  if (sourceWriterRelease) writeFileSync(sourceWriterRelease, "release", "utf8");
  if (sourceWriterProcess.exitCode === null) {
    await Promise.race([
      new Promise((resolve) => sourceWriterProcess.once("exit", resolve)),
      new Promise((resolve) => setTimeout(resolve, 5_000)),
    ]);
  }
  if (sourceWriterProcess.exitCode === null) sourceWriterProcess.kill();
  sourceWriterProcess = undefined;
  sourceWriterRelease = undefined;
}

test.beforeAll(async () => {
  test.setTimeout(70_000);
  const base = process.env.MOSS_PNL_PUBLICATION_FIXTURE_BASE ?? tmpdir();
  mkdirSync(base, { recursive: true });
  fixtureRoot = mkdtempSync(join(base, "pnl-publication-e2e-"));
  const logFd = openSync(join(fixtureRoot, "backend.log"), "a");
  fixtureProcess = spawn(FIXTURE_PYTHON, [FIXTURE_SCRIPT], {
    cwd: REPO_ROOT,
    env: {
      ...process.env,
      MOSS_PNL_PUBLICATION_FIXTURE_ROOT: fixtureRoot,
      MOSS_PNL_PUBLICATION_FIXTURE_PORT: FIXTURE_PORT,
    },
    stdio: ["ignore", logFd, logFd],
    windowsHide: true,
  });
  closeSync(logFd);
  await waitForFixture();
});

test.afterAll(async () => {
  await releaseSourceWriter();
  fixtureProcess?.kill();
});

test.beforeEach(async ({ page }) => {
  // Use the isolated fixture's real router instead of Vite's live API proxy.
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/system-read-publication") {
      return route.fulfill({ json: { enabled: false, generation: null, coverage_dates: {} } });
    }
    if (url.pathname.startsWith("/api/pnl/")) {
      const response = await route.fetch({ url: `${FIXTURE_BASE_URL}${url.pathname}${url.search}` });
      return route.fulfill({ response });
    }
    if (/^\/(api|ui|health)(\/|$)/.test(url.pathname)) {
      return route.fulfill({ status: 503, json: { detail: "Not part of the publication browser fixture" } });
    }
    return route.continue();
  });
});

test("reads a sealed database generation through the real PnL router and rejects it after revocation", async ({ page }) => {
  const apiRequests = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/")) apiRequests.push(`${url.pathname}${url.search}`);
  });
  await holdSourceWriter();
  try {
    await page.goto(`${FORMAL_STATE_BASE_URL}/pnl-by-business-insights`, {
      waitUntil: "domcontentloaded",
    });
    const contractStatus = page.locator('[data-testid="pnl-by-business-insights-contract-status"]');
    await expect(contractStatus).toContainText("pnl-page-e2e-001", { timeout: 30_000 });
    await expect(contractStatus).toContainText("tr_pnl_business_insights_gs_a");
    await expect(page.locator('[data-testid="pnl-by-business-insights-concentration-kpis"]')).toContainText("53.13%");
    expect(apiRequests).toContain("/api/pnl/dates?page=by_business_insights");
    expect(apiRequests).toContain(
      "/api/pnl/by-business/precompute-status?year=2026&as_of_date=2026-02-28",
    );
    expect(apiRequests).toContain(
      "/api/pnl/by-business-insights?year=2026&as_of_date=2026-02-28&generation=pnl-page-e2e-001",
    );

    const revoke = await page.request.post(`${FIXTURE_BASE_URL}/__fixture/revoke/pnl-page-e2e-001`);
    expect(revoke.ok()).toBe(true);
    const revokedRead = await page.request.get(
      `${FIXTURE_BASE_URL}/api/pnl/by-business-insights?year=2026&as_of_date=2026-02-28&generation=pnl-page-e2e-001`,
    );
    expect(revokedRead.status()).toBe(409);
    expect(await revokedRead.text()).toContain("revoked");
  } finally {
    await releaseSourceWriter();
  }
});

test("operator preparation publishes a new generation before the React page reads its values", async ({ page }) => {
  const apiRequests = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/")) {
      apiRequests.push({ method: request.method(), url });
    }
  });

  await page.goto(`${FORMAL_STATE_BASE_URL}/pnl-by-business-insights`, {
    waitUntil: "domcontentloaded",
  });
  const preparationState = page.locator(
    '[data-testid="pnl-by-business-insights-precompute-state"]',
  );
  await expect(preparationState).toContainText("结果已过期", { timeout: 30_000 });

  const queuedResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "POST" &&
      url.pathname === "/api/pnl/by-business/precompute-rebuild"
    );
  });
  await page.getByRole("button", { name: "请求后台准备" }).click();
  const queuedResponse = await queuedResponsePromise;
  expect(queuedResponse.ok()).toBe(true);
  const queuedUrl = new URL(queuedResponse.url());
  expect(queuedUrl.searchParams.get("year")).toBe("2026");
  expect(queuedUrl.searchParams.get("scope")).toBe("selected");
  expect(queuedUrl.searchParams.get("as_of_date")).toBe("2026-02-28");
  expect(queuedUrl.searchParams.get("include_page_dependencies")).toBe("true");
  await expect(preparationState).toContainText("准备中");

  const drain = await page.request.post(`${FIXTURE_BASE_URL}/__fixture/drain-page-rebuild`);
  expect(drain.ok()).toBe(true);
  const drained = await drain.json();
  expect(drained.receipt.status).toBe("completed");
  expect(drained.receipt.publication_status).toBe("published");
  expect(drained.receipt.generation).not.toBe("pnl-page-e2e-001");
  expect(drained.status.readiness).toBe("ready");
  expect(drained.status.generation).toBe(drained.receipt.generation);

  const contractStatus = page.locator(
    '[data-testid="pnl-by-business-insights-contract-status"]',
  );
  await expect(contractStatus).toContainText(drained.receipt.generation, { timeout: 30_000 });
  await expect(contractStatus).toContainText("tr_pnl_business_insights_post_rebuild");
  await expect(
    page.locator('[data-testid="pnl-by-business-insights-concentration-kpis"]'),
  ).toContainText("54.13%");
  expect(
    apiRequests.some(
      ({ method, url }) =>
        method === "GET" &&
        url.pathname === "/api/pnl/by-business-insights" &&
        url.searchParams.get("generation") === drained.receipt.generation,
    ),
  ).toBe(true);
});
