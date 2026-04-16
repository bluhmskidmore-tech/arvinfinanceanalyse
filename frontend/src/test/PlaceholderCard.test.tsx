import { render, screen } from "@testing-library/react";

import { PlaceholderCard } from "../features/workbench/components/PlaceholderCard";

describe("PlaceholderCard", () => {
  it("renders metric emphasis by default", () => {
    render(
      <PlaceholderCard title="标题" value="1,234" detail="说明文字" />,
    );

    expect(screen.getByText("标题")).toBeInTheDocument();
    expect(screen.getByText("1,234")).toBeInTheDocument();
    expect(screen.getByText("说明文字")).toBeInTheDocument();
  });

  it("supports text variant for list-style highlights", () => {
    render(
      <PlaceholderCard
        title="要点"
        value="较长的一段占位说明"
        detail="脚注"
        valueVariant="text"
      />,
    );

    expect(screen.getByText("较长的一段占位说明")).toBeInTheDocument();
  });
});
