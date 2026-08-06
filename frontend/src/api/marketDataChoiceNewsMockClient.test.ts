import { describe, expect, it } from "vitest";

import { createApiClient } from "./client";

describe("market-data Choice news mock contract", () => {
  it("omits structured payloads when includePayloadJson is false", async () => {
    const client = createApiClient({ mode: "mock" });
    const envelope = await client.getChoiceNewsEvents({
      limit: 20,
      offset: 0,
      includePayloadJson: false,
    });

    expect(envelope.result.payload_json_included).toBe(false);
    expect(envelope.result.events.some((event) => event.payload_json !== null)).toBe(false);
    const structuredOnly = envelope.result.events.find((event) => event.event_key === "ce_mock_002");
    expect(structuredOnly).toBeDefined();
    expect(structuredOnly?.payload_text).toBeNull();
    expect(structuredOnly?.payload_json).toBeNull();
    expect(structuredOnly?.display_text).toBe(
      "Policy follow-up - PBOC open-market operation commentary stream.",
    );
  });

  it("preserves structured payloads under the backend-compatible default", async () => {
    const client = createApiClient({ mode: "mock" });
    const envelope = await client.getChoiceNewsEvents({ limit: 20, offset: 0 });

    expect(envelope.result.payload_json_included).toBe(true);
    const structuredOnly = envelope.result.events.find((event) => event.event_key === "ce_mock_002");
    expect(structuredOnly).toBeDefined();
    expect(structuredOnly?.payload_text).toBeNull();
    expect(structuredOnly?.payload_json).toContain("Policy follow-up");
  });
});
