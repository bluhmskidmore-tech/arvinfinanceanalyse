import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AlertList } from "../components/AlertList";
import { designTokens } from "../theme/designSystem";

describe("AlertList", () => {
  it("renders alert details with extracted layout classes", () => {
    const { container } = render(
      <AlertList
        items={[
          {
            level: "danger",
            title: "限额突破",
            detail: "需要复核风险敞口",
            time: "09:30",
          },
        ]}
      />,
    );

    expect(screen.getByText("限额突破")).toBeInTheDocument();
    expect(screen.getByText("需要复核风险敞口")).toBeInTheDocument();
    expect(screen.getByText("09:30")).toBeInTheDocument();
    expect(container.querySelector(".alert-list")).toBeInTheDocument();
    expect(container.querySelector(".alert-list__dot")).toHaveStyle({
      background: designTokens.color.danger[500],
    });
  });
});
