import { readFileSync } from "node:fs";
import path from "node:path";

import { render, screen, within } from "@testing-library/react";

import { StateSurface, StateSurfaceQuotaProvider, type SurfaceStatus } from "./StateSurface";
import { STATE_SURFACE_DEDUPE_LIMIT, useStateSurfaceQuota } from "./stateSurfaceQuota";
import { SURFACE_STATUS_LABEL } from "./statusBridge";

const cssPath = path.join(import.meta.dirname, "StateSurface.module.css");

describe("StateSurface", () => {
  it("renders children as-is for status=ready", () => {
    render(
      <StateSurface status="ready" testId="surface">
        <div>real content</div>
      </StateSurface>,
    );
    expect(screen.getByText("real content")).toBeInTheDocument();
  });

  it("renders a backdrop skeleton (not children) for status=loading", () => {
    render(
      <StateSurface status="loading" testId="surface">
        <div>should not render while loading</div>
      </StateSurface>,
    );
    expect(screen.queryByText("should not render while loading")).not.toBeInTheDocument();
    expect(screen.getByText("正在载入")).toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("applies the default 120px anti-reflow floor while loading", () => {
    render(<StateSurface status="loading" testId="surface" />);
    expect(screen.getByTestId("surface")).toHaveStyle({ "--ss-min-height": "120px" } as never);
  });

  it("applies a custom numeric minHeight while loading", () => {
    render(<StateSurface status="loading" testId="surface" minHeight={240} />);
    expect(screen.getByTestId("surface")).toHaveStyle({ "--ss-min-height": "240px" } as never);
  });

  it('resolves minHeight="match" to a stretch-aware max() expression', () => {
    render(<StateSurface status="loading" testId="surface" minHeight="match" />);
    expect(screen.getByTestId("surface")).toHaveStyle({
      "--ss-min-height": "max(120px, 100%)",
    } as never);
  });

  it("shrinks for status=empty regardless of the minHeight prop (opposite of loading)", () => {
    render(<StateSurface status="empty" testId="surface" minHeight={999} />);
    const surface = screen.getByTestId("surface");
    // Empty must never adopt the anti-reflow floor — it deliberately ignores minHeight.
    expect(surface.style.getPropertyValue("--ss-min-height")).toBe("");
    expect(screen.getByText("暂无数据")).toBeInTheDocument();
  });

  it("renders empty message plus reason", () => {
    render(<StateSurface status="empty" testId="surface" reason="本期未产生业务" />);
    expect(screen.getByText("本期未产生业务", { exact: false })).toBeInTheDocument();
  });

  it("does not render children for status=empty", () => {
    render(
      <StateSurface status="empty" testId="surface">
        <div>hidden content</div>
      </StateSurface>,
    );
    expect(screen.queryByText("hidden content")).not.toBeInTheDocument();
  });

  it("renders a standalone alert backdrop for status=error without children", () => {
    render(<StateSurface status="error" testId="surface" />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("数据加载失败")).toBeInTheDocument();
    expect(screen.getByTestId("surface")).toHaveStyle({ "--ss-min-height": "120px" } as never);
  });

  it("renders an inline status line alongside existing content for status=error with children", () => {
    render(
      <StateSurface status="error" testId="surface">
        <div>stale-but-visible content</div>
      </StateSurface>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("stale-but-visible content")).toBeInTheDocument();
  });

  it("renders stale/partial as an inline status line without masking children", () => {
    render(
      <StateSurface status="stale" testId="surface-stale">
        <div>still-rendered stale content</div>
      </StateSurface>,
    );
    expect(screen.getByText("数据可能已过期")).toBeInTheDocument();
    expect(screen.getByText("still-rendered stale content")).toBeInTheDocument();

    render(
      <StateSurface status="partial" testId="surface-partial">
        <div>still-rendered partial content</div>
      </StateSurface>,
    );
    expect(screen.getByText("部分数据不可用")).toBeInTheDocument();
    expect(screen.getByText("still-rendered partial content")).toBeInTheDocument();
  });

  it("carries status-specific semantics on the status dot (never a decorative dot)", () => {
    const statuses: Array<["loading" | "empty" | "error" | "stale" | "partial", string]> = [
      ["loading", "loading"],
      ["empty", "empty"],
      ["error", "error"],
      ["stale", "stale"],
      ["partial", "partial"],
    ];
    for (const [status, expected] of statuses) {
      const { container, unmount } = render(<StateSurface status={status} />);
      const dot = container.querySelector('[data-role="status-dot"]');
      expect(dot).not.toBeNull();
      expect(dot).toHaveAttribute("data-status", expected);
      unmount();
    }
  });

  it("lets custom message/reason override the defaults", () => {
    render(<StateSurface status="error" testId="surface" message="自定义标题" reason="自定义原因" />);
    expect(screen.getByText("自定义标题")).toBeInTheDocument();
    expect(screen.getByText("自定义原因", { exact: false })).toBeInTheDocument();
  });

  it("does not crash and skips dedupe bookkeeping when no provider is mounted", () => {
    expect(() =>
      render(<StateSurface status="empty" testId="surface" dedupeKey="orphan-key" />),
    ).not.toThrow();
    expect(screen.getByTestId("surface")).toBeInTheDocument();
  });
});

describe("StateSurface dedupe quota", () => {
  function QuotaReadout({ dedupeKey }: { dedupeKey: string }) {
    const quota = useStateSurfaceQuota();
    return <output data-testid="quota-readout">{quota?.counts[dedupeKey] ?? 0}</output>;
  }

  it("counts simultaneous instances of the same dedupeKey", () => {
    render(
      <StateSurfaceQuotaProvider>
        <StateSurface status="stale" dedupeKey="report-date" testId="a">
          <div>a</div>
        </StateSurface>
        <StateSurface status="stale" dedupeKey="report-date" testId="b">
          <div>b</div>
        </StateSurface>
        <QuotaReadout dedupeKey="report-date" />
      </StateSurfaceQuotaProvider>,
    );
    expect(screen.getByTestId("quota-readout")).toHaveTextContent("2");
  });

  it("warns in dev when a dedupeKey exceeds the §6 quota of two", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(
      <StateSurfaceQuotaProvider>
        <StateSurface status="stale" dedupeKey="report-date" testId="a">
          <div>a</div>
        </StateSurface>
        <StateSurface status="stale" dedupeKey="report-date" testId="b">
          <div>b</div>
        </StateSurface>
        <StateSurface status="stale" dedupeKey="report-date" testId="c">
          <div>c</div>
        </StateSurface>
      </StateSurfaceQuotaProvider>,
    );
    expect(warnSpy).toHaveBeenCalledTimes(1);
    const [warningMessage] = warnSpy.mock.calls[0] as [string];
    expect(warningMessage).toContain('dedupeKey "report-date"');
    expect(warningMessage).toContain("第 3 次");
    expect(STATE_SURFACE_DEDUPE_LIMIT).toBe(2);
  });

  it("decrements the count when an instance unmounts", () => {
    function Harness({ showThird }: { showThird: boolean }) {
      return (
        <StateSurfaceQuotaProvider>
          <StateSurface status="stale" dedupeKey="report-date" testId="a" />
          <StateSurface status="stale" dedupeKey="report-date" testId="b" />
          {showThird ? <StateSurface status="stale" dedupeKey="report-date" testId="c" /> : null}
          <QuotaReadout dedupeKey="report-date" />
        </StateSurfaceQuotaProvider>
      );
    }
    const { rerender } = render(<Harness showThird />);
    expect(screen.getByTestId("quota-readout")).toHaveTextContent("3");
    rerender(<Harness showThird={false} />);
    expect(screen.getByTestId("quota-readout")).toHaveTextContent("2");
  });

  it("does not warn when different dedupeKeys are each used twice", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(
      <StateSurfaceQuotaProvider>
        <StateSurface status="stale" dedupeKey="key-a" testId="a1" />
        <StateSurface status="stale" dedupeKey="key-a" testId="a2" />
        <StateSurface status="stale" dedupeKey="key-b" testId="b1" />
        <StateSurface status="stale" dedupeKey="key-b" testId="b2" />
      </StateSurfaceQuotaProvider>,
    );
    expect(warnSpy).not.toHaveBeenCalled();
  });
});

describe("StateSurface §5/§7 shape guards", () => {
  it("does not join message and reason with a · separator", () => {
    // 文案自带 `·` 时组件再插一个就突破了 §7 的单行一个配额；reason 独占次行。
    render(<StateSurface status="empty" testId="surface" reason="本期未产生业务" />);
    expect(screen.getByTestId("surface").textContent).not.toContain("·");
  });

  it("does not join the status line reason with a · separator either", () => {
    render(
      <StateSurface status="stale" testId="surface" reason="回退到 2026-07-31">
        <div>content</div>
      </StateSurface>,
    );
    expect(screen.getByTestId("surface").textContent).not.toContain("·");
  });

  it("keeps the empty box self-sized: a min-height floor but no hard max-height cap", () => {
    const css = readFileSync(cssPath, "utf8");
    const shrinkBox = css.match(/\.shrinkBox\s*\{([^}]*)\}/)?.[1] ?? "";
    expect(shrinkBox).toMatch(/min-height:\s*\d+px/);
    // 封顶会让长原因文案在 overflow: visible 下溢出边框（§5 要求收缩到「消息框自身高度」）。
    expect(shrinkBox).not.toContain("max-height");
  });
});

describe("StateSurface density (childless error/stale/partial)", () => {
  const childlessStatuses: Array<Extract<SurfaceStatus, "error" | "stale" | "partial">> = [
    "error",
    "stale",
    "partial",
  ];

  it.each(childlessStatuses)(
    'defaults to the "roomy" 120px backdrop for childless status=%s',
    (status) => {
      render(<StateSurface status={status} testId="surface" />);
      const surface = screen.getByTestId("surface");
      expect(surface).toHaveStyle({ "--ss-min-height": "120px" } as never);
      // Roomy wraps the status line in a plain backdrop div: the role lives on
      // the inner status line, not on the testId'd backdrop itself.
      expect(surface).not.toHaveAttribute("role");
    },
  );

  it.each(childlessStatuses)(
    'density="compact" drops the 120px floor for childless status=%s',
    (status) => {
      render(<StateSurface status={status} testId="surface" density="compact" />);
      const surface = screen.getByTestId("surface");
      // No forced anti-reflow floor: compact must not carry --ss-min-height at all.
      expect(surface.style.getPropertyValue("--ss-min-height")).toBe("");
      // Compact *is* the status line itself (no backdrop wrapper), so the
      // role attribute lands directly on the testId'd element.
      expect(surface).toHaveAttribute("role", status === "error" ? "alert" : "status");
      expect(screen.getByRole(status === "error" ? "alert" : "status")).toBe(surface);
    },
  );

  it('density="compact" still shows the resolved message and reason', () => {
    render(
      <StateSurface
        status="error"
        testId="surface"
        density="compact"
        reason="回退到 2026-07-31"
      />,
    );
    expect(screen.getByText("数据加载失败")).toBeInTheDocument();
    expect(screen.getByText("回退到 2026-07-31")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it.each(childlessStatuses)(
    'density="compact" keeps the action slot and status semantics for childless status=%s',
    (status) => {
      const { container } = render(
        <StateSurface
          status={status}
          testId="surface"
          density="compact"
          actions={<button type="button">重试</button>}
        />,
      );
      const surface = screen.getByTestId("surface");
      expect(container.children).toHaveLength(1);
      expect(container.firstElementChild).toBe(surface);
      expect(surface).not.toHaveAttribute("role");
      expect(surface.style.getPropertyValue("--ss-min-height")).toBe("");
      const semanticRegion = within(surface).getByRole(status === "error" ? "alert" : "status");
      const action = within(surface).getByRole("button", { name: "重试" });
      expect(semanticRegion).toBeInTheDocument();
      expect(action).toBeInTheDocument();
      expect(semanticRegion).not.toContainElement(action);
    },
  );

  it('density="compact" is a no-op for status=loading (anti-reflow floor never degrades)', () => {
    render(<StateSurface status="loading" testId="surface" density="compact" />);
    const surface = screen.getByTestId("surface");
    expect(surface).toHaveAttribute("role", "status");
    expect(surface).toHaveAttribute("aria-live", "polite");
    expect(surface).toHaveStyle({ "--ss-min-height": "120px" } as never);
    expect(screen.getByText("正在载入")).toBeInTheDocument();
  });

  it('density="compact" is a no-op for status=empty (shrink behavior never degrades)', () => {
    render(<StateSurface status="empty" testId="surface" density="compact" />);
    const surface = screen.getByTestId("surface");
    expect(surface.style.getPropertyValue("--ss-min-height")).toBe("");
    expect(screen.getByText("暂无数据")).toBeInTheDocument();
  });

  it('density="compact" is a no-op when children are present (already inline, never masked)', () => {
    render(
      <StateSurface status="error" testId="surface" density="compact">
        <div>still-rendered content</div>
      </StateSurface>,
    );
    expect(screen.getByText("still-rendered content")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
    // Still the "wrap" shape (statusLine + content), not the bare compact line,
    // because the compact/roomy distinction only matters when there's no content.
    const surface = screen.getByTestId("surface");
    expect(surface).not.toHaveAttribute("role");
  });
});

describe("StateSurface default message single-source (statusBridge.SURFACE_STATUS_LABEL)", () => {
  it("renders exactly the word list's text for every non-ready status, with no local duplicate", () => {
    const nonReady: Array<Extract<SurfaceStatus, "loading" | "empty" | "error" | "stale" | "partial">> = [
      "loading",
      "empty",
      "error",
      "stale",
      "partial",
    ];
    for (const status of nonReady) {
      const expected = SURFACE_STATUS_LABEL[status];
      expect(expected).toBeTruthy();
      const { unmount } = render(<StateSurface status={status} testId="surface" />);
      expect(screen.getByText(expected as string)).toBeInTheDocument();
      unmount();
    }
  });

  it("has no default message for status=ready", () => {
    expect(SURFACE_STATUS_LABEL.ready).toBeUndefined();
  });

  it("lets an explicit message override the word list's default", () => {
    render(<StateSurface status="empty" testId="surface" message="本期未产生业务" />);
    expect(screen.getByText("本期未产生业务")).toBeInTheDocument();
    expect(screen.queryByText(SURFACE_STATUS_LABEL.empty as string)).not.toBeInTheDocument();
  });
});

describe("StateSurface 无内容态的出口动作", () => {
  it("renders actions in the empty box, while children stay dropped", () => {
    // actions 与 children 是两个槽位：children 恒指「数据」，空态没有数据；
    // 出口动作走 actions。合并成一个槽位会让同一个入口随 status 变含义。
    const { container } = render(
      <StateSurface status="empty" testId="surface" actions={<button type="button">重新生成</button>}>
        <div>hidden content</div>
      </StateSurface>,
    );
    const surface = screen.getByTestId("surface");
    expect(container.children).toHaveLength(1);
    expect(container.firstElementChild).toBe(surface);
    expect(surface).not.toHaveAttribute("role");
    const semanticRegion = within(surface).getByRole("status");
    const action = within(surface).getByRole("button", { name: "重新生成" });
    expect(semanticRegion).toBeInTheDocument();
    expect(action).toBeInTheDocument();
    expect(semanticRegion).not.toContainElement(action);
    expect(screen.queryByText("hidden content")).not.toBeInTheDocument();
    // 仍是收缩盒，不因为多了动作就退回 loading 的防重排背板
    expect(surface.className).toContain("shrinkBox");
    expect(surface.className).toContain("shrinkBoxWithActions");
  });

  it("renders actions in the childless error backdrop too", () => {
    render(<StateSurface status="error" testId="surface" actions={<button type="button">重试</button>} />);
    expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument();
  });

  it("never renders actions while loading (nothing to act on mid-flight)", () => {
    render(<StateSurface status="loading" testId="surface" actions={<button type="button">重试</button>} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("adds nothing when actions is absent (backward compat)", () => {
    render(<StateSurface status="empty" testId="surface" />);
    const surface = screen.getByTestId("surface");
    expect(surface.children).toHaveLength(2); // dot + message
    expect(surface).toHaveAttribute("role", "status");
    expect(screen.getByRole("status")).toBe(surface);
    expect(surface.className).not.toContain("shrinkBoxWithActions");
  });

  it("CSS：基础收缩盒保持旧布局，仅 actions 修饰类启用换行", () => {
    const css = readFileSync(cssPath, "utf8");
    const shrinkBox = css.match(/\.shrinkBox\s*{([^}]*)\}/)?.[1] ?? "";
    expect(shrinkBox).not.toContain("flex-wrap");
    expect(css).toMatch(/\.shrinkBoxWithActions\s*{[^}]*flex-wrap:\s*wrap/);
    expect(css).toMatch(/\.emptyActions\s*{[^}]*flex-basis:\s*100%/);
    // 收缩盒若改成 column，没有动作时「圆点 + 文案」也会竖排，改掉既有渲染
    expect(css).not.toMatch(/\.shrinkBox\s*{[^}]*flex-direction:\s*column/);
  });
});

describe("StateSurface CSS module hygiene", () => {
  it("does not use !important, bare hex, or --ib-* tokens", () => {
    const css = readFileSync(cssPath, "utf8");
    expect(css).not.toMatch(/!important/);
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(css).not.toMatch(/--ib-/);
  });

  it("only declares var(--dh-api-radius) or the 50% semantic-dot allowance for border-radius", () => {
    const css = readFileSync(cssPath, "utf8");
    const declarations = [...css.matchAll(/border-radius:\s*([^;]+);/g)].map((match) => match[1].trim());
    expect(declarations.length).toBeGreaterThan(0);
    for (const declaration of declarations) {
      expect(["var(--dh-api-radius)", "50%"]).toContain(declaration);
    }
  });
});
