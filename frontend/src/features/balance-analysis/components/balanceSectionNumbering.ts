import type { SectionHeadNumbering, SectionMetaField } from "../../../components/layout";

/**
 * 本页的编号域是 `ba-section`：`counter-reset` 在 `.balance-analysis-page`、
 * `counter-increment` 在 `.balance-analysis-sec` 与 `.balance-analysis-details--sec`。
 *
 * 用外接编号域（而不是原语自带的 stack 域）的原因：同一条序列上还有一个没迁的
 * 消费方——`.balance-analysis-details__summary::before` 也打印 `ba-section`。
 * 递增位留在分区容器上（`increment` 保持缺省），已迁的分区头只打印当前值，
 * 于是折叠分区与普通分区共用一条连续序列，不会断号。
 */
export const BALANCE_SECTION_NUMBERING: SectionHeadNumbering = { counter: "ba-section" };

/**
 * 旧 `BalanceSectionHead` 的 `meta` 是一句自由文案（「正式口径 · 净头寸与期限缺口」
 * 这类口径descriptor），而原语的 `meta` 只收 `{label, value}` 字段对。这里按整句
 * 落在 `label` 上、`value` 留空，保证渲染文案与迁移前逐字一致（含其中的 `·`，
 * 单行一个仍在 DESIGN.md §7 配额内）。
 *
 * 这是被迫的绕行，不是推荐用法：`SectionHead` 缺一个自由文本口径槽，见报告
 * 「原语层缺口」一节。
 */
export function balanceSectionMeta(meta: string | undefined): SectionMetaField[] | undefined {
  const text = meta?.trim();
  return text ? [{ label: text, value: "", title: text }] : undefined;
}
