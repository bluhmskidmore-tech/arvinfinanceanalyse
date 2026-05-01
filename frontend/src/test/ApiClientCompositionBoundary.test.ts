import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { createApiClient } from "../api/client";

const clientSource = readFileSync(resolve(process.cwd(), "src/api/client.ts"), "utf8");
const marketDataSource = readFileSync(resolve(process.cwd(), "src/api/marketDataClient.ts"), "utf8");

describe("ApiClient composition boundary", () => {
  it("keeps the public market-data source preview surface available from createApiClient", () => {
    const client = createApiClient({ mode: "mock" });

    expect(typeof client.getSourceFoundation).toBe("function");
    expect(typeof client.refreshSourcePreview).toBe("function");
    expect(typeof client.getSourcePreviewRefreshStatus).toBe("function");
    expect(typeof client.getSourceFoundationHistory).toBe("function");
    expect(typeof client.getSourceFoundationRows).toBe("function");
    expect(typeof client.getSourceFoundationTraces).toBe("function");
    expect(typeof client.getChoiceNewsEvents).toBe("function");
    expect(typeof client.ingestTushareNprNews).toBe("function");
    expect(typeof client.getResearchCalendarEvents).toBe("function");
  });

  it("keeps source-preview, news, and research-calendar implementation out of client.ts", () => {
    expect(clientSource).not.toContain("MOCK_SOURCE_FOUNDATION_SUMMARIES");
    expect(clientSource).not.toContain("MOCK_CHOICE_NEWS_EVENTS");
    expect(clientSource).not.toContain("buildMockResearchCalendarEvents");
    expect(clientSource).not.toContain("buildMockChoiceNewsEnvelope");
    expect(clientSource).not.toMatch(/async getSourceFoundation\(/);
    expect(clientSource).not.toMatch(/async refreshSourcePreview\(/);
    expect(clientSource).not.toMatch(/async getSourcePreviewRefreshStatus\(/);
    expect(clientSource).not.toMatch(/async getSourceFoundationHistory\(/);
    expect(clientSource).not.toMatch(/async getSourceFoundationRows\(/);
    expect(clientSource).not.toMatch(/async getSourceFoundationTraces\(/);
    expect(clientSource).not.toMatch(/async getChoiceNewsEvents\(/);
    expect(clientSource).not.toMatch(/async getResearchCalendarEvents\(/);
    expect(clientSource).not.toMatch(/async ingestTushareNprNews\(/);
  });

  it("requires marketDataClient.ts to own the extracted market-data composition slice", () => {
    expect(marketDataSource).toMatch(/async getSourceFoundation\(/);
    expect(marketDataSource).toMatch(/async refreshSourcePreview\(/);
    expect(marketDataSource).toMatch(/async getSourcePreviewRefreshStatus\(/);
    expect(marketDataSource).toMatch(/async getSourceFoundationHistory\(/);
    expect(marketDataSource).toMatch(/async getSourceFoundationRows\(/);
    expect(marketDataSource).toMatch(/async getSourceFoundationTraces\(/);
    expect(marketDataSource).toMatch(/async getChoiceNewsEvents\(/);
    expect(marketDataSource).toMatch(/async getResearchCalendarEvents\(/);
    expect(marketDataSource).toMatch(/async ingestTushareNprNews\(/);
  });
});
