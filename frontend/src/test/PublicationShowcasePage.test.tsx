import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import PublicationShowcasePage from "../features/publication-showcase/PublicationShowcasePage";

function renderShowcase(view: string) {
  return render(
    <MemoryRouter initialEntries={[`/publication-showcase?view=${view}`]}>
      <PublicationShowcasePage />
    </MemoryRouter>,
  );
}

describe("PublicationShowcasePage", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it.each([
    ["overview", "publication-overview-view", "一句话看懂 MOSS"],
    ["investment", "publication-investment-view", "Crisis Score"],
    ["operations", "publication-operations-view", "正式分类损益"],
    ["agent", "publication-agent-view", "AI 组织后的分析材料"],
  ] as const)("renders the %s view with the expected content", async (view, testId, expected) => {
    vi.stubEnv("DEV", true);
    vi.stubEnv("VITE_DATA_SOURCE", "mock");

    renderShowcase(view);

    const viewRoot = await screen.findByTestId(testId);
    expect(within(viewRoot).getAllByText(expected).length).toBeGreaterThan(0);
    expect(
      screen.getByText("不构成投资、经营或业务审批结论"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("展示数据均为虚构示例，不对应任何机构或账户"),
    ).toBeInTheDocument();
  });

  it("keeps the AI result non-formal and leaves action to an authorized person", async () => {
    vi.stubEnv("DEV", true);
    vi.stubEnv("VITE_DATA_SOURCE", "mock");

    renderShowcase("agent");

    expect(await screen.findByText("formal_use_allowed = false")).toBeInTheDocument();
    expect(screen.getByText("由授权人员复核后，决定是否采取行动")).toBeInTheDocument();
    expect(screen.getByText("现有用户确认不等同于独立审批签字")).toBeInTheDocument();
  });
});
