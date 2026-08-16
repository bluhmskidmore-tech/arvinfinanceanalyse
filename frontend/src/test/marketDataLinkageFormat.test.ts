import { describe, expect, it } from "vitest";

import {
  correlationStrength,
  formatLinkageDirectionLabel,
  linkageDirectionTone,
} from "../features/market-data/lib/marketDataLinkageFormat";

describe("marketDataLinkageFormat", () => {
  it("maps linkage direction labels to Chinese pills", () => {
    expect(formatLinkageDirectionLabel("positive")).toBe("偏正");
    expect(formatLinkageDirectionLabel("negative")).toBe("偏负");
    expect(formatLinkageDirectionLabel("neutral")).toBe("中性");
    expect(linkageDirectionTone("negative")).toBe("down");
    expect(linkageDirectionTone("positive")).toBe("up");
  });

  it("classifies correlation strength for spread cards", () => {
    expect(correlationStrength(0.63)).toBe("strong");
    expect(correlationStrength(0.2)).toBe("weak");
    expect(correlationStrength(null)).toBe("none");
  });
});
