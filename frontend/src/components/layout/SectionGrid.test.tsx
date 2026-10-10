import { readFileSync } from "node:fs";
import path from "node:path";

import { render, screen } from "@testing-library/react";

import { SectionGrid, SectionGridItem } from "./SectionGrid";

const cssPath = path.join(import.meta.dirname, "SectionGrid.module.css");

describe("SectionGrid", () => {
  it("renders children", () => {
    render(
      <SectionGrid testId="sg">
        <div>card-a</div>
        <div>card-b</div>
      </SectionGrid>,
    );
    expect(screen.getByText("card-a")).toBeInTheDocument();
    expect(screen.getByText("card-b")).toBeInTheDocument();
  });

  it("defaults align to start (DESIGN.md §11.2 anti-pattern guard)", () => {
    render(<SectionGrid testId="sg">content</SectionGrid>);
    expect(screen.getByTestId("sg")).toHaveAttribute("data-align", "start");
  });

  it("requires an explicit opt-in to switch to stretch", () => {
    render(
      <SectionGrid testId="sg" align="stretch">
        content
      </SectionGrid>,
    );
    expect(screen.getByTestId("sg")).toHaveAttribute("data-align", "stretch");
  });

  it("defaults gap to 16px when omitted", () => {
    render(<SectionGrid testId="sg">content</SectionGrid>);
    expect(screen.getByTestId("sg")).toHaveStyle({ "--sg-gap": "16px" } as never);
  });

  it("accepts every allowed gap on the 8/12/16/24 ladder", () => {
    for (const gap of [8, 12, 16, 24] as const) {
      const { unmount } = render(
        <SectionGrid testId="sg" gap={gap}>
          content
        </SectionGrid>,
      );
      expect(screen.getByTestId("sg")).toHaveStyle({ "--sg-gap": `${gap}px` } as never);
      unmount();
    }
  });

  it("falls back to the 16px default and warns in dev for an off-ladder gap", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(
      <SectionGrid testId="sg" gap={10 as unknown as 16}>
        content
      </SectionGrid>,
    );
    expect(screen.getByTestId("sg")).toHaveStyle({ "--sg-gap": "16px" } as never);
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining("gap=10"));
  });

  it("resolves per-breakpoint column counts and forward-fills unset breakpoints", () => {
    render(
      <SectionGrid testId="sg" cols={{ base: 1, lg: 3 }}>
        content
      </SectionGrid>,
    );
    const root = screen.getByTestId("sg");
    expect(root).toHaveStyle({
      "--sg-cols-base": "1",
      "--sg-cols-md": "1",
      "--sg-cols-lg": "3",
      "--sg-cols-xl": "3",
    } as never);
  });

  it("emits weighted tracks for an array col spec and keeps the column count in sync", () => {
    render(
      <SectionGrid testId="sg" cols={{ base: 1, lg: [1.45, 1.2, 0.95] }}>
        content
      </SectionGrid>,
    );
    const root = screen.getByTestId("sg");
    expect(root.style.getPropertyValue("--sg-track-lg")).toBe(
      "minmax(0, 1.45fr) minmax(0, 1.2fr) minmax(0, 0.95fr)",
    );
    // 列数跟随权重项数，断点媒体查询与测试断言共用同一个来源。
    expect(root.style.getPropertyValue("--sg-cols-lg")).toBe("3");
    // xl 未给定时前向继承 lg 的权重，不静默退回等分。
    expect(root.style.getPropertyValue("--sg-track-xl")).toBe(
      "minmax(0, 1.45fr) minmax(0, 1.2fr) minmax(0, 0.95fr)",
    );
    // base 仍是等分，其 track 变量不设，让 CSS 走 repeat 回退链。
    expect(root.style.getPropertyValue("--sg-track-base")).toBe("");
  });

  it("leaves every --sg-track-* unset for plain equal-width specs", () => {
    render(
      <SectionGrid testId="sg" cols={{ base: 1, lg: 3 }}>
        content
      </SectionGrid>,
    );
    const root = screen.getByTestId("sg");
    for (const leg of ["base", "md", "lg", "xl"]) {
      expect(root.style.getPropertyValue(`--sg-track-${leg}`)).toBe("");
    }
  });

  it("falls back to the previous breakpoint when a weight array has no valid positive entry", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(
      <SectionGrid testId="sg" cols={{ base: 2, lg: [0, -1] }}>
        content
      </SectionGrid>,
    );
    const root = screen.getByTestId("sg");
    expect(root.style.getPropertyValue("--sg-track-lg")).toBe("");
    expect(root.style.getPropertyValue("--sg-cols-lg")).toBe("2");
    warn.mockRestore();
  });

  it("switches to auto-fill mode and injects the min column width when minColWidth is set", () => {
    render(
      <SectionGrid testId="sg" minColWidth={240}>
        content
      </SectionGrid>,
    );
    const root = screen.getByTestId("sg");
    expect(root).toHaveAttribute("data-mode", "auto-fill");
    expect(root).toHaveStyle({ "--sg-min-col-width": "240px" } as never);
  });

  it("stays in cols mode when minColWidth is not provided", () => {
    render(<SectionGrid testId="sg">content</SectionGrid>);
    expect(screen.getByTestId("sg")).toHaveAttribute("data-mode", "cols");
  });

  // ---- SectionGridItem：子项跨列 --------------------------------------------

  it("SectionGridItem 默认（不传 span）四档跨列变量都是 1（不跨列）", () => {
    render(
      <SectionGrid testId="sg">
        <SectionGridItem testId="item">card</SectionGridItem>
      </SectionGrid>,
    );
    const item = screen.getByTestId("item");
    expect(item.style.getPropertyValue("--sgi-span-base")).toBe("1");
    expect(item.style.getPropertyValue("--sgi-span-md")).toBe("1");
    expect(item.style.getPropertyValue("--sgi-span-lg")).toBe("1");
    expect(item.style.getPropertyValue("--sgi-span-xl")).toBe("1");
  });

  it("SectionGridItem span 传数字时全断点同值", () => {
    render(
      <SectionGrid testId="sg">
        <SectionGridItem testId="item" span={2}>
          card
        </SectionGridItem>
      </SectionGrid>,
    );
    const item = screen.getByTestId("item");
    expect(item.style.getPropertyValue("--sgi-span-base")).toBe("2");
    expect(item.style.getPropertyValue("--sgi-span-md")).toBe("2");
    expect(item.style.getPropertyValue("--sgi-span-lg")).toBe("2");
    expect(item.style.getPropertyValue("--sgi-span-xl")).toBe("2");
  });

  it("SectionGridItem span 按断点前向继承（未给的档沿用上一档，不静默退回 1）", () => {
    render(
      <SectionGrid testId="sg">
        <SectionGridItem testId="item" span={{ base: 1, lg: 2 }}>
          card
        </SectionGridItem>
      </SectionGrid>,
    );
    const item = screen.getByTestId("item");
    expect(item.style.getPropertyValue("--sgi-span-base")).toBe("1");
    expect(item.style.getPropertyValue("--sgi-span-md")).toBe("1");
    expect(item.style.getPropertyValue("--sgi-span-lg")).toBe("2");
    // xl 未给定时前向继承 lg 的跨列数，实现「1440 三列时不跨、1280 两列时跨 2 列」
    // 需要显式覆盖 xl=1 才能在更宽断点收回跨列，这里验证不覆盖时的前向继承默认值。
    expect(item.style.getPropertyValue("--sgi-span-xl")).toBe("2");
  });

  it("SectionGridItem 支持「lg 跨 2 列、xl 不跨」这种非单调断点表达", () => {
    render(
      <SectionGrid testId="sg">
        <SectionGridItem testId="item" span={{ base: 1, lg: 2, xl: 1 }}>
          card
        </SectionGridItem>
      </SectionGrid>,
    );
    const item = screen.getByTestId("item");
    expect(item.style.getPropertyValue("--sgi-span-lg")).toBe("2");
    expect(item.style.getPropertyValue("--sgi-span-xl")).toBe("1");
  });

  it("SectionGridItem span 非法值（0/负数/NaN）回退为上一档而非崩溃或负跨列", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(
      <SectionGrid testId="sg">
        <SectionGridItem testId="item" span={{ base: 2, lg: -1, xl: NaN }}>
          card
        </SectionGridItem>
      </SectionGrid>,
    );
    const item = screen.getByTestId("item");
    expect(item.style.getPropertyValue("--sgi-span-base")).toBe("2");
    expect(item.style.getPropertyValue("--sgi-span-lg")).toBe("2");
    expect(item.style.getPropertyValue("--sgi-span-xl")).toBe("2");
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it("未使用 SectionGridItem 的普通 children 不受影响，不出现 span 变量", () => {
    render(
      <SectionGrid testId="sg">
        <div data-testid="plain">card</div>
      </SectionGrid>,
    );
    const plain = screen.getByTestId("plain");
    expect(plain.style.getPropertyValue("--sgi-span-lg")).toBe("");
  });

  it("CSS：grid-column: span 只合并 minmax(0, 1fr) 轨道，不引入裸宽度声明", () => {
    const css = readFileSync(cssPath, "utf8");
    expect(css).toMatch(/\.item\s*{[^}]*grid-column:\s*span var\(--sgi-span-base/);
    expect(css).toMatch(/--sgi-span-md/);
    expect(css).toMatch(/--sgi-span-lg/);
    expect(css).toMatch(/--sgi-span-xl/);
  });

  it("CSS：span 各档变量分别独立赋值（不叠 var() 回退链），与 cols 的解析方式自洽", () => {
    const css = readFileSync(cssPath, "utf8");
    // 每个 grid-column 声明里只应出现一个 --sgi-span-* 变量，不应该出现
    // var(--sgi-span-xl, var(--sgi-span-lg, ...)) 这种嵌套回退链。
    const spanDeclarations = [...css.matchAll(/grid-column:\s*span var\([^;]+;/g)].map((m) => m[0]);
    expect(spanDeclarations.length).toBeGreaterThanOrEqual(4);
    for (const declaration of spanDeclarations) {
      const varCount = (declaration.match(/--sgi-span-/g) ?? []).length;
      expect(varCount).toBe(1);
    }
  });

  it("never emits a bare 1fr column track (zero horizontal overflow requirement)", () => {
    const css = readFileSync(cssPath, "utf8");
    const trackDeclarations = [...css.matchAll(/grid-template-columns:\s*([^;]+);/g)].map(
      (match) => match[1],
    );
    expect(trackDeclarations.length).toBeGreaterThan(0);
    // Every legitimate "1fr" in this file is the second arg of a minmax()
    // call, so it is always immediately preceded by "0, " (minmax(0, 1fr))
    // or ", " that itself follows a closing paren (minmax(min(...), 1fr)).
    // A bare, unwrapped "1fr" track would not match either shape.
    const bareOneFrPattern = /(?<!0, )(?<!\), )1fr/;
    for (const declaration of trackDeclarations) {
      expect(declaration).toContain("1fr");
      expect(declaration).toContain("minmax(");
      expect(declaration).not.toMatch(bareOneFrPattern);
    }
  });

  it("does not use !important, bare hex, or --ib-* tokens", () => {
    const css = readFileSync(cssPath, "utf8");
    expect(css).not.toMatch(/!important/);
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(css).not.toMatch(/--ib-/);
  });
});
