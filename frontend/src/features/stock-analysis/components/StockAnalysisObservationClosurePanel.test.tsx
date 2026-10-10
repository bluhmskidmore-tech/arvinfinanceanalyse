import { render, screen } from "@testing-library/react";

import type { StockObservationClosureSummary } from "../lib/stockAnalysisPageModel";
import { StockAnalysisObservationClosurePanel } from "./StockAnalysisObservationClosurePanel";

function buildSummary(
  overrides: Partial<StockObservationClosureSummary> = {},
): StockObservationClosureSummary {
  return {
    formalUseAllowed: false,
    approvalStatus: "gap_or_observational",
    approvalLabel: "观测缺口页",
    endpointTotal: 4,
    endpointLoadedCount: 4,
    endpointErrorCount: 0,
    metaMissingCount: 0,
    unresolvedReasons: [
      {
        key: "main:diagnostic",
        endpointId: "main",
        endpointLabel: "主策略",
        kind: "diagnostic",
        fieldPath: "main.diagnostics[0]",
        displayText: "主策略存在诊断项",
        tone: "warning",
      },
    ],
    nextEvidenceActions: [
      {
        key: "action:main",
        source: "主策略",
        actionText: "复核主策略诊断项",
        fieldPath: "main.diagnostics[0]",
      },
    ],
    headline: "证据读取覆盖 4/4",
    detail: "正式用途：否 · 治理状态：gap_or_observational · 待复核项 1",
    tone: "warning",
    ...overrides,
  };
}

describe("StockAnalysisObservationClosurePanel", () => {
  it.each([
    [
      "diagnostic_only",
      buildSummary(),
      "仅诊断",
      "观测边界：当前只允许诊断与复核，不能当作正式结论或执行依据。",
      "warning",
    ],
    [
      "armed_not_promoted",
      buildSummary({
        unresolvedReasons: [],
        nextEvidenceActions: [],
        detail: "正式用途：否 · 治理状态：gap_or_observational · 待复核项 0",
      }),
      "已装填未推广",
      "观测边界：证据链已接通，但尚未获得正式用途授权，仍只作只读观察。",
      "warning",
    ],
    [
      "promoted_active",
      buildSummary({
        formalUseAllowed: true,
        unresolvedReasons: [],
        nextEvidenceActions: [],
        detail: "正式用途：是 · 治理状态：approved · 待复核项 0",
      }),
      "已推广生效",
      "观测边界：正式用途已放行，但页面仍只读呈现，不自动下达执行动作。",
      "positive",
    ],
    [
      "conflict",
      buildSummary({
        endpointErrorCount: 1,
        unresolvedReasons: [
          {
            key: "main:query-error",
            endpointId: "main",
            endpointLabel: "主策略",
            kind: "query-error",
            fieldPath: "main.queryState",
            displayText: "主策略读取失败",
            tone: "negative",
          },
        ],
        detail: "正式用途：否 · 治理状态：gap_or_observational · 待复核项 1",
      }),
      "状态冲突",
      "观测边界：读取失败或证据互相冲突，先修复冲突项，再谈推广或执行。",
      "negative",
    ],
    [
      "unavailable",
      buildSummary({
        endpointLoadedCount: 0,
        unresolvedReasons: [],
        nextEvidenceActions: [],
        detail: "正式用途：否 · 治理状态：gap_or_observational · 待复核项 0",
      }),
      "当前不可用",
      "观测边界：接口未接通或全链路未返回，当前规则状态不可确认。",
      "warning",
    ],
  ])(
    "renders current-rule state %s",
    (_code, summary, label, boundary, tone) => {
      render(<StockAnalysisObservationClosurePanel closureSummary={summary} />);

      const code = screen.getByTestId("stock-analysis-current-rule-state-code");
      const detail = screen.getByTestId("stock-analysis-current-rule-state-detail");

      expect(code).toHaveTextContent(_code);
      expect(code).toHaveAttribute("data-tone", tone);
      expect(screen.getByText(label)).toHaveAttribute("data-tone", tone);
      expect(detail).toHaveTextContent(boundary);
      expect(screen.getByTestId("stock-analysis-observation-closure-panel")).toHaveTextContent(
        `正式用途：${summary.formalUseAllowed ? "是" : "否"}`,
      );
    },
  );
});
