import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { render, screen } from "@testing-library/react";

import SectionHead, {
  SECTION_HEAD_COUNTER_CSS_VAR,
  SECTION_HEAD_STACK_CLASSNAME,
  type SectionMetaField,
} from "./SectionHead";
import styles from "./SectionHead.module.css";

const cssPath = resolve(process.cwd(), "src/components/layout/SectionHead.module.css");
const css = readFileSync(cssPath, "utf8");
const tsxPath = resolve(process.cwd(), "src/components/layout/SectionHead.tsx");
const tsx = readFileSync(tsxPath, "utf8");

/**
 * 外接编号域的开发期自检要读 `document.styleSheets`。vitest 没开 `css`，页面 CSS
 * 不会被注入，所以这里手工注入一张样式表来模拟「页面 CSS 已加载」。自检在一张
 * 样式表都读不到时不下结论（避免样式未注入阶段误报），因此哪怕是「配置缺失」的
 * 用例也必须注入一张表，只是表里没有那个 counter。
 */
function mountPageStyleSheet(cssText: string): HTMLStyleElement {
  const element = document.createElement("style");
  element.textContent = cssText;
  document.head.append(element);
  return element;
}

/** 页面 CSS 那半边配齐的样子：容器起点 + 分区容器递增。 */
const COMPLETE_PAGE_COUNTER_CSS = `
  .macro-toolkit-page__main { counter-reset: mt-section; }
  .macro-toolkit-section { counter-increment: mt-section; }
`;

afterEach(() => {
  for (const style of document.head.querySelectorAll("style")) style.remove();
});

describe("SectionHead 机械视觉保证", () => {
  it("渲染标题；ready（state 缺省）不渲染任何状态位 DOM", () => {
    render(<SectionHead testId="head" title="当日结论" />);
    const head = screen.getByTestId("head");
    expect(head).toHaveTextContent("当日结论");
    expect(head.querySelector('[role="status"]')).toBeNull();
  });

  it("state 非空时渲染状态位，文案与 tone 由使用方传入", () => {
    render(<SectionHead testId="head" title="持仓工作区" state={{ label: "读取中", tone: "loading" }} />);
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("读取中");
    expect(status).toHaveAttribute("data-tone", "loading");
  });

  it("state.tone 覆盖五态且各自保留原文", () => {
    const tones: Array<{ tone: "loading" | "error" | "empty" | "stale" | "partial"; label: string }> = [
      { tone: "loading", label: "读取中" },
      { tone: "error", label: "读取失败" },
      { tone: "empty", label: "暂无数据" },
      { tone: "stale", label: "数据延迟" },
      { tone: "partial", label: "部分缺失" },
    ];
    for (const { tone, label } of tones) {
      render(<SectionHead testId={`head-${tone}`} title="标题" state={{ label, tone }} />);
      const status = screen.getByTestId(`head-${tone}`).querySelector('[role="status"]');
      expect(status).not.toBeNull();
      expect(status).toHaveAttribute("data-tone", tone);
      expect(status).toHaveTextContent(label);
    }
  });

  it("numbered=false 时既不打印序号也不占用编号域", () => {
    render(
      <div className={SECTION_HEAD_STACK_CLASSNAME}>
        <SectionHead testId="head" title="面板卡头" numbered={false} />
      </div>,
    );
    expect(screen.getByTestId("head")).toHaveAttribute("data-numbered", "false");
    // 两条 CSS 规则缺一不可：只去 content 不去 counter-increment，会让不编号的
    // 头悄悄吃掉一个序号，同域内后续分区跳号。
    expect(css).toMatch(
      /\.head\[data-numbered="false"\]\s*\{[^}]*counter-increment:\s*none/,
    );
    expect(css).toMatch(
      /\.head\[data-numbered="false"\]\s\.titleRow::before\s*\{[^}]*content:\s*none/,
    );
  });

  it("编号态缺 stack 容器时在开发环境告警（静默错号没有任何其他护栏能抓到）", () => {
    // 自检只在「这个环境真的加载了编号 CSS」时才下结论——jsdom 不注入页面 .css，
    // 所以这里显式建立那个前提，否则测的就不是告警逻辑而是环境。
    const styleTag = document.createElement("style");
    styleTag.textContent = ".probe { counter-reset: probe-counter; }";
    document.head.append(styleTag);
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(<SectionHead testId="orphan" title="孤立分区头" />);
    expect(warn).toHaveBeenCalledTimes(1);
    expect(String(warn.mock.calls[0]?.[0])).toContain("SECTION_HEAD_STACK_CLASSNAME");
    warn.mockRestore();
    styleTag.remove();
  });

  it("编号 CSS 整体未加载时不告警（jsdom 下每个组件测试都会误报，真告警会被淹没）", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(<SectionHead testId="orphan-no-css" title="孤立分区头" />);
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });

  it("套了 stack 容器或显式不编号时都不告警", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(
      <div className={SECTION_HEAD_STACK_CLASSNAME}>
        <section>
          <SectionHead testId="nested" title="嵌套在 stack 里" />
        </section>
      </div>,
    );
    render(<SectionHead testId="unnumbered" title="不编号" numbered={false} />);
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });

  it("titleId 落到 h2 上，供外层 aria-labelledby 引用", () => {
    render(
      <section aria-labelledby="probe-title" data-testid="region">
        <SectionHead testId="head" title="风险概览" titleId="probe-title" numbered={false} />
      </section>,
    );
    const heading = screen.getByRole("heading", { level: 2, name: "风险概览" });
    expect(heading).toHaveAttribute("id", "probe-title");
    expect(screen.getByTestId("region")).toHaveAttribute("aria-labelledby", "probe-title");
  });

  it("不传 titleId 时 h2 不带 id（不制造无意义的 DOM 属性）", () => {
    render(<SectionHead testId="head" title="风险概览" numbered={false} />);
    expect(screen.getByRole("heading", { level: 2 })).not.toHaveAttribute("id");
  });

  it("titleWrap=wrap 时允许完整标题在窄屏换行，不退化为省略号", () => {
    render(
      <SectionHead
        testId="head"
        title="2026-07-31 primary 对账明细"
        titleWrap="wrap"
        numbered={false}
      />,
    );
    expect(screen.getByTestId("head")).toHaveAttribute("data-title-wrap", "wrap");
    expect(css).toMatch(
      /\.head\[data-title-wrap="wrap"\]\s+\.title\s*\{[^}]*overflow:\s*visible[^}]*text-overflow:\s*clip[^}]*white-space:\s*normal/,
    );
  });

  it("titleWrap 缺省保持单行省略契约，不写额外 DOM 属性", () => {
    render(<SectionHead testId="head" title="默认单行标题" numbered={false} />);
    expect(screen.getByTestId("head")).not.toHaveAttribute("data-title-wrap");
    expect(css).toMatch(
      /\.title\s*\{[^}]*overflow:\s*hidden[^}]*text-overflow:\s*ellipsis[^}]*white-space:\s*nowrap/,
    );
  });

  it("meta 的 label 与 value 之间靠 gap 拉开，不靠不渲染的空白 flex item", () => {
    // Flexbox 规范：纯空白的匿名 flex item 不渲染，所以 TSX 里的 {" "} 画不出来。
    // 两个 inline-flex 容器都必须显式 gap，否则「来源 kpi」会显示成「来源kpi」，
    // 而 toHaveTextContent 与 jsdom 都抓不到（textContent 里那个空格还在）。
    for (const selector of ["\\.metaInlineItem", "\\.metaCell"]) {
      const body = css.match(new RegExp(`${selector}\\s*\\{([^}]*)\\}`))?.[1] ?? "";
      expect(body).toMatch(/display:\s*inline-flex/);
      expect(body).toMatch(/gap:\s*\d+px/);
    }
  });

  it("meta 缺省或空数组时不渲染 meta 行", () => {
    render(<SectionHead testId="head" title="标题" meta={[]} />);
    const head = screen.getByTestId("head");
    expect(head.querySelector(`.${styles.metaInline}`)).toBeNull();
    expect(head.querySelector(`.${styles.metaGrid}`)).toBeNull();
  });

  it("meta <=2 项走行内拼接，且恰好只出现一个 · 字符", () => {
    const meta: SectionMetaField[] = [
      { label: "报告日", value: "2026-08-26" },
      { label: "口径", value: "正式" },
    ];
    render(<SectionHead testId="head" title="标题" meta={meta} />);
    const head = screen.getByTestId("head");
    expect(head).toHaveTextContent("报告日 2026-08-26");
    expect(head).toHaveTextContent("口径 正式");
    const dotCount = (head.textContent?.match(/·/g) ?? []).length;
    expect(dotCount).toBe(1);
  });

  it("meta 恰 1 项时不产生任何 · 字符", () => {
    render(<SectionHead testId="head" title="标题" meta={[{ label: "报告日", value: "2026-08-26" }]} />);
    const head = screen.getByTestId("head");
    const dotCount = (head.textContent?.match(/·/g) ?? []).length;
    expect(dotCount).toBe(0);
  });

  it("meta >2 项自动改竖线分栏，全程零 · 字符（不会被拼成违反配额的字符串）", () => {
    const meta: SectionMetaField[] = [
      { label: "报告日", value: "2026-08-26" },
      { label: "口径", value: "正式" },
      { label: "来源", value: "余额分析台账" },
      { label: "覆盖率", value: "92%" },
    ];
    render(<SectionHead testId="head" title="标题" meta={meta} />);
    const head = screen.getByTestId("head");
    for (const field of meta) {
      expect(head).toHaveTextContent(`${field.label} ${field.value}`);
    }
    const dotCount = (head.textContent?.match(/·/g) ?? []).length;
    expect(dotCount).toBe(0);
  });

  it("字段自带 · 时即使只有 2 项也改竖线分栏，组件不再叠加自己的 ·", () => {
    const meta: SectionMetaField[] = [
      { label: "报告日", value: "2026-08-26 · 已核验" },
      { label: "口径", value: "正式" },
    ];
    render(<SectionHead testId="head" title="标题" meta={meta} />);
    const head = screen.getByTestId("head");
    expect(head.querySelector(`.${styles.metaGrid}`)).not.toBeNull();
    expect(head.querySelector(`.${styles.metaInline}`)).toBeNull();
    // 唯一的 · 来自字段原文，组件没有再插一个把单行推到 2 个（DESIGN.md §7）。
    const dotCount = (head.textContent?.match(/·/g) ?? []).length;
    expect(dotCount).toBe(1);
  });

  it("meta 字段缺省 title 时回退为 “label value”；显式 title 时使用原文", () => {
    render(
      <SectionHead
        testId="head"
        title="标题"
        meta={[
          { label: "报告日", value: "2026-08-26" },
          { label: "口径", value: "正式", title: "口径：正式（已确认）" },
        ]}
      />,
    );
    const head = screen.getByTestId("head");
    expect(head.querySelector('[title="报告日 2026-08-26"]')).not.toBeNull();
    expect(head.querySelector('[title="口径：正式（已确认）"]')).not.toBeNull();
  });

  it("note 缺省不渲染；提供时渲染原文", () => {
    const { rerender } = render(<SectionHead testId="head" title="标题" />);
    expect(screen.getByTestId("head").querySelector("p")).toBeNull();
    rerender(<SectionHead testId="head" title="标题" note="含至评级缺失的债券" />);
    expect(screen.getByTestId("head")).toHaveTextContent("含至评级缺失的债券");
  });

  it("actions 透传交互元素", () => {
    render(<SectionHead testId="head" title="标题" actions={<button type="button">展开全部</button>} />);
    expect(screen.getByRole("button", { name: "展开全部" })).toBeInTheDocument();
  });

  it("导出 SECTION_HEAD_STACK_CLASSNAME 供使用方套在容器上", () => {
    expect(typeof SECTION_HEAD_STACK_CLASSNAME).toBe("string");
    expect(SECTION_HEAD_STACK_CLASSNAME.length).toBeGreaterThan(0);
  });

  // ---- 机械 CSS 保证（jsdom 不跑布局/计数器渲染，样式规则文本断言） ----------

  it("CSS：counter-reset 挂容器类、counter-increment 与 content:counter(...) 挂头部类", () => {
    expect(css).toMatch(/\.stack\s*{[^}]*counter-reset:\s*layoutSectionHead/);
    expect(css).toMatch(/\.head\s*{[^}]*counter-increment:\s*layoutSectionHead/);
    expect(css).toMatch(/content:\s*counter\(layoutSectionHead,\s*decimal-leading-zero\)/);
  });

  it("TSX：组件本身不手写编号（不存在人工序号状态/拼接逻辑）", () => {
    expect(tsx).not.toMatch(/useState/);
    expect(tsx).not.toMatch(/index\s*\+\s*1/);
    expect(tsx).not.toMatch(/String\(.*\)\.padStart/);
  });

  it("CSS：14px/600 标题 + 发丝底线 + scroll-margin-top", () => {
    expect(css).toMatch(/\.title\s*{[^}]*font-size:\s*14px/);
    expect(css).toMatch(/\.title\s*{[^}]*font-weight:\s*600/);
    expect(css).toMatch(/\.head\s*{[^}]*border-bottom:\s*1px solid var\(--dh-api-line\)/);
    expect(css).toMatch(/\.head\s*{[^}]*scroll-margin-top:/);
  });

  it("CSS：眉标不使用大写宽字距装饰（无 text-transform/letter-spacing 眉标类）", () => {
    expect(css).not.toMatch(/text-transform\s*:\s*uppercase/);
  });

  it("CSS：不使用衬线字体", () => {
    expect(css).not.toMatch(/serif/i);
  });

  it("CSS：强调色只留 actions 可点击元素，标题/meta/note 用中性色阶", () => {
    expect(css).toMatch(/\.actions a,\s*\n?\s*\.actions button\s*{[^}]*color:\s*var\(--dh-api-blue\)/);
    expect(css).toMatch(/\.title\s*{[^}]*color:\s*var\(--dh-api-ink\)/);
    expect(css).toMatch(/\.metaLabel\s*{[^}]*color:\s*var\(--dh-api-muted\)/);
    expect(css).toMatch(/\.note\s*{[^}]*color:\s*var\(--dh-api-muted\)/);
    expect(css).not.toMatch(/\.title\s*{[^}]*var\(--dh-api-blue\)/);
  });

  it("CSS：颜色只走 --dh-api-* 语义链，零 !important / 裸 hex / --ib- 引用", () => {
    expect(css).not.toMatch(/!important/);
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(css).not.toMatch(/--ib-/);
  });

  it("TSX：唯一的内联样式是外接编号的 counter 名绑定，无字面量缺值占位符", () => {
    // 原来是「一条内联 style 都不许有」。外接编号必须把 counter 名交到 CSS 手里，
    // 而 React 只有 style 这一个写自定义属性的入口，所以改成更紧的约束：整份文件
    // 只有一处 style=，它绑定的对象只含 SECTION_HEAD_COUNTER_CSS_VAR 一个键。
    // 松掉这条断言（比如加第二处 style= 或往对象里塞第二个键）会让「不给外部注入
    // 任意样式开后门」这个承诺失效。
    expect(tsx.match(/style\s*=/g) ?? []).toHaveLength(1);
    expect(tsx).toMatch(/style=\{counterNameStyle\(/);
    const styleObjectBodies = tsx.match(/return \{ \[SECTION_HEAD_COUNTER_CSS_VAR\]: counter \};/g);
    expect(styleObjectBodies).toHaveLength(1);
    expect(tsx).not.toMatch(/["'`]--["'`]/);
    expect(tsx).not.toMatch(/["'`]-["'`]/);
  });

  it("props 不开放 style / className 透传口子", () => {
    // 缺口三的真正要求不是「有一个间距 API」，是「不要有任意样式注入口」。
    // 这两条断言是那个承诺的机械形式：没有它们，后来的人加一个 style?: CSSProperties
    // 不会碰红任何测试。
    const propsBlock = tsx.slice(
      tsx.indexOf("export type SectionHeadProps"),
      tsx.indexOf("export const SECTION_HEAD_COUNTER_CSS_VAR"),
    );
    expect(propsBlock.length).toBeGreaterThan(0);
    expect(propsBlock).not.toMatch(/\bstyle\?:/);
    expect(propsBlock).not.toMatch(/\bclassName\?:/);
  });
});

/**
 * 编号相关能力的失败模式是「静默错号」而不是「缺号」：号照常打印，只是打错。
 * 现有的 38 条深色契约在分区头全部错号的状态下依然全绿，所以本段是唯一防线。
 * jsdom 不计算 CSS counter，因此一律断言 DOM 属性与样式规则文本，不断言渲染数字。
 */
describe("SectionHead 外接编号域（缺口一）", () => {
  it("numbered 传对象时进入外接编号态，counter 名落到自定义属性上", () => {
    mountPageStyleSheet(COMPLETE_PAGE_COUNTER_CSS);
    render(<SectionHead testId="head" title="策略展示" numbered={{ counter: "mt-section" }} />);
    const head = screen.getByTestId("head");
    expect(head).toHaveAttribute("data-numbered", "external");
    expect(head.style.getPropertyValue(SECTION_HEAD_COUNTER_CSS_VAR)).toBe("mt-section");
    // 递增位默认在页面容器上，分区头不认领。
    expect(head).not.toHaveAttribute("data-counter-increment");
  });

  it("外接态关掉本原语自己的 counter-increment（否则页面容器与分区头双重递增，序号翻倍）", () => {
    expect(css).toMatch(
      /\.head\[data-numbered="external"\]\s*\{[^}]*counter-increment:\s*none/,
    );
  });

  it("外接态的序号样式仍归原语：只换 counter 名，decimal-leading-zero 使用方碰不到", () => {
    expect(css).toMatch(
      /\.head\[data-numbered="external"\]\s\.titleRow::before\s*\{[^}]*content:\s*counter\(var\(--layout-section-head-counter\),\s*decimal-leading-zero\)/,
    );
    // 11px / tabular 数字栈 / muted 全部继承基础 .titleRow::before，外接态没有另起一套。
    expect(css).toMatch(/\.titleRow::before\s*\{[^}]*font-size:\s*11px/);
    expect(css).toMatch(/\.titleRow::before\s*\{[^}]*font-variant-numeric:\s*tabular-nums/);
    expect(css).toMatch(/\.titleRow::before\s*\{[^}]*color:\s*var\(--dh-api-muted\)/);
    expect(css).toMatch(/\.titleRow::before\s*\{[^}]*font-family:\s*var\(--moss-font-tabular\)/);
  });

  it("外接 var() 没有回退值：漏配时序号消失，而不是静默打印本原语编号域的号", () => {
    // 这是本次改动里最容易被「顺手补个回退更稳妥」改坏的一条。写了回退，忘传
    // counter 名的页面会打印 layoutSectionHead 的序号——一个看上去完全正常、
    // 实际来自另一个编号域的错号。
    expect(css).not.toMatch(/var\(--layout-section-head-counter\s*,/);
  });

  it("increment: true 时递增位落到分区头上，且规则特异性高于关闭递增那条", () => {
    mountPageStyleSheet(".macro-toolkit-page__main { counter-reset: mt-section; }");
    render(
      <SectionHead
        testId="head"
        title="策略展示"
        numbered={{ counter: "mt-section", increment: true }}
      />,
    );
    expect(screen.getByTestId("head")).toHaveAttribute("data-counter-increment", "self");
    expect(css).toMatch(
      /\.head\[data-numbered="external"\]\[data-counter-increment="self"\]\s*\{[^}]*counter-increment:\s*var\(--layout-section-head-counter\)/,
    );
    // 两个属性选择器 > 一个，特异性天然更高；顺序上也在关闭规则之后，两重保险。
    expect(css.indexOf('[data-counter-increment="self"]')).toBeGreaterThan(
      css.indexOf('.head[data-numbered="external"] {'),
    );
  });

  it("外接态不再告警缺 stack 容器（那时编号域本来就不该是本原语的）", () => {
    mountPageStyleSheet(COMPLETE_PAGE_COUNTER_CSS);
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(<SectionHead testId="head" title="策略展示" numbered={{ counter: "mt-section" }} />);
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });

  it("外接 counter 名非法时不设自定义属性并告警", () => {
    mountPageStyleSheet(COMPLETE_PAGE_COUNTER_CSS);
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    for (const [index, counter] of ["mt section", "--mt-section", "none", "9lives", ""].entries()) {
      render(<SectionHead testId={`bad-${index}`} title="策略展示" numbered={{ counter }} />);
      const head = screen.getByTestId(`bad-${index}`);
      expect(head).toHaveAttribute("data-numbered", "external");
      expect(head.getAttribute("style")).toBeNull();
    }
    expect(warn).toHaveBeenCalledTimes(5);
    expect(String(warn.mock.calls[0]?.[0])).toContain("custom-ident");
    warn.mockRestore();
  });

  it("外接 counter 在页面 CSS 里没有起点（counter-reset）时告警", () => {
    // 缺 counter-reset 与缺 stack 容器是同一个坑：浏览器在元素自身隐式建计数器，
    // 号照打，只是每个头各从 01 开始。
    mountPageStyleSheet(".macro-toolkit-section { counter-increment: mt-section; }");
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(<SectionHead testId="head" title="策略展示" numbered={{ counter: "mt-section" }} />);
    expect(warn).toHaveBeenCalledTimes(1);
    expect(String(warn.mock.calls[0]?.[0])).toContain("counter-reset");
    warn.mockRestore();
  });

  it("外接 counter 没有任何 counter-increment 且未开 increment 时告警", () => {
    // 这个配置下所有分区头会打印同一个号，是最像「正常」的错号。
    mountPageStyleSheet(".macro-toolkit-page__main { counter-reset: mt-section; }");
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(<SectionHead testId="head" title="策略展示" numbered={{ counter: "mt-section" }} />);
    expect(warn).toHaveBeenCalledTimes(1);
    expect(String(warn.mock.calls[0]?.[0])).toContain("counter-increment");
    warn.mockRestore();
  });

  it("increment: true 时不再要求页面 CSS 里有 counter-increment（递增位在自己身上）", () => {
    mountPageStyleSheet(".macro-toolkit-page__main { counter-reset: mt-section; }");
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(
      <SectionHead
        testId="head"
        title="策略展示"
        numbered={{ counter: "mt-section", increment: true }}
      />,
    );
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });

  it("自检读 @media 里的声明，也不把同前缀的别名 counter 当成自己那个", () => {
    mountPageStyleSheet(`
      @media (min-width: 1px) {
        .macro-toolkit-page__main { counter-reset: mt-section; }
        .macro-toolkit-section { counter-increment: mt-section; }
      }
    `);
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(<SectionHead testId="ok" title="媒体查询里配齐" numbered={{ counter: "mt-section" }} />);
    expect(warn).not.toHaveBeenCalled();
    // mt-section-ops 只是名字以 mt-section 开头，不能被算作已配置。
    render(<SectionHead testId="alias" title="别名" numbered={{ counter: "mt-section-ops" }} />);
    expect(warn).toHaveBeenCalledTimes(2);
    warn.mockRestore();
  });

  it("一张样式表都读不到时不下结论（避免样式尚未注入阶段误报）", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(<SectionHead testId="head" title="策略展示" numbered={{ counter: "mt-section" }} />);
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });
});

describe("SectionHead 分类眉标（缺口二）", () => {
  it("category 渲染在标题行首，排在标题之前，且不进入 h2 的可访问名", () => {
    render(<SectionHead testId="head" title="策略展示" category="策略" />);
    const head = screen.getByTestId("head");
    const titleRow = head.querySelector(`.${styles.titleRow}`);
    expect(titleRow?.firstElementChild).toHaveTextContent("策略");
    expect(titleRow?.firstElementChild).toHaveClass(styles.category);
    // 编号是 .titleRow::before，恒排在第一个 DOM 子元素之前，于是渲染次序天然是
    // 「编号 → 分类 → 标题」，不需要页面参与排布。
    expect(head.querySelector(`.${styles.category}`)?.nextElementSibling?.tagName).toBe("H2");
    // 分类词是节题网格里的独立槽位，不能污染标题的可访问名。
    expect(screen.getByRole("heading", { level: 2, name: "策略展示" })).toBeInTheDocument();
  });

  it("category 与编号之间不插 ·（单行的 · 配额留给 meta）", () => {
    render(
      <SectionHead
        testId="head"
        title="策略展示"
        category="策略"
        meta={[
          { label: "报告日", value: "2026-08-26" },
          { label: "口径", value: "正式" },
        ]}
      />,
    );
    const head = screen.getByTestId("head");
    const dotCount = (head.textContent?.match(/·/g) ?? []).length;
    expect(dotCount).toBe(1);
  });

  it("category 未传/空串/纯空白时不渲染、不占版面", () => {
    const { rerender } = render(<SectionHead testId="head" title="策略展示" />);
    const baselineChildren = screen.getByTestId("head").querySelector(`.${styles.titleRow}`)
      ?.childElementCount;
    for (const category of ["", "   "]) {
      rerender(<SectionHead testId="head" title="策略展示" category={category} />);
      const titleRow = screen.getByTestId("head").querySelector(`.${styles.titleRow}`);
      expect(titleRow?.querySelector(`.${styles.category}`)).toBeNull();
      expect(titleRow?.childElementCount).toBe(baselineChildren);
    }
  });

  it("CSS：分类眉标 11px / muted / 400，弱于 14px 600 的标题，不强于 note", () => {
    expect(css).toMatch(/\.category\s*\{[^}]*font-size:\s*11px/);
    expect(css).toMatch(/\.category\s*\{[^}]*font-weight:\s*400/);
    expect(css).toMatch(/\.category\s*\{[^}]*color:\s*var\(--dh-api-muted\)/);
    // note 是 11px muted；分类词不得比它更响（上一轮映射进 12px 的 meta 就是在这里翻车的）。
    expect(css).toMatch(/\.note\s*\{[^}]*font-size:\s*11px/);
    expect(css).not.toMatch(/\.category\s*\{[^}]*var\(--dh-api-soft\)/);
    expect(css).not.toMatch(/\.category\s*\{[^}]*letter-spacing/);
  });
});

describe("SectionHead 受控间距（缺口三）", () => {
  it("contentGap 缺省不写属性，DOM 与既有实现逐字一致", () => {
    render(<SectionHead testId="head" title="标题" />);
    const head = screen.getByTestId("head");
    expect(head).not.toHaveAttribute("data-content-gap");
    expect(head).not.toHaveAttribute("data-numbered");
    expect(head).not.toHaveAttribute("data-counter-increment");
    expect(head.getAttribute("style")).toBeNull();
  });

  it("contentGap 各档位写出对应属性，CSS 里各有一条外边距规则", () => {
    for (const gap of ["tight", "flush"] as const) {
      render(<SectionHead testId={`head-${gap}`} title="标题" contentGap={gap} />);
      expect(screen.getByTestId(`head-${gap}`)).toHaveAttribute("data-content-gap", gap);
    }
    // market-data 的消费方要的就是 8px 这一档（老组件靠 style 注入 marginBottom: 8）。
    expect(css).toMatch(/\.head\[data-content-gap="tight"\]\s*\{[^}]*margin-bottom:\s*8px/);
    expect(css).toMatch(/\.head\[data-content-gap="flush"\]\s*\{[^}]*margin-bottom:\s*0/);
    expect(css).toMatch(/\.head\s*\{[^}]*margin-bottom:\s*12px/);
  });

  it("CSS：档位只动 margin-bottom，不动 padding-bottom 与发丝底线", () => {
    const tierBodies = [
      ...css.matchAll(/\.head\[data-content-gap="(?:tight|flush)"\]\s*\{([^}]*)\}/g),
    ].map((match) => match[1]);
    expect(tierBodies).toHaveLength(2);
    for (const body of tierBodies) {
      const declaredProperties = [...body.matchAll(/([a-z-]+)\s*:/g)].map((match) => match[1]);
      expect(declaredProperties).toEqual(["margin-bottom"]);
    }
  });

  it("contentGap 是闭合枚举，没有任意数值/任意样式的旁路", () => {
    // 枚举以外的值连编译都过不去；这里锁的是「CSS 侧也只认这几档」。
    const tierValues = [...css.matchAll(/\[data-content-gap="([a-z]+)"\]/g)].map(
      (match) => match[1],
    );
    expect(new Set(tierValues)).toEqual(new Set(["tight", "flush"]));
  });
});

describe("SectionHead 向后兼容（bond-dashboard 在产使用）", () => {
  it("numbered 缺省与 numbered={false} 的 DOM 输出不因新能力改变", () => {
    render(
      <div className={SECTION_HEAD_STACK_CLASSNAME}>
        <SectionHead testId="default" title="当日结论" />
        <SectionHead testId="unnumbered" title="面板卡头" numbered={false} />
      </div>,
    );
    const numbered = screen.getByTestId("default");
    expect(numbered).not.toHaveAttribute("data-numbered");
    expect(numbered.getAttribute("style")).toBeNull();
    expect(numbered).not.toHaveAttribute("data-counter-increment");
    expect(numbered).not.toHaveAttribute("data-content-gap");

    const unnumbered = screen.getByTestId("unnumbered");
    expect(unnumbered).toHaveAttribute("data-numbered", "false");
    expect(unnumbered.getAttribute("style")).toBeNull();
    expect(unnumbered).not.toHaveAttribute("data-counter-increment");
    expect(unnumbered).not.toHaveAttribute("data-content-gap");
  });

  it("三个新槽位全部缺省时，标题行的子元素与既有实现一致", () => {
    render(<SectionHead testId="head" title="当日结论" state={{ label: "读取中", tone: "loading" }} />);
    const titleRow = screen.getByTestId("head").querySelector(`.${styles.titleRow}`);
    expect([...(titleRow?.children ?? [])].map((child) => child.tagName)).toEqual([
      "H2",
      "SPAN",
      "SPAN",
    ]);
  });
});
