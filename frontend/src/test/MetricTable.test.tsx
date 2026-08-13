import { useState, type ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { KpiMetricWithValue } from "../api/contracts";
import { MetricTable } from "../features/kpi-performance/components/MetricTable";
import { EM_DASH } from "../utils/format";

function renderTable(client: ApiClient, metrics: KpiMetricWithValue[]) {
  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(() => new QueryClient());
    return (
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>{children}</ApiClientProvider>
      </QueryClientProvider>
    );
  }

  return render(
    <Wrapper>
      <MetricTable metrics={metrics} valueAsOfDate="2025-12-31" />
    </Wrapper>,
  );
}

function metricFixture(partial: Partial<KpiMetricWithValue> = {}): KpiMetricWithValue {
  return {
    metric_id: 1,
    metric_code: "M-001",
    owner_id: 10,
    year: 2025,
    major_category: "经营类",
    metric_name: "净利润完成率",
    target_value: "100",
    score_weight: "20",
    scoring_rule_type: "MANUAL",
    data_source_type: "MANUAL",
    is_active: true,
    actual_value: null,
    progress_pct: null,
    score_value: null,
    ...partial,
  };
}

describe("kpi MetricTable missing values and local summary", () => {
  it("renders missing values as EM_DASH and marks the local summary row as unofficial", () => {
    renderTable(createApiClient({ mode: "mock" }), [metricFixture()]);

    expect(screen.getAllByText(EM_DASH).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("-")).not.toBeInTheDocument();

    expect(screen.getByText("合计（前端本地加总·非官方口径）")).toBeInTheDocument();
  });
});
