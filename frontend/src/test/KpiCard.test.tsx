import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { KpiCard } from "../components/KpiCard";

describe("KpiCard", () => {
  it("preserves the full label in text and the native title attribute", () => {
    const label = "组合加权平均到期收益率（剔除发行类债券后口径）";

    render(<KpiCard label={label} value="2.45" unit="%" />);

    const title = screen.getByText(label);
    expect(title).toHaveTextContent(label);
    expect(title).toHaveAttribute("title", label);
  });
});
