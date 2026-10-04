import { useEffect, useRef, type CSSProperties, type ReactNode, type RefObject } from "react";

import { EM_DASH } from "../../utils/format";
import styles from "./SectionHead.module.css";

/**
 * SectionHead 原语：编号分区头。
 *
 * 用法：把要编号的一串分区包在一个共同的祖先元素里，并给它加上从本文件导出的
 * `SECTION_HEAD_STACK_CLASSNAME`；每个分区的头部渲染一个 `<SectionHead>`。
 * 序号完全由 CSS counter 生成（容器 counter-reset、头部 counter-increment），
 * 组件内部不做任何手写编号逻辑；某个分区因数据缺失整体不渲染 `<SectionHead>`
 * 时，后续分区编号自动顺移，不会跳号。
 *
 * ```tsx
 * import SectionHead, { SECTION_HEAD_STACK_CLASSNAME } from ".../SectionHead";
 *
 * <div className={SECTION_HEAD_STACK_CLASSNAME}>
 *   <section>
 *     <SectionHead title="当日结论" />
 *     ...
 *   </section>
 *   {hasRiskSection && (
 *     <section>
 *       <SectionHead title="风险概览" />
 *       ...
 *     </section>
 *   )}
 * </div>
 * ```
 *
 * 缺容器时的行为是**静默错号而不是缺号**：CSS Lists 规范规定，`counter-increment`
 * 找不到祖先 `counter-reset` 时会在元素自身隐式建计数器，作用域是「自身 + 后代 +
 * 后续兄弟」。于是序号照常打印，但每个不互为兄弟的分区头各建各的计数器，实测
 * 会渲染成 01 / 01。深色主题契约测试对此完全不敏感（错号状态下 38 条依然全绿），
 * 所以组件在开发环境自检祖先链，把这个隐式约定变成显式告警。不需要编号的场景
 * 传 `numbered={false}`，序号不打印、自检也不触发。
 *
 * 编号还有第三种来源：页面自己的计数器（`numbered={{ counter: "mt-section" }}`）。
 * 二值的 `numbered` 挡死了一类页面的渐进迁移——`macro-toolkit` 全页 19 个分区共用
 * 一个 `mt-section` 计数器，只迁一部分头到本原语时，剩下的头不再打印序号，序列
 * 就断成 03 / 09 / 14 / 18 这样的孤立编号，于是这类页面只能「全迁或不迁」。外接
 * 模式让分区头加入页面既有的编号域：**编号来源**（counter 名）由使用方给出，
 * **编号样式**（11px 等宽 tabular muted + `decimal-leading-zero`）仍然只由本原语
 * 的 CSS module 定义，使用方拿不到改样式的口子。
 */

export type SectionStateTone = "loading" | "error" | "empty" | "stale" | "partial";

export type SectionState = {
  label: string;
  tone: SectionStateTone;
} | null;

export type SectionMetaField = {
  label: string;
  value: string;
  /** 完整口径/来源说明；缺省回退为 "label value"。 */
  title?: string;
};

/**
 * 外接编号域：分区头加入页面自己的 CSS counter，而不是本原语的编号域。
 */
export type SectionHeadExternalCounter = {
  /**
   * 页面 CSS 里那个计数器的名字，必须与页面 `counter-reset` / `counter-increment`
   * 用的标识符逐字一致（CSS `<custom-ident>`，例如 `"mt-section"`）。
   */
  counter: string;
  /**
   * 递增位是否落在分区头自己身上。缺省 `false`：递增由页面既有规则负责（通常挂
   * 在分区容器上，如 `.macro-toolkit-section { counter-increment: mt-section }`），
   * 分区头只负责打印当前值。**这正是混合编号域能连续的原因**——容器照常递增，
   * 于是同一页里没迁完的老分区头与已迁的 `SectionHead` 共用一条连续序列。
   * 递增位本来就该落在分区头上的页面传 `true`。
   */
  increment?: boolean;
};

/** 编号来源：本原语的 stack 编号域 / 不编号 / 页面自己的编号域。 */
export type SectionHeadNumbering = boolean | SectionHeadExternalCounter;

/**
 * 分区头到分区内容的间距档位。枚举而不是任意值：任意 style/className 透传会
 * 把刚拆掉的耦合装回去（实测页面会用 `> div`、`span[style] + h2[style]` 这类
 * 结构耦合选择器从外部改组件，props 层看不见、不报错、失效无声）。
 */
export type SectionHeadContentGap = "default" | "tight" | "flush";

export type SectionHeadProps = {
  title: string;
  /**
   * 分类眉标（「策略」「席位」「危机证据」这类有区分度的分类词），不是标题的
   * 装饰性复述。空串/纯空白/未传时整个槽位不渲染，不占版面。
   *
   * 刻意不叫 `eyebrow`，也不复刻老 `PageSectionLead` 的大写宽字距眉标：DESIGN.md
   * §3 已把大写宽字距徽标收回给状态/口径徽标，而且 `text-transform: uppercase`
   * 在中文标签上本来就无效。
   */
  category?: string;
  /** ready（null/undefined）时不渲染状态位，不占版面。 */
  state?: SectionState;
  /** 字段数组；"·" 拼接与配额、竖线分栏全部由组件内部推导，不接受预拼字符串。 */
  meta?: SectionMetaField[];
  note?: string;
  /** 仅此处的可交互元素允许使用 accent 色。 */
  actions?: ReactNode;
  /**
   * 编号来源。默认 `true`，走本原语的 CSS counter，需要外层有
   * `SECTION_HEAD_STACK_CLASSNAME` 容器界定编号域。用在不编号的场景（面板卡头、
   * 复用老组件的过渡实现）时传 `false`，序号不打印、也不占用编号域。传对象则
   * 加入页面自己的编号域，见 `SectionHeadExternalCounter`。
   */
  numbered?: SectionHeadNumbering;
  /** 分区头到分区内容的间距档位，默认 `"default"`（12px）。 */
  contentGap?: SectionHeadContentGap;
  /**
   * 标题在窄屏的展示方式。默认 `"truncate"` 保持单行省略；业务限定词或日期不可
   * 隐藏时传 `"wrap"`，允许标题完整换行，但仍不开放任意样式覆盖。
   */
  titleWrap?: "truncate" | "wrap";
  /**
   * 落到 `<h2>` 上的 id，供外层 `<section aria-labelledby>` 引用，给分区一个
   * region 可访问名。这是锚点不是样式口子，不违反「不开放任意样式注入」——
   * 缺它会让所有用 `aria-labelledby` 指向标题的分区无法迁移（实测因此整页
   * 排除过一个路由）。
   */
  titleId?: string;
  testId?: string;
};

/**
 * 外接编号域把 counter 名放在这个自定义属性上，本原语的 CSS 规则只从这里读名字。
 * 导出是为了让页面/测试能引用同一个字面量，不是让页面自己去设它——设值口子只有
 * `numbered={{ counter }}` 这一个。
 */
export const SECTION_HEAD_COUNTER_CSS_VAR = "--layout-section-head-counter";

/** 单行元信息最多 1 个 "·"：<=2 个字段才允许内联拼接。 */
const META_INLINE_LIMIT = 2;

const META_DOT = "·";

/**
 * 契约漂移（后端少返回一个字段）会让 `value` 在运行时变成 undefined；分区头是
 * 26 个域共用的原语，不能因为一个 meta 字段缺失把整页抛进错误边界。缺值统一
 * 按项目惯例渲染为 EM_DASH，而不是把 "undefined" 打进正文或 title。
 */
function normalizeMetaField(field: SectionMetaField): SectionMetaField {
  const label = typeof field.label === "string" ? field.label : String(field.label ?? "");
  const value =
    field.value === null || field.value === undefined || field.value === ""
      ? EM_DASH
      : typeof field.value === "string"
        ? field.value
        : String(field.value);
  return { ...field, label, value };
}

/**
 * 字段自带 "·" 时内联拼接会突破 §7 的单行一个配额（组件插的那个之外还有字段
 * 自己的），改走零 "·" 的竖线分栏。否则「配额在组件内」只能防住字段数量，
 * 防不住字段内容。
 */
function metaCarriesOwnDot(fields: SectionMetaField[]): boolean {
  return fields.some(
    (field) => field.label.includes(META_DOT) || field.value.includes(META_DOT),
  );
}

function shouldInlineMeta(fields: SectionMetaField[]): boolean {
  return fields.length <= META_INLINE_LIMIT && !metaCarriesOwnDot(fields);
}

function metaFieldTitle(field: SectionMetaField): string {
  return field.title ?? `${field.label} ${field.value}`;
}

function MetaInline({ fields }: { fields: SectionMetaField[] }) {
  return (
    <p className={styles.metaInline}>
      {fields.map((field, index) => (
        <span key={field.label} className={styles.metaInlineItem} title={metaFieldTitle(field)}>
          {index > 0 ? (
            <span className={styles.metaDot} aria-hidden="true">
              {META_DOT}
            </span>
          ) : null}
          <span className={styles.metaLabel}>{field.label}</span>
          {" "}
          <span className={styles.metaValue}>{field.value}</span>
        </span>
      ))}
    </p>
  );
}

function MetaGrid({ fields }: { fields: SectionMetaField[] }) {
  return (
    <div className={styles.metaGrid}>
      {fields.map((field) => (
        <span key={field.label} className={styles.metaCell} title={metaFieldTitle(field)}>
          <span className={styles.metaLabel}>{field.label}</span>
          {" "}
          <span className={styles.metaValue}>{field.value}</span>
        </span>
      ))}
    </div>
  );
}

type NumberingMode = "stack" | "none" | "external";

type ResolvedNumbering = {
  mode: NumberingMode;
  /** 合法的外接 counter 名；非外接模式或名字非法时为 null。 */
  counter: string | null;
  /** 外接模式下递增位是否落在分区头自己身上。 */
  incrementHere: boolean;
};

/** CSS `<custom-ident>`：字母或下划线开头（允许一个前导连字符），后接字母、数字、下划线、连字符。 */
const CSS_CUSTOM_IDENT = /^-?[A-Za-z_][A-Za-z0-9_-]*$/;

/** CSS 保留字不能当 counter 名（`counter(none, …)` 是语法错误，不是「不编号」）。 */
const COUNTER_NAME_KEYWORDS = new Set([
  "none",
  "inherit",
  "initial",
  "unset",
  "revert",
  "revert-layer",
]);

function isCounterName(value: string): boolean {
  return CSS_CUSTOM_IDENT.test(value) && !COUNTER_NAME_KEYWORDS.has(value.toLowerCase());
}

function resolveNumbering(numbered: SectionHeadNumbering): ResolvedNumbering {
  if (numbered === true) return { mode: "stack", counter: null, incrementHere: false };
  if (numbered === false) return { mode: "none", counter: null, incrementHere: false };
  const counter = numbered.counter.trim();
  return {
    mode: "external",
    counter: isCounterName(counter) ? counter : null,
    incrementHere: numbered.increment === true,
  };
}

const NUMBERING_DATA_ATTRIBUTE: Record<NumberingMode, string | undefined> = {
  // 默认编号态不写属性：DOM 与外接/不编号两态之外保持逐字不变。
  stack: undefined,
  none: "false",
  external: "external",
};

type SectionHeadStyle = CSSProperties & Record<`--${string}`, string | number>;

/**
 * 唯一的内联样式：把外接 counter 名交给 CSS。名字非法时什么都不设，CSS 侧
 * `counter(var(--layout-section-head-counter), …)` 在计算值阶段失效，::before
 * 直接不生成——不会退化成打印本原语自己的编号域序号。
 */
function counterNameStyle(counter: string | null): SectionHeadStyle | undefined {
  if (counter === null) return undefined;
  return { [SECTION_HEAD_COUNTER_CSS_VAR]: counter };
}

function identPattern(ident: string): RegExp {
  const escaped = ident.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(?<![\\w-])${escaped}(?![\\w-])`);
}

type CounterCssFacts = {
  /**
   * 这个环境确实加载了带编号的 CSS。判据不是「读到了样式表」——jsdom 下测试框架
   * 会注入零星样式表，而页面 .css 从不注入，那样每个外接编号头都会误报。判据是
   * 「文档里存在任意一条 counter-* 声明」：真实浏览器里本原语自己的 module.css
   * 就带 counter-increment，一条都读不到就说明编号 CSS 整体缺席，不该下结论。
   */
  readable: boolean;
  /** 编号域有起点（counter-reset / counter-set）。 */
  hasOrigin: boolean;
  /** 有规则在递增它。 */
  hasIncrement: boolean;
};

/**
 * 扫已加载样式表里对某个 counter 名的声明。读 `rule.style` 的具体声明而不是把
 * 整张表 `cssText` 序列化出来做正则：后者在 5000 行量级的页面 CSS 上每次挂载都
 * 要重新序列化一遍，前者是 O(规则数) 的属性查表。
 */
function collectCounterCssFacts(counter: string): CounterCssFacts {
  const pattern = identPattern(counter);
  const facts: CounterCssFacts = { readable: false, hasOrigin: false, hasIncrement: false };

  const visit = (rules: CSSRuleList | undefined) => {
    if (!rules) return;
    for (const rule of Array.from(rules)) {
      const declaration = (rule as CSSStyleRule).style as CSSStyleDeclaration | undefined;
      if (declaration) {
        const reset = declaration.getPropertyValue("counter-reset");
        const set = declaration.getPropertyValue("counter-set");
        const increment = declaration.getPropertyValue("counter-increment");
        if (reset || set || increment) facts.readable = true;
        if (!facts.hasOrigin) {
          facts.hasOrigin = pattern.test(reset) || pattern.test(set);
        }
        if (!facts.hasIncrement) {
          facts.hasIncrement = pattern.test(increment);
        }
      }
      // @media / @supports 等分组规则里的声明同样算数。
      visit((rule as CSSGroupingRule).cssRules);
    }
  };

  for (const sheet of Array.from(document.styleSheets)) {
    let rules: CSSRuleList;
    try {
      rules = sheet.cssRules;
    } catch {
      // 跨域样式表读不到 cssRules，跳过。
      continue;
    }
    visit(rules);
  }
  return facts;
}

/**
 * 开发期自检：编号出错的三种方式都是**静默错号而不是缺号**，而没有任何自动化
 * 护栏能抓到它们（深色契约、a11y、几何锁都不读 ::before 的 counter 值）。这里在
 * 挂载时把三种误用变成控制台可见的告警：
 *
 * 1. 本原语编号域缺 stack 容器（浏览器隐式建计数器，同页多个头各自从 01 开始）；
 * 2. 外接模式给的 counter 名不是合法 `<custom-ident>`；
 * 3. 外接模式给了名字但页面 CSS 那半边没配齐（没有编号域起点，或没人递增）。
 *
 * 外接模式不再检查 stack 容器——那时编号域本来就不该是本原语的。生产环境不执行，
 * 永不阻断渲染。
 *
 * 三项检查都先要求「这个环境真的加载了编号 CSS」。jsdom 下页面 .css 从不注入，
 * 单独渲染一个头也本来就不会有 stack 容器，无条件告警会让每个组件测试刷屏，
 * 把真告警淹掉。
 */
function useNumberingGuard(
  mode: NumberingMode,
  counter: string | null,
  incrementHere: boolean,
  ref: RefObject<HTMLElement | null>,
): void {
  useEffect(() => {
    if (!import.meta.env.DEV || mode === "none") return;
    const node = ref.current;
    if (!node) return;
    const label = node.querySelector("h2")?.textContent ?? "(无标题)";

    // 名字非法是纯代码错误，与样式是否加载无关，先判且不受下面的 gate 影响。
    if (mode === "external" && counter === null) {
      console.warn(
        `[SectionHead] 「${label}」的 numbered.counter 不是合法的 CSS <custom-ident>，序号不会渲染。` +
          "counter 名要与页面 CSS 里 counter-reset / counter-increment 用的标识符逐字一致，" +
          '例如 numbered={{ counter: "mt-section" }}。',
      );
      return;
    }

    const facts = collectCounterCssFacts(counter ?? "");
    if (!facts.readable) return;

    if (mode === "stack") {
      if (node.closest(`.${styles.stack}`)) return;
      console.warn(
        `[SectionHead] 「${label}」缺少 ` +
          "SECTION_HEAD_STACK_CLASSNAME 祖先容器。CSS counter 会在本元素自身隐式建计数器，" +
          "导致同页多个分区头各自从 01 开始（静默错号，不是缺号）。请把同一串分区包进一个 " +
          "stack 容器；确实不需要编号时传 numbered={false}。",
      );
      return;
    }

    if (counter === null) return;

    if (!facts.hasOrigin) {
      console.warn(
        `[SectionHead] 「${label}」外接计数器 ${counter}：已加载样式里找不到任何 counter-reset / ` +
          `counter-set ${counter}，这个编号域没有起点。浏览器会在元素自身隐式建计数器，` +
          "结果同样是静默错号而不是缺号。请在页面 CSS 里给编号域容器加 counter-reset。",
      );
    }
    if (!incrementHere && !facts.hasIncrement) {
      console.warn(
        `[SectionHead] 「${label}」外接计数器 ${counter}：已加载样式里没有任何 counter-increment ` +
          `${counter}，而 numbered.increment 也没开，于是同域内每个分区头都会打印同一个号。` +
          "递增位在分区容器上时保持默认，递增位应该落在分区头自己身上时传 increment: true。",
      );
    }
  }, [mode, counter, incrementHere, ref]);
}

export default function SectionHead({
  title,
  category,
  state,
  meta,
  note,
  actions,
  numbered = true,
  contentGap = "default",
  titleWrap = "truncate",
  titleId,
  testId,
}: SectionHeadProps) {
  const metaFields = meta && meta.length > 0 ? meta.map(normalizeMetaField) : null;
  const categoryLabel = category?.trim() ? category.trim() : null;
  const { mode, counter, incrementHere } = resolveNumbering(numbered);
  const headRef = useRef<HTMLElement>(null);
  useNumberingGuard(mode, counter, incrementHere, headRef);

  return (
    <header
      ref={headRef}
      className={styles.head}
      data-testid={testId}
      data-numbered={NUMBERING_DATA_ATTRIBUTE[mode]}
      data-counter-increment={mode === "external" && incrementHere ? "self" : undefined}
      data-content-gap={contentGap === "default" ? undefined : contentGap}
      data-title-wrap={titleWrap === "wrap" ? "wrap" : undefined}
      style={counterNameStyle(mode === "external" ? counter : null)}
    >
      <div className={styles.titleRow}>
        {/* 分类眉标与编号同处标题行首：编号是 .titleRow::before，所以它永远排在
            分类词之前，两者一起构成「01 策略 标题」的单行基线布局。 */}
        {categoryLabel ? <span className={styles.category}>{categoryLabel}</span> : null}
        <h2 className={styles.title} id={titleId} title={title}>
          {title}
        </h2>
        <span className={styles.spacer} />
        {state ? (
          <span className={styles.state} data-tone={state.tone} role="status">
            <span className={styles.stateDot} aria-hidden="true" />
            {state.label}
          </span>
        ) : null}
        {actions ? <div className={styles.actions}>{actions}</div> : null}
      </div>

      {metaFields ? (
        shouldInlineMeta(metaFields) ? (
          <MetaInline fields={metaFields} />
        ) : (
          <MetaGrid fields={metaFields} />
        )
      ) : null}

      {note ? <p className={styles.note}>{note}</p> : null}
    </header>
  );
}

/** 挂在编号分区头的共同祖先上，作为 CSS counter 的重置作用域。 */
export const SECTION_HEAD_STACK_CLASSNAME = styles.stack;
