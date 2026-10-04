import { describe, expect, it } from "vitest";

import { isPublicationShowcaseEnabled } from "./publicationShowcaseGate";

describe("publication showcase route gate", () => {
  it("opens only for a development mock-data session", () => {
    expect(
      isPublicationShowcaseEnabled({ dev: true, dataSource: " mock " }),
    ).toBe(true);
  });

  it("stays hidden from production and real-data sessions", () => {
    expect(
      isPublicationShowcaseEnabled({ dev: false, dataSource: "mock" }),
    ).toBe(false);
    expect(
      isPublicationShowcaseEnabled({ dev: true, dataSource: "real" }),
    ).toBe(false);
  });
});
