import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { HomeResearchReportRow } from "./dashboardHomeBodyView";
import { DashboardHomeOptionTwoResearchList } from "./DashboardHomeOptionTwoResearchList";

function report(
  id: string,
  title: string,
  overrides: Partial<HomeResearchReportRow> = {},
): HomeResearchReportRow {
  return {
    id,
    title,
    category: "fixed_income",
    publishedAt: "2026-07-15",
    source: "tushare_research",
    institution: "中信固收",
    summary: "—",
    link: null,
    isNewsFallback: false,
    ...overrides,
  };
}

describe("DashboardHomeOptionTwoResearchList", () => {
  it("cleans only governed filename boundaries and keeps raw titles as metadata", () => {
    const rawTitle = "中信固收_利率债周报_20260715.PDF";
    render(
      <DashboardHomeOptionTwoResearchList
        reports={[
          report("managed", ` ${rawTitle} `, {
            summary: `${rawTitle}：核心观点`,
          }),
          report("unmanaged-prefix", "中信固收研究_信用债周报_20260714.pdf", {
            summary: "中信固收研究_信用债周报_20260714.pdf",
          }),
          report("empty-clean", "华泰固收_.pdf", {
            institution: "华泰固收",
            source: "华泰",
          }),
          report("source-prefix", "来源甲_国债曲线_20260712.pDf", {
            institution: "—",
            source: "来源甲",
            summary: "—",
          }),
          report("internal-pdf", "普通固收观点.PDF附注", {
            institution: "tushare_research",
            source: "tushare_research",
            summary: "普通固收观点.PDF附注：",
          }),
        ]}
        state={{ kind: "ready", label: "已接入" }}
      />,
    );

    const rows = screen.getAllByTestId("dashboard-home-research-row");
    const cells = rows.map((row) => within(row).getAllByRole("cell"));
    expect(cells.map((row) => row[0].textContent)).toEqual([
      "利率债周报",
      "中信固收研究_信用债周报",
      "华泰固收_.pdf",
      "国债曲线",
      "普通固收观点.PDF附注",
    ]);
    expect(cells[0][0]).toHaveAttribute("aria-label", rawTitle);
    expect(cells[0][0]).toHaveAttribute("title", rawTitle);
    expect(cells[0][1]).toHaveTextContent("核心观点");
    expect(cells[1][1]).toHaveTextContent("—");
    expect(cells[2][1]).toHaveTextContent("—");
    expect(cells[3][3]).toHaveTextContent("来源甲");
    expect(cells[4][3]).toHaveTextContent("—");
  });

  it("uses validated HTTP links and derives PDF status from the URL pathname", () => {
    render(
      <DashboardHomeOptionTwoResearchList
        reports={[
          report("pdf", "利率债PDF报告", {
            link: "https://example.com/path/report.PDF?download=1#page=2",
          }),
          report("html", "信用债网页报告", {
            link: "http://example.com/path/report?format=pdf",
          }),
          report("script", "非法链接", { link: "javascript:alert(1)" }),
          report("malformed", "格式错误链接", { link: "not a url" }),
        ]}
        state={{ kind: "ready", label: "已接入" }}
      />,
    );

    const rows = screen.getAllByTestId("dashboard-home-research-row");
    const pdfLink = within(rows[0]).getByRole("link", {
      name: "打开PDF原文：利率债PDF报告",
    });
    const htmlLink = within(rows[1]).getByRole("link", {
      name: "打开原文：信用债网页报告",
    });
    expect(pdfLink).toHaveTextContent("PDF");
    expect(pdfLink).toHaveAttribute(
      "href",
      "https://example.com/path/report.PDF?download=1#page=2",
    );
    expect(pdfLink).toHaveAttribute("target", "_blank");
    expect(pdfLink).toHaveAttribute("rel", "noreferrer");
    expect(htmlLink).toHaveTextContent("原文");
    expect(within(rows[2]).queryByRole("link")).not.toBeInTheDocument();
    expect(within(rows[3]).queryByRole("link")).not.toBeInTheDocument();
  });

  it("keeps news fallback titles intact and makes the fallback explicit without a report date", () => {
    const fallbackTitle = "宏观新闻_央行公开市场_20260715.PDF";
    render(
      <DashboardHomeOptionTwoResearchList
        reports={[
          report("news", fallbackTitle, {
            institution: "—",
            source: "Choice新闻",
            summary: "Choice新闻 · 今日更新",
            isNewsFallback: true,
          }),
        ]}
        state={{ kind: "partial", label: "研报源暂缺 · 新闻补位" }}
      />,
    );

    const panel = screen.getByTestId("dashboard-home-research-reports");
    expect(within(panel).getByText("研报源暂缺 · 新闻补位")).toBeInTheDocument();
    const row = within(panel).getByTestId("dashboard-home-research-row");
    const cells = within(row).getAllByRole("cell");
    expect(cells[0]).toHaveTextContent(fallbackTitle);
    expect(cells[0]).toHaveAttribute("aria-label", fallbackTitle);
    expect(cells[1]).toHaveTextContent("—");
    expect(cells[2]).toHaveTextContent("—");
    expect(row.querySelector("time")).toBeNull();
  });

  it("renders the supplied state instead of report rows when the list is empty", () => {
    render(
      <DashboardHomeOptionTwoResearchList
        reports={[]}
        state={{ kind: "loading", label: "研究报告加载中" }}
      />,
    );

    const panel = screen.getByTestId("dashboard-home-research-reports");
    expect(within(panel).getByRole("status")).toHaveTextContent("研究报告加载中");
    expect(
      within(panel).queryByTestId("dashboard-home-research-row"),
    ).not.toBeInTheDocument();
  });
});
