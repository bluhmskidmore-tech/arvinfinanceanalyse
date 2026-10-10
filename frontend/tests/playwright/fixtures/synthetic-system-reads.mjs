import { expect } from "@playwright/test";

export const SYNTHETIC_READ_GENERATION =
  "system-read-2026-08-31-00000000000000000001";
export const syntheticReadHeaders = {
  "X-MOSS-Read-Generation": SYNTHETIC_READ_GENERATION,
};

// Exact auxiliary reads made by the home view-model and its HTTP clients.
// They intentionally remain unavailable in these focused browser fixtures.
export const homeAuxiliaryGetPaths = [
  "/api/ledger-pnl/candidate-financial-indicators",
  "/api/bond-dashboard/home-summary",
  "/api/bond-analytics/portfolio-headlines",
  "/api/bond-analytics/position-changes",
  "/api/bond-analytics/credit-spread-migration",
  "/api/bond-analytics/return-decomposition",
  "/api/bond-analytics/yield-curve-term-structure",
  "/api/bond-analytics/krd-curve-risk",
  "/api/pnl-attribution/campisi/four-effects",
  "/ui/balance-analysis/dates",
  "/ui/market-data/rates",
  "/ui/home/income-trend",
  "/ui/home/research-reports",
  "/ui/home/macro-release-context",
  "/ui/calendar/supply-auctions",
  "/ui/news/choice-events/latest-batch",
];

export function assertSyntheticReadRequest(route, expectedPath) {
  const request = route.request();
  expect(request.method()).toBe("GET");
  expect(new URL(request.url()).pathname).toBe(expectedPath);
  expect(request.headers()["x-moss-read-generation"]).toBe(SYNTHETIC_READ_GENERATION);
}

export function assertNoUnexpectedServiceRequests(fixture, allowedGetPaths = []) {
  expect(fixture.unhandledRequests.filter(({ method, path }) =>
    method !== "GET" || !allowedGetPaths.includes(path),
  )).toEqual([]);
}

// Register before page-specific routes. Every service request remains synthetic,
// including after a test removes its temporary publication-handshake handler.
export async function installSyntheticSystemReads(page) {
  const unhandledRequests = [];
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!/^\/(api|ui|health)(\/|$)/.test(url.pathname)) {
      return route.continue();
    }
    if (!["GET", "HEAD"].includes(request.method())) {
      unhandledRequests.push({ method: request.method(), path: url.pathname });
      return route.fulfill({
        status: 405,
        headers: syntheticReadHeaders,
        json: { detail: "Not part of this synthetic browser fixture" },
      });
    }
    if (url.pathname === "/api/system-read-publication") {
      expect(request.method()).toBe("GET");
      return route.fulfill({
        headers: syntheticReadHeaders,
        json: {
          enabled: true,
          generation: SYNTHETIC_READ_GENERATION,
          coverage_dates: {},
        },
      });
    }
    unhandledRequests.push({ method: request.method(), path: url.pathname });
    return route.fulfill({
      status: 503,
      headers: syntheticReadHeaders,
      json: { detail: "Not part of this synthetic browser fixture" },
    });
  });
  return { unhandledRequests };
}
