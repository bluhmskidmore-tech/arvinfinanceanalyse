import { createServer } from "node:http";
import { spawnSync } from "node:child_process";
import { existsSync, statSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { basename, extname, join, normalize, relative, resolve } from "node:path";

import { chromium } from "playwright";

const frontendRoot = process.cwd();
const distRoot = resolve(frontendRoot, "dist");
const distIndexPath = resolve(distRoot, "index.html");
const assetsRoot = resolve(distRoot, "assets");
const reportDate = "2026-04-30";
const hydrationTimeoutMs = 12_000;
const deferredAssetTimeoutMs = 5_000;
const agGridAssetPattern = /^agGridInstitutional-[A-Za-z0-9_-]+\.(?:css|js)$/;

function buildProductionBundle() {
  const npmExecPath = process.env.npm_execpath;
  if (!npmExecPath) {
    throw new Error("npm_execpath is unavailable; run this guard through npm.");
  }
  const result = spawnSync(process.execPath, [npmExecPath, "run", "build:fast"], {
    cwd: frontendRoot,
    env: {
      ...process.env,
      VITE_DATA_SOURCE: "real",
    },
    stdio: "inherit",
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function contentTypeForPath(filePath) {
  switch (extname(filePath)) {
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
    case ".woff2":
      return "font/woff2";
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

async function serveDistRequest(request, response) {
  const requestUrl = new URL(request.url ?? "/", "http://127.0.0.1");
  let filePath = distFilePath(requestUrl.pathname);
  if (!existsSync(filePath) || statSync(filePath).isDirectory()) {
    filePath = distIndexPath;
  }
  const body = await readFile(filePath);
  response.writeHead(200, {
    "cache-control": "no-store",
    "content-type": contentTypeForPath(filePath),
  });
  response.end(body);
}

async function createProductionServer() {
  const server = createServer((request, response) => {
    void serveDistRequest(request, response).catch((error) => {
      response.writeHead(500, { "content-type": "text/plain; charset=utf-8" });
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
    throw new Error("Balance-analysis startup server did not expose a TCP port.");
  }
  return {
    baseUrl: `http://127.0.0.1:${address.port}`,
    close: () =>
      new Promise((resolveClose, rejectClose) => {
        server.close((error) => (error ? rejectClose(error) : resolveClose(undefined)));
      }),
  };
}

function apiPayload(pathname) {
  if (pathname === "/ui/balance-analysis/current-user") {
    return {
      display_name: "Startup guard",
      permissions: [],
      user_id: "startup-guard",
    };
  }

  const result = {
    cards: [],
    currency_basis: "CNY",
    details: [],
    items: [],
    operational_sections: [],
    position_scope: "all",
    report_date: reportDate,
    rows: [],
    summary: [],
    tables: [],
  };
  if (pathname === "/ui/balance-analysis/dates") {
    result.report_dates = [reportDate];
  }
  if (pathname === "/ui/balance-movement-analysis/dates") {
    result.currency_basis = "CNX";
    result.report_dates = [reportDate];
  }
  if (pathname === "/ui/balance-analysis/advanced-attribution") {
    Object.assign(result, {
      blocked_components: [],
      missing_inputs: [],
      mode: "analytical",
      scenario_inputs: {},
      scenario_name: null,
      status: "not_ready",
      upstream_summaries: {},
      warnings: [],
    });
  }
  return {
    result,
    result_meta: {
      as_of_date: reportDate,
      basis: "formal",
      quality_flag: "ok",
    },
  };
}

async function waitForAutomaticHydration(requestedApiPaths, pageMessages) {
  const deadline = Date.now() + hydrationTimeoutMs;
  const hasRequiredReads = () =>
    requestedApiPaths.some((path) => path === "/ui/balance-analysis/dates") &&
    requestedApiPaths.some(
      (path) => path === "/ui/balance-movement-analysis/dates?currency_basis=CNX",
    ) &&
    requestedApiPaths.some(
      (path) =>
        path.startsWith("/ui/balance-movement-analysis?") &&
        path.includes(`report_date=${reportDate}`),
    ) &&
    requestedApiPaths.some((path) =>
      path.startsWith(
        `/api/analysis/adb/comparison?start_date=${reportDate.slice(0, 4)}-01-01`,
      ),
    );

  while (!hasRequiredReads() && Date.now() < deadline) {
    await new Promise((resolveWait) => setTimeout(resolveWait, 50));
  }
  if (!hasRequiredReads()) {
    throw new Error(
      [
        `Automatic hydration did not finish. Requested API paths: ${requestedApiPaths.join(", ")}`,
        `Page messages: ${pageMessages.join(" | ") || "none"}`,
      ].join("\n"),
    );
  }
}

function assetBytes(assetName) {
  const assetPath = join(assetsRoot, assetName);
  return existsSync(assetPath) ? statSync(assetPath).size : 0;
}

if (process.argv.includes("--build")) {
  buildProductionBundle();
}

if (!existsSync(distIndexPath)) {
  throw new Error("Production dist is missing. Run `npm run build:fast` first.");
}

const server = await createProductionServer();
const browser = await chromium.launch({ headless: true });

try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();
  const requestedApiPaths = [];
  const requestedAssets = new Set();
  const pageMessages = [];

  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/ui/")) {
      requestedApiPaths.push(`${url.pathname}${url.search}`);
    }
    if (url.pathname.startsWith("/assets/")) {
      requestedAssets.add(basename(url.pathname));
    }
  });
  page.on("console", (message) => {
    if (message.type() === "error") {
      pageMessages.push(`console: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => {
    pageMessages.push(`pageerror: ${error.message}`);
  });

  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/ui/")) {
      await route.fulfill({
        body: JSON.stringify(apiPayload(url.pathname)),
        contentType: "application/json",
        status: 200,
      });
      return;
    }
    await route.continue();
  });

  await page.goto(`${server.baseUrl}/balance-analysis`, {
    waitUntil: "domcontentloaded",
  });
  try {
    await page
      .locator('[data-testid="balance-analysis-page"]')
      .waitFor({ state: "visible", timeout: hydrationTimeoutMs });
  } catch (error) {
    throw new Error(
      `Balance-analysis page did not become visible. Browser messages: ${
        pageMessages.join(" | ") || "none"
      }`,
      { cause: error },
    );
  }
  await waitForAutomaticHydration(requestedApiPaths, pageMessages);
  await new Promise((resolveWait) => setTimeout(resolveWait, 150));

  const performanceAssets = await page.evaluate(() =>
    performance
      .getEntriesByType("resource")
      .map((entry) => new URL(entry.name).pathname)
      .filter((pathname) => pathname.startsWith("/assets/"))
      .map((pathname) => pathname.split("/").at(-1)),
  );
  for (const assetName of performanceAssets) {
    if (assetName) requestedAssets.add(assetName);
  }

  const sortedAssets = [...requestedAssets].sort();
  const fullClientAssets = sortedAssets.filter((assetName) =>
    /^client-[A-Za-z0-9_-]+\.js$/.test(assetName),
  );
  const startupAgGridAssets = sortedAssets.filter((assetName) =>
    agGridAssetPattern.test(assetName),
  );
  const routeAssets = sortedAssets.filter((assetName) =>
    /^BalanceAnalysisPage-[A-Za-z0-9_-]+\.(css|js)$/.test(assetName),
  );
  const requestedJavaScriptBytes = sortedAssets
    .filter((assetName) => assetName.endsWith(".js"))
    .reduce((total, assetName) => total + assetBytes(assetName), 0);

  if (startupAgGridAssets.length > 0) {
    throw new Error(
      `/balance-analysis loaded AG Grid before user interaction: ${startupAgGridAssets.join(", ")}`,
    );
  }

  await page
    .locator('[data-testid="balance-analysis-supplemental-panels"] > summary')
    .click();
  const deferredAssetDeadline = Date.now() + deferredAssetTimeoutMs;
  let sawAgGridJs = [...requestedAssets].some(
    (assetName) => agGridAssetPattern.test(assetName) && assetName.endsWith(".js"),
  );
  let sawAgGridCss = [...requestedAssets].some(
    (assetName) => agGridAssetPattern.test(assetName) && assetName.endsWith(".css"),
  );
  while (!(sawAgGridJs && sawAgGridCss) && Date.now() < deferredAssetDeadline) {
    await new Promise((resolveWait) => setTimeout(resolveWait, 50));
    sawAgGridJs = [...requestedAssets].some(
      (assetName) => agGridAssetPattern.test(assetName) && assetName.endsWith(".js"),
    );
    sawAgGridCss = [...requestedAssets].some(
      (assetName) => agGridAssetPattern.test(assetName) && assetName.endsWith(".css"),
    );
  }
  const expandedAgGridAssets = [...requestedAssets]
    .filter((assetName) => agGridAssetPattern.test(assetName))
    .sort();

  console.log(
    JSON.stringify(
      {
        expandedAgGridAssets,
        fullClientAssets,
        requestedAssetCount: sortedAssets.length,
        requestedJavaScriptBytes,
        routeAssets: routeAssets.map((assetName) => ({
          assetName,
          bytes: assetBytes(assetName),
        })),
      },
      null,
      2,
    ),
  );

  if (fullClientAssets.length > 0) {
    throw new Error(
      `/balance-analysis automatic hydration loaded the full API client: ${fullClientAssets.join(", ")}`,
    );
  }
  const missingDeferredAgGridAssets = [];
  if (!expandedAgGridAssets.some((assetName) => assetName.endsWith(".js"))) {
    missingDeferredAgGridAssets.push("JavaScript");
  }
  if (!expandedAgGridAssets.some((assetName) => assetName.endsWith(".css"))) {
    missingDeferredAgGridAssets.push("CSS");
  }
  if (missingDeferredAgGridAssets.length > 0) {
    throw new Error(
      `/balance-analysis did not load its deferred AG Grid ${missingDeferredAgGridAssets.join(
        " and ",
      )} asset after the supplemental panels were expanded.`,
    );
  }
  if (pageMessages.length > 0) {
    throw new Error(
      `/balance-analysis startup emitted browser errors: ${pageMessages.join(" | ")}`,
    );
  }

  console.log("Balance-analysis startup runtime guard passed.");
  await context.close();
} finally {
  await browser.close();
  await server.close();
}
