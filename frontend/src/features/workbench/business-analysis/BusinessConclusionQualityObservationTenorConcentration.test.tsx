import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BusinessConclusion } from "./BusinessConclusion";
import { QualityObservation } from "./QualityObservation";
import { TenorConcentrationPanel } from "./TenorConcentrationPanel";
import tenorStyles from "./TenorConcentrationPanel.module.css";

const tenorStylesText = readFileSync(
  resolve(
    process.cwd(),
    "src/features/workbench/business-analysis/TenorConcentrationPanel.module.css",
  ),
  "utf8",
);

function getEvidencePanel(heading: string) {
  const panel = screen.getByRole("heading", { level: 2, name: heading }).closest("section");
  expect(panel).toHaveClass("moss-page-v2-evidence-panel");
  return panel as HTMLElement;
}

function cssRuleBody(selector: string) {
  const match = tenorStylesText.match(new RegExp(`\\.${selector}\\s*\\{([^}]*)\\}`));
  expect(match).not.toBeNull();
  return match?.[1] ?? "";
}

function getRowByLabel(label: string) {
  const row = screen.getByText(label, { exact: true }).parentElement;
  expect(row).not.toBeNull();
  return within(row as HTMLElement);
}

describe("business-analysis evidence panels", () => {
  it("keeps the governed business conclusion inside an EvidencePanel", () => {
    render(
      <BusinessConclusion
        reportDate="2026-02-28"
        view="monthly"
        rowCount={5}
        assetBusinessNetIncome="4.20"
        liabilityBusinessNetIncome="-1.30"
        grandBusinessNetIncome="2.90"
        missingFxCount={2}
      />,
    );

    const panel = getEvidencePanel("本期经营结论");
    expect(panel).toHaveTextContent("报告日 2026-02-28");
    expect(panel).toHaveTextContent("产品分类行 5 行");
    expect(panel).toHaveTextContent("资产净收入 4.20");
    expect(panel).toHaveTextContent("负债净收入 -1.30");
    expect(panel).toHaveTextContent("经营净收入 2.90");
    expect(panel).toHaveTextContent("外汇覆盖: 缺 2 对");
  });

  it("keeps quality values and statuses unchanged without inline styles", () => {
    render(
      <QualityObservation
        sourceCount={2}
        macroCount={3}
        newsCount={4}
        fxMaterializedCount={5}
        fxCandidateCount={6}
        missingFxCount={1}
      />,
    );

    const panel = getEvidencePanel("经营质量观察");
    expect(getRowByLabel("源批次数").getByText("2", { exact: true })).toBeInTheDocument();
    expect(getRowByLabel("源批次数").getByText("已到位", { exact: true })).toBeInTheDocument();
    expect(getRowByLabel("宏观最新点位").getByText("3", { exact: true })).toBeInTheDocument();
    expect(getRowByLabel("宏观最新点位").getByText("已到位", { exact: true })).toBeInTheDocument();
    expect(getRowByLabel("新闻事件").getByText("4", { exact: true })).toBeInTheDocument();
    expect(getRowByLabel("新闻事件").getByText("可读", { exact: true })).toBeInTheDocument();
    expect(getRowByLabel("正式外汇覆盖").getByText("5/6", { exact: true })).toBeInTheDocument();
    expect(getRowByLabel("正式外汇覆盖").getByText("关注", { exact: true })).toBeInTheDocument();
    expect(getRowByLabel("缺失货币对").getByText("1", { exact: true })).toBeInTheDocument();
    expect(getRowByLabel("缺失货币对").getByText("预警", { exact: true })).toBeInTheDocument();
    expect(panel.querySelector("[style]")).toBeNull();
  });

  it("keeps tenor rows unchanged with directional negative and neutral positive states", () => {
    render(<TenorConcentrationPanel />);

    const panel = getEvidencePanel("期限与集中度（示意）");
    const negativeValue = screen.getByText("-373.0 亿", { exact: true });
    const positiveValue = screen.getByText("+96.2 亿", { exact: true });
    expect(screen.getByText("1年内净缺口", { exact: true })).toBeInTheDocument();
    expect(screen.getByText("1-3年净缺口", { exact: true })).toBeInTheDocument();
    expect(screen.getByText("-128.5 亿", { exact: true })).toBeInTheDocument();
    expect(screen.getByText("3年以上净缺口", { exact: true })).toBeInTheDocument();
    expect(negativeValue.parentElement).toHaveClass(tenorStyles.row, tenorStyles.rowNegative);
    expect(negativeValue).toHaveClass(tenorStyles.value, tenorStyles.valueNegative);
    expect(positiveValue.parentElement).toHaveClass(tenorStyles.row, tenorStyles.rowPositive);
    expect(positiveValue).toHaveClass(tenorStyles.value, tenorStyles.valuePositive);
    expect(cssRuleBody("rowNegative")).toContain("--ib-down");
    expect(cssRuleBody("valueNegative")).toContain("--ib-down");
    expect(cssRuleBody("rowNote")).toContain("color: var(--ib-ink-secondary)");
    expect(cssRuleBody("rowPositive")).toContain("background: var(--ib-surface-muted)");
    expect(cssRuleBody("rowPositive")).not.toContain("--ib-up");
    expect(cssRuleBody("valuePositive")).toContain("color: var(--ib-ink-secondary)");
    expect(cssRuleBody("valuePositive")).not.toContain("--ib-up");
    expect(panel.querySelector("[style]")).toBeNull();
  });
});
