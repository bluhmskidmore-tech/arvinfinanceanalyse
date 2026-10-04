import { act, fireEvent, render, screen } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { BalanceZqtzMaturityStructure } from "../../../api/contracts";
import { MaturityDistributionChart } from "./MaturityDistributionChart";

const chart = vi.hoisted(() => ({ initialize: vi.fn() }));
vi.mock("../../../lib/echarts", () => ({
  default: function MockECharts({ onEvents }: { onEvents: { click: (event: { dataIndex: number }) => void } }) {
    useEffect(() => { chart.initialize(); }, []);
    return <button data-testid="maturity-chart" onClick={() => onEvents.click({ dataIndex: 1 })}>chart bar</button>;
  },
}));

const structure: BalanceZqtzMaturityStructure = {
  meta: {
    source_tables: [], source_scope: "synthetic", report_date: "2026-09-30", prior_report_date: null,
    currency_basis: "CNX", unit: "yuan", eligible_total: "300000000", covered_total: "300000000",
    unknown_total: "0", coverage_pct: "100", status: "supported", caveat: "",
  },
  buckets: [
    { maturity_bucket: "<=30d", bucket_label: "30天内", current_amount: "200000000", prior_amount: "0",
      delta_amount: "200000000", item_count: 1, share_pct: "66.67" },
    { maturity_bucket: ">5y", bucket_label: "5年以上", current_amount: "100000000", prior_amount: "0",
      delta_amount: "100000000", item_count: 1, share_pct: "33.33" },
  ],
};

function observeVisibility() {
  let callback!: IntersectionObserverCallback;
  const observe = vi.fn();
  const disconnect = vi.fn();
  vi.stubGlobal("IntersectionObserver", vi.fn(function Observer(onIntersect: IntersectionObserverCallback) {
    callback = onIntersect;
    return { observe, disconnect };
  }));
  const intersect = (visible: boolean) => act(() => callback([
    { isIntersecting: visible, intersectionRatio: visible ? 1 : 0 } as IntersectionObserverEntry,
  ], {} as IntersectionObserver));
  return { observe, disconnect, intersect };
}

describe("maturity chart visibility", () => {
  beforeEach(() => chart.initialize.mockClear());
  afterEach(() => vi.unstubAllGlobals());

  it("leaves a distant chart uninitialized and retains its first mount after entering the viewport margin", () => {
    const observer = observeVisibility();
    render(<MaturityDistributionChart structure={structure} onSelect={vi.fn()} />);
    expect(chart.initialize).not.toHaveBeenCalled();
    const placeholder = screen.getByTestId("balance-movement-maturity-chart-placeholder");
    expect(placeholder).toHaveClass("balance-movement-maturity-chart-placeholder");
    expect(observer.observe).toHaveBeenCalledWith(placeholder);
    observer.intersect(false);
    expect(chart.initialize).not.toHaveBeenCalled();

    observer.intersect(true);
    const mountedChart = screen.getByTestId("maturity-chart");
    expect(chart.initialize).toHaveBeenCalledTimes(1);
    expect(observer.disconnect).toHaveBeenCalled();
    observer.intersect(false);
    observer.intersect(true);
    expect(screen.getByTestId("maturity-chart")).toBe(mountedChart);
    expect(chart.initialize).toHaveBeenCalledTimes(1);
  });

  it("shows the chart immediately when IntersectionObserver is unavailable", () => {
    vi.stubGlobal("IntersectionObserver", undefined);
    render(<MaturityDistributionChart structure={structure} onSelect={vi.fn()} />);
    expect(screen.getByTestId("maturity-chart")).toBeInTheDocument();
    expect(screen.queryByTestId("balance-movement-maturity-chart-placeholder")).not.toBeInTheDocument();
    expect(chart.initialize).toHaveBeenCalledTimes(1);
  });

  it("keeps the original bucket click mapping after deferred initialization", () => {
    const observer = observeVisibility();
    const onSelect = vi.fn();
    render(<MaturityDistributionChart structure={structure} onSelect={onSelect} />);
    observer.intersect(true);
    fireEvent.click(screen.getByTestId("maturity-chart"));
    expect(onSelect).toHaveBeenCalledExactlyOnceWith(">5y");
  });
});
