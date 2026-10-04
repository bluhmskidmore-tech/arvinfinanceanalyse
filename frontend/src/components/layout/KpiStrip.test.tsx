import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { render, screen } from "@testing-library/react";

import { EM_DASH } from "../../pageModel";
import KpiStrip, { type KpiCell } from "./KpiStrip";

const cssPath = resolve(process.cwd(), "src/components/layout/KpiStrip.module.css");
const css = readFileSync(cssPath, "utf8");
const tsxPath = resolve(process.cwd(), "src/components/layout/KpiStrip.tsx");
const tsx = readFileSync(tsxPath, "utf8");

function makeCells(overrides: Partial<KpiCell>[] = []): KpiCell[] {
  const base: KpiCell[] = [
    { key: "a", label: "规模", value: "1,234.5", unit: "亿元" },
    { key: "b", label: "久期", value: "3.21", unit: "年" },
  ];
  return overrides.length > 0 ? (overrides as KpiCell[]) : base;
}

describe("KpiStrip 机械视觉保证", () => {
  it("渲染 label/value/unit/delta，完整标签进 title", () => {
    render(
      <KpiStrip
        testId="strip"
        cells={[
          {
            key: "scale",
            label: "组合规模合计（含正回购口径）",
            value: "12,345.67",
            unit: "亿元",
            delta: "+1.20%",
            deltaTone: "positive",
          },
        ]}
      />,
    );
    const cell = screen.getByTestId("strip-scale");
    expect(cell).toHaveTextContent("12,345.67");
    expect(cell).toHaveTextContent("亿元");
    expect(cell).toHaveTextContent("+1.20%");
    const label = screen.getByText("组合规模合计（含正回购口径）");
    expect(label).toHaveAttribute("title", "组合规模合计（含正回购口径）");
  });

  it("hero 尺寸档落 data-size=hero，默认档为 default 且主值共用 20px", () => {
    const { rerender } = render(<KpiStrip testId="strip" cells={makeCells()} size="hero" />);
    expect(screen.getByTestId("strip")).toHaveAttribute("data-size", "hero");

    rerender(<KpiStrip testId="strip" cells={makeCells()} />);
    expect(screen.getByTestId("strip")).toHaveAttribute("data-size", "default");

    // hero 档只放宽格内留白，主值字号仍由共享规范控制。
    expect(css).toContain('.strip[data-size="hero"] .value');
    expect(css).toContain('.strip[data-size="hero"] .cell');
  });

  it("缺值渲染 EM_DASH 且不渲染单位（即便传入了 unit）", () => {
    render(<KpiStrip testId="strip" cells={[{ key: "x", label: "空值格", value: "", unit: "亿元" }]} />);
    const cell = screen.getByTestId("strip-x");
    expect(cell).toHaveTextContent("—");
    expect(cell).not.toHaveTextContent("亿元");
  });

  it("value 本身就是 EM_DASH 时同样不渲染单位", () => {
    render(<KpiStrip testId="strip" cells={[{ key: "x", label: "空值格", value: "—", unit: "%" }]} />);
    const cell = screen.getByTestId("strip-x");
    expect(cell.textContent).not.toContain("%");
  });

  it("长数值（>=9 字符）标记 data-compact=true，短数值不标记", () => {
    render(
      <KpiStrip
        testId="strip"
        cells={[
          { key: "long", label: "长读数", value: "123,456,789.01" },
          { key: "short", label: "短读数", value: "12.3" },
        ]}
      />,
    );
    const longCell = screen.getByTestId("strip-long");
    const shortCell = screen.getByTestId("strip-short");
    expect(longCell.querySelector('[data-compact="true"]')).not.toBeNull();
    expect(shortCell.querySelector('[data-compact="true"]')).toBeNull();
  });

  it("text 主值落受控 variant，保留状态类结论的小号正文语气", () => {
    render(
      <KpiStrip
        testId="strip"
        cells={[{ key: "state", label: "当前状态", value: "等待复核", valueVariant: "text" }]}
      />,
    );
    expect(screen.getByTestId("strip-state").querySelector('[data-value-variant="text"]')).not.toBeNull();
    expect(css).toContain('.valueRow[data-value-variant="text"] .value');
  });

  it("noteTitle 保留小注的完整悬停证据，缺省仍回退到可见小注", () => {
    const { rerender } = render(
      <KpiStrip
        testId="strip"
        cells={[{ key: "evidence", label: "证据", value: "可用", note: "覆盖 30 天", noteTitle: "覆盖 30 天；来源已核验" }]}
      />,
    );
    expect(screen.getByText("覆盖 30 天")).toHaveAttribute("title", "覆盖 30 天；来源已核验");

    rerender(
      <KpiStrip
        testId="strip"
        cells={[{ key: "evidence", label: "证据", value: "可用", note: "覆盖 30 天" }]}
      />,
    );
    expect(screen.getByText("覆盖 30 天")).toHaveAttribute("title", "覆盖 30 天");
  });

  it("主值装饰继承数值语气，根节点可保留语义定位钩子", () => {
    render(
      <KpiStrip
        testId="strip"
        className="domain-kpi-strip"
        ariaLabel="关键指标"
        cells={[
          {
            key: "risk",
            label: "偏离度",
            value: "6.2%",
            valueTone: "negative",
            valueAdornment: <span data-testid="warning">!</span>,
          },
        ]}
      />,
    );

    const strip = screen.getByTestId("strip");
    const value = screen.getByTestId("strip-risk").querySelector("strong");
    expect(strip).toHaveClass("domain-kpi-strip");
    expect(strip).toHaveAttribute("role", "region");
    expect(strip).toHaveAttribute("aria-label", "关键指标");
    expect(value).toHaveAttribute("data-tone", "negative");
    expect(value).toContainElement(screen.getByTestId("warning"));
    expect(css).toMatch(/\.valueAdornment\s*\{[^}]*margin-left:\s*6px/);
  });

  it("spark 未提供时不渲染走势区也不渲染无历史序列小注", () => {
    render(<KpiStrip testId="strip" cells={[{ key: "noSpark", label: "无走势概念", value: "1.00" }]} />);
    const cell = screen.getByTestId("strip-noSpark");
    expect(cell.querySelector("svg")).toBeNull();
    expect(cell).not.toHaveTextContent("无历史序列");
  });

  it("spark 提供但无有效点（null/空数组/单点）时渲染无历史序列小注而非假线", () => {
    render(
      <KpiStrip
        testId="strip"
        cells={[
          { key: "nullSpark", label: "空走势", value: "1.00", spark: null },
          { key: "emptySpark", label: "空数组", value: "1.00", spark: [] },
          { key: "onePoint", label: "单点", value: "1.00", spark: [5] },
        ]}
      />,
    );
    for (const key of ["nullSpark", "emptySpark", "onePoint"]) {
      const cell = screen.getByTestId(`strip-${key}`);
      expect(cell).toHaveTextContent("无历史序列");
      expect(cell.querySelector("svg")).toBeNull();
    }
  });

  it("spark 有 >=2 个有效点时画线，不显示无历史序列小注", () => {
    render(
      <KpiStrip
        testId="strip"
        cells={[{ key: "ok", label: "有走势", value: "1.00", spark: [1, 2, 3, 2.5] }]}
      />,
    );
    const cell = screen.getByTestId("strip-ok");
    expect(cell.querySelector("svg")).not.toBeNull();
    expect(cell.querySelector("polyline")).not.toBeNull();
    expect(cell).not.toHaveTextContent("无历史序列");
  });

  it("spark 只使用有限点绘制，保留原序列的相对 x 间距，有限点不足两项时诚实回退", () => {
    render(
      <KpiStrip
        testId="strip"
        cells={[
          { key: "nan", label: "含 NaN", value: "1.00", spark: [1, Number.NaN, 2] },
          { key: "infinite", label: "含无穷", value: "1.00", spark: [1, Infinity, 2, -Infinity] },
          { key: "single", label: "仅一个有限点", value: "1.00", spark: [Infinity, 2, -Infinity] },
        ]}
      />,
    );

    const nanPoints = screen.getByTestId("strip-nan").querySelector("polyline")?.getAttribute("points") ?? "";
    expect(nanPoints).not.toMatch(/NaN|Infinity/);
    expect(nanPoints.split(" ")).toHaveLength(2);
    expect(nanPoints).toMatch(/^0\.00,[\d.]+ 56\.00,[\d.]+$/);

    const infinitePoints =
      screen.getByTestId("strip-infinite").querySelector("polyline")?.getAttribute("points") ?? "";
    expect(infinitePoints).not.toMatch(/NaN|Infinity/);
    expect(infinitePoints).toMatch(/^0\.00,[\d.]+ 37\.33,[\d.]+$/);

    const single = screen.getByTestId("strip-single");
    expect(single).toHaveTextContent("无历史序列");
    expect(single.querySelector("svg")).toBeNull();
  });

  it("spark 对有限极值安全归一化，不因跨度溢出生成 NaN 或 Infinity 坐标", () => {
    render(
      <KpiStrip
        testId="strip"
        cells={[
          {
            key: "extreme",
            label: "极值走势",
            value: "1.00",
            spark: [Number.MAX_VALUE, Number.NaN, -Number.MAX_VALUE],
          },
        ]}
      />,
    );

    const points =
      screen.getByTestId("strip-extreme").querySelector("polyline")?.getAttribute("points") ?? "";
    expect(points).not.toMatch(/NaN|Infinity/);
    expect(points).toMatch(/^0\.00,[\d.]+ 56\.00,[\d.]+$/);
  });

  it("delta 缺省时不渲染 delta 元素", () => {
    render(<KpiStrip testId="strip" cells={[{ key: "nodelta", label: "无变动", value: "1.00" }]} />);
    const cell = screen.getByTestId("strip-nodelta");
    expect(cell.querySelector('[data-tone]')).toBeNull();
  });

  it("deltaTone 映射到 data-tone 属性", () => {
    render(
      <KpiStrip
        testId="strip"
        cells={[
          { key: "up", label: "环比", value: "1.00", delta: "+1%", deltaTone: "positive" },
          { key: "down", label: "环比", value: "1.00", delta: "-1%", deltaTone: "negative" },
        ]}
      />,
    );
    expect(screen.getByTestId("strip-up").querySelector('[data-tone="positive"]')).not.toBeNull();
    expect(screen.getByTestId("strip-down").querySelector('[data-tone="negative"]')).not.toBeNull();
  });

  it("loading 态渲染骨架格且不出现真实数值文本", () => {
    render(<KpiStrip testId="strip" loading cells={makeCells()} />);
    const strip = screen.getByTestId("strip");
    expect(strip).toHaveAttribute("data-loading", "true");
    expect(strip.querySelectorAll('[data-skeleton="true"]')).toHaveLength(2);
    expect(strip).not.toHaveTextContent("1,234.5");
  });

  it("loading 骨架数量至少覆盖 xl 列数，不产生比横带更窄的占位", () => {
    render(<KpiStrip testId="strip" loading cells={makeCells()} cols={{ xl: 6 }} />);
    const strip = screen.getByTestId("strip");
    expect(strip.querySelectorAll('[data-skeleton="true"]')).toHaveLength(6);
    expect(strip).toHaveAttribute("data-cols-xl", "6");
  });

  it("cols 缺省时按 cells.length 展开单行（xl/lg 相同）", () => {
    render(<KpiStrip testId="strip" cells={makeCells()} />);
    const strip = screen.getByTestId("strip");
    expect(strip).toHaveAttribute("data-cols-xl", "2");
    expect(strip).toHaveAttribute("data-cols-lg", "2");
    expect(strip).toHaveAttribute("data-cols-base", "2");
  });

  it("cols 会被夹在 [1,8] 区间，防止越界列数破坏栅格", () => {
    render(<KpiStrip testId="strip" cells={makeCells()} cols={{ xl: 20, base: 0 }} />);
    const strip = screen.getByTestId("strip");
    expect(strip).toHaveAttribute("data-cols-xl", "8");
    expect(strip).toHaveAttribute("data-cols-base", "1");
  });

  it("自定义 cols 会原样反映到各断点 data 属性", () => {
    render(<KpiStrip testId="strip" cells={makeCells()} cols={{ base: 1, md: 3, lg: 4, xl: 4 }} />);
    const strip = screen.getByTestId("strip");
    expect(strip).toHaveAttribute("data-cols-base", "1");
    expect(strip).toHaveAttribute("data-cols-md", "3");
    expect(strip).toHaveAttribute("data-cols-lg", "4");
    expect(strip).toHaveAttribute("data-cols-xl", "4");
  });

  // ---- cellTestIdPrefix：横带锚点与格子前缀解耦 ------------------------------

  it("cellTestIdPrefix 未传时，格子 testid 逐字沿用 testId 前缀（现状不变）", () => {
    render(<KpiStrip testId="bond-dashboard-kpi" cells={makeCells()} />);
    expect(screen.getByTestId("bond-dashboard-kpi")).toBeInTheDocument();
    expect(screen.getByTestId("bond-dashboard-kpi-a")).toBeInTheDocument();
    expect(screen.getByTestId("bond-dashboard-kpi-b")).toBeInTheDocument();
  });

  it("cellTestIdPrefix 传入时，横带锚点与格子前缀可以是完全不相关的两串 id", () => {
    render(
      <KpiStrip
        testId="bond-dashboard-headline-kpis"
        cellTestIdPrefix="bond-dashboard-kpi"
        cells={makeCells()}
      />,
    );
    // 横带根节点用 testId，不受 cellTestIdPrefix 影响。
    const band = screen.getByTestId("bond-dashboard-headline-kpis");
    expect(band).toBeInTheDocument();
    // 格子用 cellTestIdPrefix，与 testId 不是前缀关系也能各自命中。
    expect(screen.getByTestId("bond-dashboard-kpi-a")).toBeInTheDocument();
    expect(screen.getByTestId("bond-dashboard-kpi-b")).toBeInTheDocument();
    expect(screen.queryByTestId("bond-dashboard-headline-kpis-a")).toBeNull();
  });

  it("cellTestIdPrefix 单独传入（无 testId）时，横带根节点无 testid 但格子仍可寻址", () => {
    render(<KpiStrip cellTestIdPrefix="only-cells" cells={makeCells()} />);
    expect(screen.getByTestId("only-cells-a")).toBeInTheDocument();
    expect(screen.getByTestId("only-cells-b")).toBeInTheDocument();
  });

  it("loading 骨架 testid 同样跟随 cellTestIdPrefix（而不是固定绑死 testId）", () => {
    render(
      <KpiStrip
        testId="bond-dashboard-headline-kpis"
        cellTestIdPrefix="bond-dashboard-kpi"
        loading
        cells={makeCells()}
      />,
    );
    expect(screen.getByTestId("bond-dashboard-kpi-skeleton-0")).toBeInTheDocument();
    expect(screen.queryByTestId("bond-dashboard-headline-kpis-skeleton-0")).toBeNull();
  });

  // ---- 机械 CSS 保证（jsdom 不跑布局/绘制，样式规则文本断言） ----------------

  it("CSS：标签 2 行 clamp + 固定 min-height", () => {
    expect(css).toMatch(/\.label\s*{[^}]*-webkit-line-clamp:\s*2/);
    expect(css).toMatch(/\.label\s*{[^}]*min-height:\s*32px/);
  });

  it("CSS：主值/单位/变动读数走等宽栈 tabular-nums", () => {
    expect(css).toMatch(/\.value\s*{[^}]*font-variant-numeric:\s*tabular-nums/);
    expect(css).toMatch(/\.unit\s*{[^}]*font-variant-numeric:\s*tabular-nums/);
    expect(css).toMatch(/\.delta\s*{[^}]*font-variant-numeric:\s*tabular-nums/);
  });

  it("CSS：主值固定 20px，且 keep-all 防拆词", () => {
    expect(css).toMatch(/\.value\s*{[^}]*font-size:\s*20px/);
    expect(css).toMatch(/\.value\s*{[^}]*word-break:\s*keep-all/);
    expect(css).toMatch(/\.unit\s*{[^}]*word-break:\s*keep-all/);
  });

  it("CSS：长数值保持 20px 并完整换行，不随断点缩字", () => {
    expect(css).toMatch(/\[data-compact="true"\]\s*\.value\s*{[^}]*font-size:\s*20px/);
    expect(css).toMatch(/\[data-compact="true"\]\s*\.value\s*{[^}]*overflow-wrap:\s*anywhere/);
    // 主值字号不应被媒体断点降级。
    const mediaBlocks = [...css.matchAll(/@media[^{]*{([\s\S]*?)}\s*}/g)].map((m) => m[0]);
    expect(mediaBlocks.some((block) => block.includes("font-size"))).toBe(false);
  });

  it("CSS：等高分格靠 grid-auto-rows:1fr，分隔线靠 gap（不是靠 nth-child 精确算末列）", () => {
    expect(css).toMatch(/grid-auto-rows:\s*1fr/);
    expect(css).toMatch(/gap:\s*1px/);
    expect(css).not.toMatch(/nth-child/);
  });

  it("CSS：颜色只走 --dh-api-* 语义链，零 !important / 裸 hex / --ib- 引用", () => {
    expect(css).not.toMatch(/!important/);
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(css).not.toMatch(/--ib-/);
    expect(css).toMatch(/var\(--dh-api-radius\)/);
  });

  it("TSX：无静态内联 style，缺值走 EM_DASH 导入而非字面量", () => {
    expect(tsx).not.toMatch(/style=\{\{/);
    expect(tsx).not.toMatch(/["'`]--["'`]/);
    expect(tsx).toMatch(/import\s*\{\s*EM_DASH/);
  });
});

describe("KpiStrip 主值着色", () => {
  const valueOf = (testId: string) =>
    screen.getByTestId(testId).querySelector("strong") as HTMLElement;

  it("传 valueTone 时把 tone 挂在主值上，与 delta 的 tone 各自独立", () => {
    render(
      <KpiStrip
        testId="strip"
        cells={[
          {
            key: "risk",
            label: "A股风险",
            value: "64",
            valueTone: "negative",
            delta: "+3",
            deltaTone: "positive",
          },
        ]}
      />,
    );
    expect(valueOf("strip-risk")).toHaveAttribute("data-tone", "negative");
    expect(screen.getByText("+3")).toHaveAttribute("data-tone", "positive");
  });

  it("不传 valueTone 时主值不挂属性（存量调用点 DOM 逐字不变）", () => {
    render(<KpiStrip testId="strip" cells={[{ key: "a", label: "规模", value: "1,234.5" }]} />);
    expect(valueOf("strip-a")).not.toHaveAttribute("data-tone");
  });

  it("缺值恒为中性：即使显式传了 tone，EM_DASH 也不着色", () => {
    // 把"没有数据"染成红或绿会被读成一个业务结论。
    render(
      <KpiStrip
        testId="strip"
        cells={[{ key: "a", label: "规模", value: "", valueTone: "negative" }]}
      />,
    );
    const value = valueOf("strip-a");
    expect(value).toHaveTextContent(EM_DASH);
    expect(value).not.toHaveAttribute("data-tone");
  });

  it("格级状态挂在格子上，缺省不挂属性", () => {
    render(
      <KpiStrip
        testId="strip"
        cells={[
          { key: "a", label: "已就绪", value: "1", cellStatus: "ready" },
          { key: "b", label: "延后", value: "2", cellStatus: "deferred" },
          { key: "c", label: "缺省", value: "3" },
        ]}
      />,
    );
    expect(screen.getByTestId("strip-a")).toHaveAttribute("data-status", "ready");
    expect(screen.getByTestId("strip-b")).toHaveAttribute("data-status", "deferred");
    expect(screen.getByTestId("strip-c")).not.toHaveAttribute("data-status");
  });

  it("为非 ready 的格级状态提供仅供辅助技术读取的语义文本", () => {
    render(
      <KpiStrip
        testId="strip"
        cells={[
          { key: "ready", label: "已就绪", value: "1", cellStatus: "ready" },
          { key: "loading", label: "载入中", value: "2", cellStatus: "loading" },
          { key: "deferred", label: "等待中", value: "3", cellStatus: "deferred" },
          { key: "failed", label: "失败", value: "4", cellStatus: "failed" },
        ]}
      />,
    );

    for (const label of ["正在载入", "等待完整分析", "读取失败"]) {
      const statusText = screen.getByText(label);
      expect(statusText.className).toContain("srOnly");
    }
    expect(screen.getByTestId("strip-ready")).not.toHaveTextContent("正在载入");
    expect(screen.getByTestId("strip-ready")).not.toHaveTextContent("等待完整分析");
    expect(screen.getByTestId("strip-ready")).not.toHaveTextContent("读取失败");
  });

  it("CSS：状态优先于语气——非 ready 的状态色特异性高于 tone，且不靠 !important", () => {
    // 「还没拿到数」和「拿到了一个坏数」必须看得出区别。
    expect(css).toMatch(
      /\.cell\[data-status="loading"\]\s*\.value,\s*\.cell\[data-status="deferred"\]\s*\.value\s*{[^}]*var\(--dh-api-muted\)/,
    );
    expect(css).toMatch(/\.cell\[data-status="failed"\]\s*\.value\s*{[^}]*var\(--dh-api-red\)/);
    // ready 与「不传」都不写规则，两者才能与既有渲染逐字相同
    expect(css).not.toMatch(/\.cell\[data-status="ready"\]/);
  });

  it("CSS：主值三档着色走 --dh-api-* 语义链，neutral 不写规则以继承 ink", () => {
    expect(css).toMatch(/\.value\[data-tone="positive"\]\s*{[^}]*var\(--dh-api-green\)/);
    expect(css).toMatch(/\.value\[data-tone="negative"\]\s*{[^}]*var\(--dh-api-red\)/);
    expect(css).toMatch(/\.value\[data-tone="warning"\]\s*{[^}]*var\(--dh-api-amber\)/);
    // neutral 有规则就意味着它会覆盖 .value 的 ink，与"缺省同色"的契约冲突
    expect(css).not.toMatch(/\.value\[data-tone="neutral"\]/);
  });
});
