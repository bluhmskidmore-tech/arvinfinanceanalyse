import { fireEvent, render, screen } from "@testing-library/react";
import { createElement, type CSSProperties } from "react";
import { describe, expect, it, vi } from "vitest";

import { SectionCard } from "../components/SectionCard";

describe("SectionCard", () => {
  it("uses extracted shell class by default while preserving style passthrough", () => {
    const { container, rerender } = render(
      <SectionCard title="Default shell">Healthy content</SectionCard>,
    );

    const defaultCard = screen.getByText("Default shell").closest(".ant-card");
    expect(defaultCard).toHaveClass("section-card");
    expect(defaultCard).not.toHaveAttribute("style");

    const passthroughStyle: CSSProperties = { marginTop: 12 };
    rerender(createElement(SectionCard, { title: "Styled shell", style: passthroughStyle }, "Healthy content"));

    const styledCard = screen.getByText("Styled shell").closest(".ant-card");
    expect(styledCard).toHaveClass("section-card");
    expect(styledCard).toHaveStyle({ marginTop: "12px" });
    expect(container.querySelectorAll(".section-card")).toHaveLength(1);
  });

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
