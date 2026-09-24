import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CrossAssetHeroPanel } from "./CrossAssetHeroPanel";

describe("CrossAssetHeroPanel regime disclosure", () => {
  it("attaches the shared frontend-analytics disclosure chip next to the regime badge", () => {
    render(
      <CrossAssetHeroPanel
        conclusion="测试结论"
        regimeLabel="宽松抢跑"
        regimeDescription="体制说明"
        rateDirectionLabel="下行"
        reportDate="2026-04-14"
        compositeScore={0.42}
      />,
    );

    const heroPanel = screen.getByTestId("cross-asset-hero-panel");
    // 体制徽章为前端 identifyMarketRegime 派生：必须复用同页统一披露章（同文案同挂牌），
    // 不允许只留 title 悬停提示。
    const chip = within(heroPanel).getByTestId("cross-asset-frontend-analytics-chip");
    expect(chip).toHaveTextContent("分析口径 · 前端计算（非正式指标）");
    expect(chip.getAttribute("title")).toContain("不替代正式指标");

    // 原体制/利率方向徽章保持不变（含 title 说明）。
    const regimeChip = within(heroPanel).getByTitle("体制说明");
    expect(regimeChip).toHaveTextContent("体制 宽松抢跑");
  });
});
