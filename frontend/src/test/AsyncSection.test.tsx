import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AsyncSection } from "../features/executive-dashboard/components/AsyncSection";

describe("AsyncSection", () => {
  it("renders loading state", () => {
    render(
      <AsyncSection
        title="收益归因"
        isLoading
        isError={false}
        isEmpty={false}
        onRetry={() => undefined}
      >
        <div>loaded</div>
      </AsyncSection>,
    );

    expect(screen.getByText("正在载入收益归因")).toBeInTheDocument();
  });

  it("keeps full-height layout by default and allows local opt-out", () => {
    const { container, rerender } = render(
      <AsyncSection
        title="layout"
        isLoading={false}
        isError={false}
        isEmpty={false}
        onRetry={() => undefined}
      >
        <div>loaded</div>
      </AsyncSection>,
    );

    const filledSection = container.querySelector("section");
    expect(filledSection).toHaveClass("async-section");
    expect(filledSection).toHaveClass("async-section--fill");
    expect(filledSection).not.toHaveAttribute("style");

    rerender(
      <AsyncSection
        title="layout"
        isLoading={false}
        isError={false}
        isEmpty={false}
        fillHeight={false}
        onRetry={() => undefined}
      >
        <div>loaded</div>
      </AsyncSection>,
    );

    const autoSection = container.querySelector("section");
    expect(autoSection).toHaveClass("async-section");
    expect(autoSection).toHaveClass("async-section--auto");
    expect(autoSection).not.toHaveAttribute("style");
  });

  it("uses the extracted AsyncSection shell class without inline token variables", () => {
    const { container } = render(
      <AsyncSection
        title="layout"
        isLoading={false}
        isError={false}
        isEmpty={false}
        onRetry={() => undefined}
      >
        <div>loaded</div>
      </AsyncSection>,
    );

    const section = container.querySelector("section");
    expect(section).toHaveClass("async-section");
    expect(section).not.toHaveAttribute("style");
  });

  it("renders empty state", () => {
    render(
      <AsyncSection
        title="预警与事件"
        isLoading={false}
        isError={false}
        isEmpty
        onRetry={() => undefined}
      >
        <div>loaded</div>
      </AsyncSection>,
    );

    expect(screen.getByText("当前暂无可展示内容。")).toBeInTheDocument();
  });

  it("renders error state and supports retry", async () => {
    const onRetry = vi.fn();
    const user = userEvent.setup();

    render(
      <AsyncSection
        title="风险全景"
        isLoading={false}
        isError
        isEmpty={false}
        onRetry={onRetry}
      >
        <button type="button">loaded</button>
      </AsyncSection>,
    );

    expect(screen.getByText("数据载入失败。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /重\s*试/ }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
