import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { loadReactECharts } from "../features/product-category-pnl/pages/LazyReactECharts";
import { DerivedChartPanel } from "../features/product-category-pnl/pages/ProductCategoryComparisonCharts";
import type { EChartsOption } from "../lib/echarts";

vi.mock("../lib/echarts", () => ({
  default: ({ option }: { option?: unknown }) => (
    <div data-testid="product-category-echarts-stub">
      <span data-testid="product-category-echarts-option">
        {JSON.stringify(option ?? null)}
      </span>
    </div>
  ),
}));

type ObserverInit = IntersectionObserverInit | undefined;

class ControlledIntersectionObserver {
  static instances: ControlledIntersectionObserver[] = [];

  readonly targets: Element[] = [];
  disconnectCount = 0;

  constructor(
    readonly callback: IntersectionObserverCallback,
    readonly init: ObserverInit,
  ) {
    ControlledIntersectionObserver.instances.push(this);
  }

  observe(target: Element) {
    this.targets.push(target);
  }

  unobserve() {}

  disconnect() {
    this.disconnectCount += 1;
  }

  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }

  emit(isIntersecting: boolean) {
    act(() => {
      this.callback(
        this.targets.map(
          (target) => ({ isIntersecting, target }) as IntersectionObserverEntry,
        ),
        this as unknown as IntersectionObserver,
      );
    });
  }
}

function stubIntersectionObserver() {
  ControlledIntersectionObserver.instances = [];
  vi.stubGlobal("IntersectionObserver", ControlledIntersectionObserver);
  return ControlledIntersectionObserver;
}

const OPTION = {
  series: [{ type: "line", data: [1, 2, 3] }],
} as EChartsOption;

const PANEL_TEST_ID = "product-category-derived-chart-lazy-fixture";
const PLACEHOLDER_TEST_ID = `${PANEL_TEST_ID}-canvas-placeholder`;

function renderPanel() {
  return render(
    <DerivedChartPanel
      testId={PANEL_TEST_ID}
      title="TPL资产规模收益率走势图"
      description="跟踪TPL资产人民币规模、外币规模与综合收益率变化。"
      option={OPTION}
    />,
  );
}

// 图表包装器改成动态 import 后，首帧能否同步出图取决于模块缓存是否已就绪。
// 显式等一次预取，避免这些同步断言依赖微任务调度顺序。
beforeAll(async () => {
  await loadReactECharts();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("DerivedChartPanel 懒挂载", () => {
  it("renders the chart immediately when IntersectionObserver is unavailable", () => {
    vi.stubGlobal("IntersectionObserver", undefined);

    renderPanel();

    expect(screen.getByTestId(PANEL_TEST_ID)).toBeInTheDocument();
    expect(screen.getByTestId("product-category-echarts-stub")).toBeInTheDocument();
    expect(
      JSON.parse(
        screen.getByTestId("product-category-echarts-option").textContent ?? "null",
      ),
    ).toMatchObject({ series: [{ type: "line" }] });
    expect(screen.queryByTestId(PLACEHOLDER_TEST_ID)).not.toBeInTheDocument();
  });

  it("keeps the card frame but defers the chart while the panel stays out of view", () => {
    const observer = stubIntersectionObserver();

    renderPanel();

    expect(screen.getByTestId(PANEL_TEST_ID)).toBeInTheDocument();
    expect(screen.getByText("TPL资产规模收益率走势图")).toBeInTheDocument();
    expect(
      screen.getByText(
        "跟踪TPL资产人民币规模、外币规模与综合收益率变化。",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("product-category-echarts-stub")).not.toBeInTheDocument();

    const placeholder = screen.getByTestId(PLACEHOLDER_TEST_ID);
    expect(placeholder).toHaveClass("product-category-derived-chart__canvas");

    const instance = observer.instances.at(-1);
    expect(instance?.targets).toContain(placeholder);
    expect(instance?.init?.rootMargin).toBe("300px 0px");
  });

  it("mounts the chart once it intersects and keeps it mounted afterwards", () => {
    const observer = stubIntersectionObserver();

    renderPanel();
    const instance = observer.instances.at(-1);
    expect(instance).toBeDefined();

    instance!.emit(false);
    expect(screen.queryByTestId("product-category-echarts-stub")).not.toBeInTheDocument();

    instance!.emit(true);
    expect(screen.getByTestId("product-category-echarts-stub")).toBeInTheDocument();
    expect(screen.queryByTestId(PLACEHOLDER_TEST_ID)).not.toBeInTheDocument();
    expect(instance!.disconnectCount).toBeGreaterThan(0);

    instance!.emit(false);
    expect(screen.getByTestId("product-category-echarts-stub")).toBeInTheDocument();
  });

  it("renders nothing when the option is missing", () => {
    stubIntersectionObserver();

    const { container } = render(
      <DerivedChartPanel
        testId={PANEL_TEST_ID}
        title="TPL资产规模收益率走势图"
        description="跟踪TPL资产人民币规模、外币规模与综合收益率变化。"
        option={null}
      />,
    );

    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByTestId(PLACEHOLDER_TEST_ID)).not.toBeInTheDocument();
  });
});

describe("LazyReactECharts 按需下载", () => {
  afterEach(() => {
    vi.doUnmock("../lib/echarts");
    vi.resetModules();
  });

  it("holds a same-class placeholder until the shared echarts module resolves", async () => {
    vi.resetModules();
    let releaseSharedModule!: () => void;
    const sharedModuleGate = new Promise<void>((resolve) => {
      releaseSharedModule = resolve;
    });
    vi.doMock("../lib/echarts", async () => {
      await sharedModuleGate;
      return {
        default: () => <div data-testid="product-category-echarts-stub" />,
      };
    });

    const { LazyReactECharts } = await import(
      "../features/product-category-pnl/pages/LazyReactECharts"
    );

    const { container } = render(
      <LazyReactECharts
        option={OPTION}
        className="product-category-derived-chart__canvas"
      />,
    );

    expect(
      container.querySelector(".product-category-derived-chart__canvas"),
    ).not.toBeNull();
    expect(
      screen.queryByTestId("product-category-echarts-stub"),
    ).not.toBeInTheDocument();

    releaseSharedModule();

    expect(
      await screen.findByTestId("product-category-echarts-stub"),
    ).toBeInTheDocument();
  });
});
