import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SectionCard } from "../components/SectionCard";

describe("SectionCard", () => {
  it("renders error state with extracted classes and retry action", () => {
    const onRetry = vi.fn();

    const { container } = render(
      <SectionCard title="Risk block" error onRetry={onRetry}>
        Healthy content
      </SectionCard>,
    );

    const errorText = screen.getByText("区块加载失败。");
    expect(errorText).toHaveClass("section-card__error-text");
    expect(errorText).not.toHaveAttribute("style");
    expect(container.querySelector(".section-card__error")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button"));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
