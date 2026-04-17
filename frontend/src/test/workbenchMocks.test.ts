import { describe, expect, it } from "vitest";

import {
  alertsPayload,
  contributionPayload,
  overviewPayload,
  placeholderSnapshots,
  pnlAttributionPayload,
  riskOverviewPayload,
  summaryPayload,
} from "../mocks/workbench";

describe("workbench mock payloads", () => {
  it("overviewPayload has title and minimum metric content", () => {
    expect(overviewPayload.title.trim().length).toBeGreaterThan(0);
    expect(overviewPayload.metrics.length).toBeGreaterThanOrEqual(4);
    expect(overviewPayload.metrics.every((m) => m.label.length > 0)).toBe(true);
  });

  it("summaryPayload has title and points", () => {
    expect(summaryPayload.title.trim().length).toBeGreaterThan(0);
    expect(summaryPayload.narrative.trim().length).toBeGreaterThan(0);
    expect(summaryPayload.points.length).toBeGreaterThanOrEqual(3);
  });

  it("pnlAttributionPayload has title and segments", () => {
    expect(pnlAttributionPayload.title.trim().length).toBeGreaterThan(0);
    expect(pnlAttributionPayload.segments.length).toBeGreaterThanOrEqual(3);
  });

  it("riskOverviewPayload has title and signals", () => {
    expect(riskOverviewPayload.title.trim().length).toBeGreaterThan(0);
    expect(riskOverviewPayload.signals.length).toBeGreaterThanOrEqual(3);
  });

  it("contributionPayload has title and rows", () => {
    expect(contributionPayload.title.trim().length).toBeGreaterThan(0);
    expect(contributionPayload.rows.length).toBeGreaterThanOrEqual(2);
  });

  it("alertsPayload has title and items", () => {
    expect(alertsPayload.title.trim().length).toBeGreaterThan(0);
    expect(alertsPayload.items.length).toBeGreaterThanOrEqual(2);
  });
});

describe("placeholderSnapshots", () => {
  const requiredKeys = [
    "dashboard",
    "operations-analysis",
    "liability-analytics",
    "risk-overview",
    "team-performance",
    "bond-analysis",
    "cube-query",
    "platform-config",
    "market-data",
  ] as const;

  it("includes stable section keys", () => {
    for (const key of requiredKeys) {
      expect(key in placeholderSnapshots).toBe(true);
    }
  });

  it("each snapshot has title, summary, and highlights", () => {
    for (const snap of Object.values(placeholderSnapshots)) {
      expect(snap.title.trim().length).toBeGreaterThan(0);
      expect(snap.summary.trim().length).toBeGreaterThan(0);
      expect(Array.isArray(snap.highlights)).toBe(true);
      expect(snap.highlights.length).toBeGreaterThanOrEqual(1);
    }
  });

  it("dashboard snapshot mentions shell-layer contract language", () => {
    expect(placeholderSnapshots.dashboard.summary).toContain("契约");
  });
});
