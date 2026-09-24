import { describe, expect, it } from "vitest";

import { buildMockApiEnvelope } from "./mockApiEnvelope";

describe("buildMockApiEnvelope", () => {
  it("keeps mock source provenance even when simulating a formal business basis", () => {
    const envelope = buildMockApiEnvelope(
      "pnl.bridge",
      { value: 1 },
      {
        basis: "formal",
        formal_use_allowed: true,
        quality_flag: "warning",
      },
    );

    expect(envelope.result_meta.basis).toBe("formal");
    expect(envelope.result_meta.formal_use_allowed).toBe(true);
    expect(envelope.result_meta.source_surface).toBe("mock");
    expect(envelope.result_meta.quality_flag).toBe("warning");
  });
});
