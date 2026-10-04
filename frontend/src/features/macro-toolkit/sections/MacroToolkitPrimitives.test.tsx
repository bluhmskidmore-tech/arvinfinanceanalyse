import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ScoreTrack } from "./MacroToolkitPrimitives";

describe("ScoreTrack", () => {
  it.each([
    ["null", null],
    ["undefined", undefined],
    ["NaN", Number.NaN],
    ["positive infinity", Number.POSITIVE_INFINITY],
    ["negative infinity", Number.NEGATIVE_INFINITY],
  ])("does not display %s as a numeric score", (_, score) => {
    const { container } = render(<ScoreTrack score={score} />);

    expect(container.querySelector("progress[value]")).not.toBeInTheDocument();
    expect(container.querySelector("[aria-valuenow]")).not.toBeInTheDocument();
  });

  it.each([
    [0, 0],
    [42.5, 42.5],
    [100, 100],
    [-5, 0],
    [105, 100],
  ])("keeps the finite score %s accessible as %s", (score, expected) => {
    render(<ScoreTrack score={score} />);

    const track = screen.getByRole("progressbar", { name: "评分" });
    expect(track).toHaveAttribute("value", String(expected));
    expect(track).toHaveAttribute("max", "100");
  });
});
