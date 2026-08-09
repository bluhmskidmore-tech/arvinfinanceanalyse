import { describe, expect, it } from "vitest";

import { createMockHomeMarketTickerClient } from "./homeMarketTickerMockClient";
import { createMockMarketDataClient } from "./marketDataMockClient";

describe("Choice news mock clients", () => {
  it("keeps payload_json by default and reports it on the home market ticker mock", async () => {
    const client = createMockHomeMarketTickerClient();

    const payload = await client.getChoiceNewsEvents({
      limit: 5,
      offset: 0,
      topicCode: "tushare.news",
    });

    expect(payload.result.payload_json_included).toBe(true);
    expect(payload.result.events[0]?.payload_json).toBeNull();
  });

  it("clears payload_json when explicitly excluded on the shared market-data mock", async () => {
    const client = createMockMarketDataClient();

    const payload = await client.getChoiceNewsEvents({
      limit: 5,
      offset: 0,
      topicCode: "C000003006",
      includePayloadJson: false,
    });

    expect(payload.result.payload_json_included).toBe(false);
    expect(payload.result.events[0]?.payload_json).toBeNull();
  });

  it("preserves payload_json when explicitly included on the shared market-data mock", async () => {
    const client = createMockMarketDataClient();

    const payload = await client.getChoiceNewsEvents({
      limit: 5,
      offset: 0,
      topicCode: "C000003006",
      includePayloadJson: true,
    });

    expect(payload.result.payload_json_included).toBe(true);
    expect(payload.result.events[0]?.payload_json).toContain("headline");
  });

  it("builds compare evidence from the returned page on both mock paths", async () => {
    const clients = [
      createMockHomeMarketTickerClient(),
      createMockMarketDataClient(),
    ];

    for (const client of clients) {
      const payload = await client.getChoiceNewsEvents({
        limit: 1,
        offset: 1,
        includePayloadJson: false,
      });
      const returnedEventId = payload.result.events[0]?.event_key;
      const comparison = payload.result.compare?.same_direction[0];

      expect(returnedEventId).toBeTruthy();
      expect(comparison?.event_count).toBe(1);
      expect(comparison?.source_event_ids).toEqual([returnedEventId]);
    }
  });
});
