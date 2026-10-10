/*
 * DataTable —— 轻量只读表格原语（Nocturne 深色终端）。
 *
 * 存在理由：DESIGN.md 的表格密度纪律（表头 12px/500、表体 12px、发丝底边、
 * 数值列右对齐等宽）此前在每个页面用 `.ant-table-*` 覆盖重写一遍。antd
 * cssinjs 运行时注入的特异度 0-4-0 且注入顺序不可控，页面只能三写类名提权
 * 再补 !important。本组件把密度做成组件默认值：零 antd 依赖、零 !important、
 * 零内联 style，页面不再需要一行 antd 覆盖。
 *
 * 适用范围：只读业务表（数十到数百行、无排序/无分页/无虚拟滚动）。需要虚拟
 * 滚动、列排序、固定列、行选择、单元格编辑的表继续用 AG Grid。
 */
import { useId, useState, type ReactNode } from "react";

import type { Numeric } from "../../api/contracts";
import { EM_DASH, numericRaw } from "../../pageModel";
import { toneForStatus, type Tone } from "../../utils/tone";

import styles from "./DataTable.module.css";

export type ColumnAlign = "text" | "numeric";

export type DataTableColumn<Row> = {
  /** 列标识；同时是 `render` 缺省时从行对象取值的字段名。 */
  key: string;
  title: string;
  /** `numeric` 自动右对齐 + 等宽字体栈 + tabular-nums（DESIGN.md §3）。 */
  align?: ColumnAlign;
  /** 列题单位后缀，渲染为 `标题(亿)`；写在标题里也可以，但分开更好排版。 */
  unit?: string | null;
  /** 走 `<col width>`（HTML 原生列宽，避免内联 style）；横向滚动模式下百分比只是提示。 */
  width?: number | string;
  /** 缺省从 `row[key]` 取值，见 `defaultCellContent` 的取值纪律。 */
  render?: (row: Row) => ReactNode;
  /** 列级口径注（如「Top10 内占比」）。收进列头 `title`，不占正文版面（DESIGN.md §6）。 */
  note?: string;
  /**
   * 允许该列列头换行；默认 `false`（列头永不换行，是既有保证，不因本项退化）。
   * 折行只发生在显式声明的列上，用于压低多列窄断点下宽表的最小宽度——列头不折行
   * 会把「最长表头文字宽度」变成硬约束，折行后同一列头可以用两行换取更窄的列。
   */
  headerWrap?: boolean;
  /**
   * 单元格单行省略 + 完整值 `title` 提示（对齐 antd `ellipsis: true` 的效果），
   * 需要配合 `width` 使用。声明本项的列会让整张表切到 `table-layout: fixed`
   * （否则浏览器自动表格布局会按不折行文本的内容宽度撑开列，省略永远不会触发），
   * 因此会连带影响同表内未设 `width` 的其它列，退化为按剩余空间平分而不是按内容
   * 撑开。不声明（默认）不受任何影响。
   */
  ellipsis?: boolean;
};

export type DataTableStatus = "ready" | "loading" | "empty" | "error" | "stale" | "partial";

export type DataTableEmptyPolicy =
  /** 空即收缩为「暂无数据」，不区分「真空」与「envelope 未到达」。 */
  | "collapse"
  /** 只有真实空 payload 收缩；`rows === undefined` 保留骨架高度防重排。 */
  | "skeleton-until-envelope";

/** 目前只有 compact；保留字面量联合作为未来扩展位。 */
export type DataTableDensity = "compact";

/**
 * 整列缺失的原因说明。DESIGN.md §6：明细行只留安静的 `—`，原因说明在表头
 * 说明区出现一次。组件按 `reason` 去重，不提供任何逐行复述原因的通道。
 */
export type DataTableColumnNotice = {
  columnKey: string;
  reason: string;
};

/** 合计行：按 `column.key` 取汇总单元格，缺省列渲染 EM_DASH。 */
export type DataTableSummaryRow = Readonly<Record<string, ReactNode>>;

export type DataTableProps<Row> = {
  /** `undefined` = envelope 未到达；`[]` = 真实空 payload。两者行为由 `emptyPolicy` 区分。 */
  rows: Row[] | undefined;
  rowKey: keyof Row | ((row: Row) => string);
  columns: readonly DataTableColumn<Row>[];
  status?: DataTableStatus;
  emptyPolicy?: DataTableEmptyPolicy;
  emptyMessage?: string;
  errorMessage?: string;
  /** 覆盖 loading/stale/partial 行内状态行的默认文案（如「回退到 2026-08-25 报告日」）。 */
  statusMessage?: string;
  columnNotices?: readonly DataTableColumnNotice[];
  summaryRow?: DataTableSummaryRow;
  density?: DataTableDensity;
  /** Top N + 「展开全部」；不传即全量渲染。 */
  maxRows?: number;
  /** 骨架占位行数，用于逼近真实高度防重排（DESIGN.md §6）。 */
  skeletonRows?: number;
  /** 表格无可见标题时的可访问名。 */
  ariaLabel?: string;
  testId?: string;
  /**
   * 行级 testId：按行数据算出该 `<tr>` 的完整 `data-testid`。不传时 `<tr>` 不挂
   * `data-testid`（与现状逐字一致）；对单行返回 `undefined` 可以让该行不挂锚点。
   *
   * 要求调用方给出完整字符串，而不是「表级 testId + 自动拼接后缀」的隐式约定：
   * 跨页金样本 / Playwright spec 引用的行级 testId 命名规则各页不同且不能改名
   * （见 `bond-dashboard-risk-row-<key>`），DataTable 不应该替调用方发明新命名法。
   */
  rowTestId?: (row: Row, index: number) => string | undefined;
  /**
   * 行级 `data-*` 属性：按行数据决定整行的呈现开关，典型用途是「这一行是延后/
   * 诚实态，整行降权变色」——`macro-observation` 的数据健康修复项表就断言
   * `data-deferred="true"`，此前没有这个口子只能保留原生 `<table>`。
   *
   * 只收 `data-*`，不是任意 props 注入口：原语的价值在于它能保证的东西
   * （对齐、缺值、状态），开放 className/style 会让每个调用方各自绕过这些保证。
   * 不要用它挂 `data-testid`——那是 `rowTestId` 的职责，同时给会以后者为准。
   */
  rowAttrs?: (row: Row, index: number) => Record<`data-${string}`, string | undefined> | undefined;
  /**
   * 把某一列渲染成 `<th scope="row">` 而不是 `<td>`，即"这列是这一行的名字"。
   * 缺省全部渲染为 `<td>`（与现状逐字一致）。
   *
   * 存在的理由是可访问性不能因为迁移而退化：屏幕阅读器靠行头把「142 摊余成本
   * 债权投资 / 期末余额 / 1,234」念成一句话，丢了行头就只剩孤立数字。
   * `market-finance` 的证据对照表正因为原语没有这个能力而没有迁移。
   */
  rowHeaderKey?: string;
};

/** 组件解析出的渲染形态，暴露在根节点 `data-view` 上供页面与测试断言。 */
type DataTableView = "rows" | "skeleton" | "empty" | "error";

/**
 * 状态 → tone。error/stale 委托 `toneForStatus`（tone.ts 是 tone 词表的单一来源）；
 * partial 不在该表内，按 DESIGN.md §6「部分缺失」归警戒色。
 * 具体色值不在这里，落在 DataTable.module.css 的 `[data-tone]` 规则上，
 * 与 `TONE_DH_CSS_VAR` 由 DataTable.test.tsx 值级互锁。
 */
const STATUS_TONE: Record<Exclude<DataTableStatus, "ready">, Tone> = {
  loading: "neutral",
  empty: "neutral",
  error: toneForStatus("error"),
  stale: toneForStatus("stale"),
  partial: "warning",
};

const INLINE_STATUS_TEXT: Record<"loading" | "stale" | "partial", string> = {
  loading: "数据刷新中，下方为上一次结果。",
  stale: "数据为延迟快照，不是最新报告日。",
  partial: "部分数据缺失，下方为可用部分。",
};

function isNumericValue(value: object): value is Numeric {
  const candidate = value as Partial<Numeric>;
  return (
    (candidate.raw === null || typeof candidate.raw === "number") &&
    typeof candidate.unit === "string" &&
    typeof candidate.display === "string"
  );
}

/**
 * 无 `render` 时的兜底取值。只负责「不说谎」：
 * - 治理 Numeric：raw 缺失或非有限 → EM_DASH；否则用后端已烘焙单位与精度的
 *   `display`，前端不二次换算。需要换算单位的列（元 → 亿、ratio → %）必须自带
 *   `render`，否则拿到的是后端口径而不是页面口径。
 * - 裸 number/string：原样输出，不替页面发明精度或千分位。
 * - 其他对象形状：EM_DASH，绝不出现 "[object Object]"。
 */
function defaultCellContent(value: unknown): ReactNode {
  if (value === null || value === undefined) return EM_DASH;
  if (typeof value === "object" && value !== null) {
    if (!isNumericValue(value)) return EM_DASH;
    return numericRaw(value) === null ? EM_DASH : value.display;
  }
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : EM_DASH;
  if (typeof value === "string") return value.trim() === "" ? EM_DASH : value;
  return EM_DASH;
}

function cellContent<Row>(row: Row, column: DataTableColumn<Row>): ReactNode {
  if (column.render) return column.render(row);
  /*
   * 按 column.key 动态取值：Row 是泛型、key 是 string，两者没有静态可证的索引
   * 关系。这里走 Reflect.get 而不是经 unknown 中转到 Record 的双重断言——后者
   * 绕过 noUnknownCastGuard 的护栏，需要在 tests 侧登记白名单才放行。
   */
  const value: unknown =
    row !== null && typeof row === "object" ? Reflect.get(row, column.key) : undefined;
  return defaultCellContent(value);
}

function resolveRowKey<Row>(
  row: Row,
  rowKey: keyof Row | ((row: Row) => string),
  index: number,
): string {
  const raw: unknown = typeof rowKey === "function" ? rowKey(row) : row[rowKey as keyof Row];
  const key = raw === null || raw === undefined ? "" : String(raw);
  // 后端存在空名行（组合对比已观察到），空键回退到序号，避免 React key 冲突。
  return key.trim() === "" ? `row-${index}` : key;
}

function resolveView<Row>(
  rows: Row[] | undefined,
  status: DataTableStatus,
  emptyPolicy: DataTableEmptyPolicy,
): DataTableView {
  // 有数据时永远渲染数据：error/stale/partial 走行内状态行，不用遮罩盖掉已有结果。
  if (rows !== undefined && rows.length > 0) return "rows";
  if (status === "error") return "error";
  if (status === "loading") return "skeleton";
  if (status === "empty") return "empty";
  if (rows === undefined) {
    return emptyPolicy === "skeleton-until-envelope" ? "skeleton" : "empty";
  }
  return "empty";
}

type ResolvedNotice = { reason: string; columnTitles: string[] };

function buildNotices<Row>(
  columns: readonly DataTableColumn<Row>[],
  columnNotices: readonly DataTableColumnNotice[] | undefined,
): { notices: ResolvedNotice[]; reasonByColumn: Map<string, string> } {
  const notices: ResolvedNotice[] = [];
  const reasonByColumn = new Map<string, string>();
  if (!columnNotices || columnNotices.length === 0) {
    return { notices, reasonByColumn };
  }
  const byReason = new Map<string, ResolvedNotice>();
  for (const notice of columnNotices) {
    reasonByColumn.set(notice.columnKey, notice.reason);
    let entry = byReason.get(notice.reason);
    if (!entry) {
      entry = { reason: notice.reason, columnTitles: [] };
      byReason.set(notice.reason, entry);
      notices.push(entry);
    }
    const title = columns.find((column) => column.key === notice.columnKey)?.title;
    if (title && !entry.columnTitles.includes(title)) {
      entry.columnTitles.push(title);
    }
  }
  return { notices, reasonByColumn };
}

function alignOf<Row>(column: DataTableColumn<Row>): ColumnAlign {
  return column.align ?? "text";
}

function headTitle<Row>(column: DataTableColumn<Row>, reason: string | undefined): string | undefined {
  const parts = [column.note, reason].filter((part): part is string => Boolean(part));
  return parts.length > 0 ? parts.join("；") : undefined;
}

function suffixTestId(testId: string | undefined, suffix: string): string | undefined {
  return testId === undefined ? undefined : `${testId}-${suffix}`;
}

export function DataTable<Row>({
  rows,
  rowKey,
  columns,
  status = "ready",
  emptyPolicy = "skeleton-until-envelope",
  emptyMessage = "暂无数据",
  errorMessage = "数据加载失败",
  statusMessage,
  columnNotices,
  summaryRow,
  density = "compact",
  maxRows,
  skeletonRows = 4,
  ariaLabel,
  testId,
  rowTestId,
  rowAttrs,
  rowHeaderKey,
}: DataTableProps<Row>) {
  const [expanded, setExpanded] = useState(false);
  const domId = useId();
  const bodyId = `${domId}-body`;
  const noticeId = `${domId}-notice`;

  const view = resolveView(rows, status, emptyPolicy);
  const { notices, reasonByColumn } = buildNotices(columns, columnNotices);
  // 任一列声明 ellipsis 才切 table-layout: fixed；没有列用到时保持 auto，逐字不变。
  const hasEllipsisColumn = columns.some((column) => column.ellipsis);

  const allRows = rows ?? [];
  const truncated = maxRows !== undefined && maxRows > 0 && allRows.length > maxRows;
  const visibleRows = truncated && !expanded ? allRows.slice(0, maxRows) : allRows;

  // `status="empty"` 与「有行」是互相矛盾的输入，此时以数据为准，不挂误导性的状态行。
  const inlineStatus =
    view === "rows" && status !== "ready" && status !== "empty"
      ? {
          tone: STATUS_TONE[status],
          text: statusMessage ?? (status === "error" ? errorMessage : INLINE_STATUS_TEXT[status]),
        }
      : null;

  const headRow = (
    <tr>
      {columns.map((column) => (
        <th
          key={column.key}
          scope="col"
          className={styles.headCell}
          data-align={alignOf(column)}
          data-wrap={column.headerWrap ? "true" : undefined}
          title={headTitle(column, reasonByColumn.get(column.key))}
        >
          {column.title}
          {column.unit ? <span className={styles.headUnit}>{`(${column.unit})`}</span> : null}
        </th>
      ))}
    </tr>
  );

  const colGroup = (
    <colgroup>
      {columns.map((column) => (
        <col key={column.key} width={column.width} />
      ))}
    </colgroup>
  );

  return (
    <div
      className={styles.root}
      data-testid={testId}
      data-density={density}
      data-status={status}
      data-view={view}
    >
      {notices.length > 0 ? (
        <ul className={styles.notices} id={noticeId} data-testid={suffixTestId(testId, "notices")}>
          {notices.map((notice) => (
            <li key={notice.reason} className={styles.noticeItem}>
              {notice.columnTitles.length > 0
                ? `${notice.columnTitles.join(" / ")}：${notice.reason}`
                : notice.reason}
            </li>
          ))}
        </ul>
      ) : null}

      {inlineStatus ? (
        <p
          className={styles.statusRow}
          data-tone={inlineStatus.tone}
          data-testid={suffixTestId(testId, "status")}
          role={status === "error" ? "alert" : "status"}
        >
          {inlineStatus.text}
        </p>
      ) : null}

      {view === "skeleton" ? (
        <div
          className={styles.skeleton}
          data-testid={suffixTestId(testId, "skeleton")}
          role="status"
        >
          <span className={styles.srOnly}>数据载入中</span>
          <div className={styles.scroll}>
            {/* 骨架保留真实列头几何，只把行内容换成静态占位条（DESIGN.md §8 不加循环动效）。 */}
            <table className={styles.table} data-layout={hasEllipsisColumn ? "fixed" : undefined} aria-hidden="true">
              {colGroup}
              <thead>{headRow}</thead>
              <tbody>
                {Array.from({ length: Math.max(1, skeletonRows) }, (_unused, rowIndex) => (
                  <tr key={`skeleton-${rowIndex}`} className={styles.row}>
                    {columns.map((column) => (
                      <td key={column.key} className={styles.cell} data-align={alignOf(column)}>
                        <span className={styles.skeletonBar} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {view === "empty" || view === "error" ? (
        <p
          className={styles.surface}
          data-tone={view === "error" ? STATUS_TONE.error : STATUS_TONE.empty}
          data-testid={suffixTestId(testId, view === "error" ? "error" : "empty")}
          role={view === "error" ? "alert" : "status"}
        >
          {view === "error" ? errorMessage : emptyMessage}
        </p>
      ) : null}

      {view === "rows" ? (
        <div className={styles.scroll}>
          <table
            className={styles.table}
            data-layout={hasEllipsisColumn ? "fixed" : undefined}
            aria-label={ariaLabel}
            aria-describedby={notices.length > 0 ? noticeId : undefined}
          >
            {colGroup}
            <thead>{headRow}</thead>
            <tbody id={bodyId}>
              {visibleRows.map((row, rowIndex) => {
                const rowTestIdValue = rowTestId?.(row, rowIndex);
                return (
                  <tr
                    key={resolveRowKey(row, rowKey, rowIndex)}
                    className={styles.row}
                    {...rowAttrs?.(row, rowIndex)}
                    {...(rowTestIdValue === undefined ? {} : { "data-testid": rowTestIdValue })}
                  >
                    {columns.map((column) => {
                      const content = cellContent(row, column);
                      const shared = {
                        className: styles.cell,
                        "data-align": alignOf(column),
                        "data-ellipsis": column.ellipsis ? "true" : undefined,
                        title:
                          column.ellipsis && typeof content === "string" ? content : undefined,
                      } as const;
                      return column.key === rowHeaderKey ? (
                        <th key={column.key} scope="row" {...shared}>
                          {content}
                        </th>
                      ) : (
                        <td key={column.key} {...shared}>
                          {content}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
            {summaryRow ? (
              <tfoot data-testid={suffixTestId(testId, "summary")}>
                <tr>
                  {columns.map((column, columnIndex) =>
                    columnIndex === 0 ? (
                      <th
                        key={column.key}
                        scope="row"
                        className={styles.footCell}
                        data-align={alignOf(column)}
                      >
                        {summaryRow[column.key] ?? EM_DASH}
                      </th>
                    ) : (
                      <td
                        key={column.key}
                        className={styles.footCell}
                        data-align={alignOf(column)}
                      >
                        {summaryRow[column.key] ?? EM_DASH}
                      </td>
                    ),
                  )}
                </tr>
              </tfoot>
            ) : null}
          </table>
        </div>
      ) : null}

      {view === "rows" && truncated ? (
        /* 折叠与展开两态都渲染这一条，控件本身不出现/消失，避免切换时的布局跳动。 */
        <div className={styles.footer} data-testid={suffixTestId(testId, "truncation")}>
          <span className={styles.footerNote}>
            {expanded
              ? `已展开全部 ${allRows.length} 行`
              : `共 ${allRows.length} 行，当前显示前 ${maxRows} 行`}
          </span>
          <button
            type="button"
            className={styles.toggle}
            onClick={() => setExpanded((previous) => !previous)}
            aria-expanded={expanded}
            aria-controls={bodyId}
          >
            {expanded ? "收起" : "展开全部"}
          </button>
        </div>
      ) : null}
    </div>
  );
}
