import { fireEvent, render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { PnlByBusinessInsightsLeadershipModel } from "./pnlByBusinessInsightsModel";
import { PnlByBusinessInsightsLeadershipPanel } from "./PnlByBusinessInsightsLeadershipPanel";

const readyModel: PnlByBusinessInsightsLeadershipModel = {
  status: "ready",
  reason: "正式口径已匹配；上游存在质量提示",
  qualityWarning: true,
  resolvedDate: "2026-06-30",
  traceId: "tr_test",
  items: [
    { key: "concentration", label: "结构集中度", value: "HHI 13.42% · Top3 50.50%", detail: "口径", rowKey: null },
    { key: "negative_ftp", label: "持续负 FTP", value: "同业存单 91.67%", detail: "连续9个月", rowKey: "cd" },
    { key: "share_drift", label: "日均份额同比漂移", value: "公募基金 -3.52pp", detail: "同期间", rowKey: "fund" },
    { key: "scale_yield", label: "规模—FTP后收益", value: "政策性金融债", detail: "相对分类", rowKey: "policy" },
  ],
};

describe("PnlByBusinessInsightsLeadershipPanel", () => {
  it("renders four approved facts and reuses the parent-row selection callback", () => {
    const onSelectRow = vi.fn();
    const { getByTestId } = render(
      <MemoryRouter>
        <PnlByBusinessInsightsLeadershipPanel
          model={readyModel}
          year={2026}
          asOfDate="2026-06-30"
          onSelectRow={onSelectRow}
        />
      </MemoryRouter>,
    );

    expect(getByTestId("pnl-by-business-insights-leadership-panel")).toHaveTextContent("正式结构分析");
    expect(getByTestId("pnl-by-business-insights-leadership-panel")).toHaveTextContent("HHI 13.42%");
    expect(getByTestId("pnl-by-business-insights-leadership-panel")).toHaveTextContent("质量提示");
    fireEvent.click(getByTestId("pnl-by-business-insights-leadership-negative_ftp"));
    expect(onSelectRow).toHaveBeenCalledWith("cd");
    expect(getByTestId("pnl-by-business-insights-leadership-detail-link")).toHaveAttribute(
      "href",
      "/pnl-by-business-insights?year=2026&as_of_date=2026-06-30",
    );
  });

  it("shows an explicit review state without fabricating metric values", () => {
    const { getByTestId, queryByText } = render(
      <MemoryRouter>
        <PnlByBusinessInsightsLeadershipPanel
          model={{
            status: "review",
            reason: "结构分析截止日不一致，需复核后使用",
            qualityWarning: false,
            resolvedDate: "2026-05-31",
            traceId: null,
            items: [],
          }}
          year={2026}
          asOfDate="2026-06-30"
          onSelectRow={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(getByTestId("pnl-by-business-insights-leadership-review")).toHaveTextContent("结构分析待复核");
    expect(queryByText("0.00%")).not.toBeInTheDocument();
  });
});
