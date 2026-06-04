import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FilterBar, type FilterBarProps } from "../components/FilterBar";

describe("FilterBar", () => {
  it("renders its default class without inline layout defaults", () => {
    render(
      <FilterBar>
        <button type="button">Apply</button>
      </FilterBar>,
    );

    const filterBar = screen.getByRole("button", { name: "Apply" }).parentElement;

    expect(filterBar).toHaveClass("moss-filter-bar");
    expect(filterBar).not.toHaveAttribute("style");
  });

  it("lets callers keep classes without adding inline layout style", () => {
    render(
      <FilterBar className="custom-filter">
        <button type="button">Apply</button>
      </FilterBar>,
    );

    const filterBar = screen.getByRole("button", { name: "Apply" }).parentElement;

    expect(filterBar).toHaveClass("moss-filter-bar");
    expect(filterBar).toHaveClass("custom-filter");
    expect(filterBar).not.toHaveAttribute("style");
  });

  it("preserves the caller style override API", () => {
    const customProps: Pick<FilterBarProps, "className" | "style"> = {
      className: "custom-filter",
      style: { gap: 20, justifyContent: "flex-end" },
    };

    render(
      <FilterBar {...customProps}>
        <button type="button">Apply</button>
      </FilterBar>,
    );

    const filterBar = screen.getByRole("button", { name: "Apply" }).parentElement;

    expect(filterBar).toHaveClass("moss-filter-bar");
    expect(filterBar).toHaveClass("custom-filter");
    expect(filterBar).toHaveStyle({
      gap: "20px",
      justifyContent: "flex-end",
    });
  });
});
