import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { PageAsyncSection } from "./PageAsyncSection";

function renderSection(
  overrides: Partial<Parameters<typeof PageAsyncSection>[0]> = {},
) {
  const onRetry = vi.fn();
  const view = render(
    <PageAsyncSection
      title="收益归因"
      isLoading={false}
      isError={false}
      isEmpty={false}
      onRetry={onRetry}
      {...overrides}
    >
      <div data-testid="inner">loaded</div>
    </PageAsyncSection>,
  );
  return { onRetry, ...view };
}

describe("PageAsyncSection", () => {
  it("uses the page-v2 evidence panel shell and fills height by default", () => {
    const { container } = renderSection();

    const shell = container.querySelector("section");
    expect(shell).toHaveClass("moss-page-v2-evidence-panel");
    expect(shell).toHaveClass("moss-page-async-section--fill");
    expect(screen.getByText("收益归因")).toBeInTheDocument();
    expect(screen.getByTestId("inner")).toBeInTheDocument();
  });

  it("allows local opt-out of fill height", () => {
    const { container } = renderSection({ fillHeight: false });

    const shell = container.querySelector("section");
    expect(shell).toHaveClass("moss-page-v2-evidence-panel");
    expect(shell).not.toHaveClass("moss-page-async-section--fill");
  });

  it("renders loading state on the page-v2 state surface with legacy copy", () => {
    renderSection({ isLoading: true });

    const loading = screen.getByTestId("page-async-section-loading");
    expect(loading).toHaveClass("moss-page-v2-state-surface");
    expect(loading).toHaveAttribute("data-state-variant", "loading");
    expect(screen.getByText("正在载入收益归因")).toBeInTheDocument();
    expect(loading.querySelector(".moss-skeleton-bar-stack")).toBeInTheDocument();
    expect(screen.queryByTestId("inner")).not.toBeInTheDocument();
  });

  it("renders error state with legacy copy and retry action", async () => {
    const user = userEvent.setup();
    const { onRetry } = renderSection({ isError: true });

    const error = screen.getByTestId("page-async-section-error");
    expect(error).toHaveClass("moss-page-v2-state-surface");
    expect(error).toHaveAttribute("data-state-variant", "error");
    expect(screen.getByText("数据载入失败。")).toBeInTheDocument();
    expect(
      screen.getByText("当前页面保留重试入口，不在浏览器端自行拼接正式口径。"),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("inner")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "重试" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("renders empty state with legacy copy", () => {
    renderSection({ isEmpty: true });

    const empty = screen.getByTestId("page-async-section-empty");
    expect(empty).toHaveClass("moss-page-v2-state-surface");
    expect(empty).toHaveAttribute("data-state-variant", "empty");
    expect(screen.getByText("当前暂无可展示内容。")).toBeInTheDocument();
    expect(screen.queryByTestId("inner")).not.toBeInTheDocument();
  });

  it("renders title and extra together in the header row", () => {
    renderSection({ extra: <span data-testid="extra">3 项</span> });

    const extra = screen.getByTestId("extra");
    expect(extra.parentElement).toHaveClass("moss-page-async-section__header");
    expect(screen.getByText("收益归因")).toBeInTheDocument();
    expect(screen.getByTestId("inner")).toBeInTheDocument();
  });
});
