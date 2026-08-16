import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { KpiMetricWithValue, KpiOwner } from "../api/contracts";
import {
  BATCH_PASTE_MAX_ROWS,
  BatchPasteModal,
} from "../features/kpi-performance/components/BatchPasteModal";
import { MetricTable } from "../features/kpi-performance/components/MetricTable";
import { OwnerList } from "../features/kpi-performance/components/OwnerList";

function Wrapper({ children }: { children: ReactNode }) {
  return (
    <ApiClientProvider client={createApiClient({ mode: "mock" })}>{children}</ApiClientProvider>
  );
}

function makeMetric(partial: Partial<KpiMetricWithValue> = {}): KpiMetricWithValue {
  return {
    metric_id: 1,
    metric_code: "M1",
    owner_id: 1,
    year: 2026,
    major_category: "经营效益类",
    indicator_category: "效益类",
    metric_name: "营业收入",
    target_value: "100",
    score_weight: "10",
    scoring_rule_type: "LINEAR_RATIO",
    data_source_type: "MANUAL",
    is_active: true,
    actual_value: "92",
    ...partial,
  };
}

function makeOwner(partial: Partial<KpiOwner> = {}): KpiOwner {
  return {
    owner_id: 1,
    owner_name: "固定收益部",
    org_unit: "金融市场总部",
    person_name: null,
    year: 2026,
    scope_type: "department",
    scope_key: null,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...partial,
  };
}

describe("MetricTable accessibility and copy", () => {
  it("names the inline save/cancel/metric-settings icon buttons and drops the METRICS eyebrow", async () => {
    const user = userEvent.setup();
    render(
      <Wrapper>
        <MetricTable
          metrics={[makeMetric()]}
          valueAsOfDate="2026-08-14"
          onEditMetricDef={vi.fn()}
        />
      </Wrapper>,
    );

    // 英文眉标已删除，标题保留。
    expect(screen.queryByText("METRICS")).not.toBeInTheDocument();
    expect(screen.getByText("指标明细")).toBeInTheDocument();

    // 指标设置图标按钮具备可访问名称。
    expect(screen.getByRole("button", { name: "设置指标" })).toBeInTheDocument();

    // 进入行内编辑后，保存/取消图标按钮具备可访问名称。
    await user.click(screen.getByText("100.00"));
    expect(screen.getByRole("button", { name: "保存编辑" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "取消编辑" })).toBeInTheDocument();
  });
});

describe("OwnerList copy", () => {
  it("drops the OWNER eyebrow while keeping the panel title", () => {
    render(
      <OwnerList owners={[makeOwner()]} selectedOwnerId={null} onSelect={vi.fn()} />,
    );

    expect(screen.queryByText("OWNER")).not.toBeInTheDocument();
    expect(screen.getByText("考核部室")).toBeInTheDocument();
  });
});

describe("BatchPasteModal import guardrails", () => {
  function renderModal(metrics: KpiMetricWithValue[]) {
    return render(
      <Wrapper>
        <BatchPasteModal
          open
          onClose={vi.fn()}
          owner={makeOwner()}
          asOfDate="2026-08-14"
          metrics={metrics}
          onSuccess={vi.fn()}
        />
      </Wrapper>,
    );
  }

  it("refuses to parse when the pasted rows exceed the max import limit", async () => {
    const user = userEvent.setup();
    renderModal([makeMetric()]);

    const overLimit = Array.from(
      { length: BATCH_PASTE_MAX_ROWS + 1 },
      (_, i) => `M1\t${i}`,
    ).join("\n");
    const textarea = screen.getByPlaceholderText("从 Excel 粘贴…");
    // userEvent.type 逐字符输入过慢，直接 paste 大文本。
    await user.click(textarea);
    await user.paste(overLimit);
    // antd 会在两个汉字的按钮文案中间插空格，accessible name 为「解 析」。
    await user.click(screen.getByRole("button", { name: /解\s*析/ }));

    expect(screen.getByText("超出导入行数上限")).toBeInTheDocument();
    expect(
      screen.getByText(
        `共 ${BATCH_PASTE_MAX_ROWS + 1} 行，超出单次最大导入 ${BATCH_PASTE_MAX_ROWS} 行，请分批粘贴导入。`,
      ),
    ).toBeInTheDocument();
    // 超限时不渲染预览表。
    expect(screen.queryByText("预览")).not.toBeInTheDocument();
  });

  it("paginates the preview table instead of rendering every parsed row at once", async () => {
    const user = userEvent.setup();
    const metrics = Array.from({ length: 60 }, (_, i) =>
      makeMetric({
        metric_id: i + 1,
        metric_code: `M${i + 1}`,
        metric_name: `指标 ${i + 1}`,
      }),
    );
    renderModal(metrics);

    const pasted = Array.from({ length: 60 }, (_, i) => `M${i + 1}\t${i + 1}`).join("\n");
    const textarea = screen.getByPlaceholderText("从 Excel 粘贴…");
    await user.click(textarea);
    await user.paste(pasted);
    await user.click(screen.getByRole("button", { name: /解\s*析/ }));

    expect(screen.getByText("预览")).toBeInTheDocument();
    expect(screen.getByText("有效 60")).toBeInTheDocument();
    // 分页器出现（pageSize 50），首屏只渲染第一页而非全部 60 行。
    expect(document.querySelector(".ant-pagination")).not.toBeNull();
    expect(screen.getByText("指标 1")).toBeInTheDocument();
    expect(screen.queryByText("指标 60")).not.toBeInTheDocument();
  });
});
