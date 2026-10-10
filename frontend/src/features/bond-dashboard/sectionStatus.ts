import type {
  ApiEnvelope,
  BondDashboardBundlePayload,
  BondDashboardBundleSectionId,
} from "../../api/contracts";
import {
  sectionStateFromStatus,
  type SectionState,
  type SurfaceStatus,
} from "../../components/layout";

/**
 * 页面统一的分区五态词表。
 *
 * 重构前这三句文案在 `BondDashboardSectionLead` 的注释里靠「各使用方私有实现，
 * 锁定同一文案」维持，四个分区各写了一遍 `sectionLeadState`。原语只提供
 * `SurfaceStatus → SectionState` 的形状转换（`sectionStateFromStatus`），
 * 文案属于页面语域，收在这里做单一来源。
 */
const SECTION_STATUS_LABEL: Record<Exclude<SurfaceStatus, "ready">, string> = {
  loading: "读取中",
  error: "读取失败",
  empty: "暂无数据",
  stale: "数据延迟",
  partial: "部分缺失",
};

/** 判定顺序与重构前逐字一致：loading 优先，其次 error，最后 empty。 */
export function bondSectionStatus(input: {
  loading: boolean;
  error?: boolean;
  empty: boolean;
}): SurfaceStatus {
  if (input.loading) return "loading";
  if (input.error) return "error";
  if (input.empty) return "empty";
  return "ready";
}

export function bondSectionState(status: SurfaceStatus): SectionState {
  return status === "ready" ? null : sectionStateFromStatus(status, SECTION_STATUS_LABEL[status]);
}

// ---------------------------------------------------------------------------
// 数据块级状态（DESIGN.md §6 五态齐备 / 不能静默吞态）
// ---------------------------------------------------------------------------

/**
 * 单个数据块自己的呈现状态。
 *
 * 它替代了各组件原来的 `loading: boolean`：布尔量只能表达「在读 / 不在读」，
 * 于是「请求已结束但该分区没回数」只能落进「不在读」，再被 DataTable 的
 * `skeleton-until-envelope` 渲染成骨架——用户看到的是「还在加载」，实际是失败，
 * 正是 §6「不能静默吞态」要防的。`message` 只在 error 下有意义。
 */
export type BondSectionDataState = {
  status: SurfaceStatus;
  message?: string | null;
};

/** 供直接渲染单个组件的测试与非 bundle 调用方使用的常量就绪态。 */
export const BOND_SECTION_READY: BondSectionDataState = { status: "ready" };

/**
 * 分区读取失败但后端没给原因时的兜底文案。整包失败不带 message，交给
 * DataTable / StateSurface 的默认「数据加载失败」，避免同一句全局原因在
 * 八个数据块里重复出现（§6 状态信息去重）；01 区 notice 已经承担了原因与重试指引。
 */
const SECTION_FAILED_MESSAGE = "该分区读取失败";
const SECTION_MISSING_MESSAGE = "该分区未返回数据";
/**
 * 报告日已确定不可用（dates 读取失败 / 无可用报告日）时 bundle 查询根本没有启用，
 * 这里没有「在途请求」可等，必须说清是被上游阻断而不是还在读。
 */
const SECTION_BLOCKED_MESSAGE = "报告日不可用，未发起查询";

/**
 * 把 bundle 的分区级读取结果映射成数据块状态。只读 `bondDashboardPageModel` 已
 * 消费的同两个字段（`section_statuses` / `failed_sections`），不改模型层。
 *
 * 判定顺序：
 * - 整包失败 → error（不带 message，见上）
 * - 报告日已终态不可用且信封未到达 → error + 「未发起查询」。禁用态 query 的
 *   `isPending` 永远为真，若仍按 loading 渲染，骨架会一直停在页面上（2026-09 审计）
 * - 信封尚未到达（dates 在途 / 报告日刚落地 / bundle 正在请求）→ loading
 * - 该分区 `section_statuses[section].status === "error"` → error + 后端原因
 * - 该分区在 `failed_sections` 里但没有 status 条目 → error + 兜底文案
 * - 分区数据不在 `sections` 里且后端没说原因 → error + 「未返回数据」。
 *   这里刻意不判 empty：empty 是「确实没有数据」的业务断言，而此刻我们只知道
 *   「没拿到数据」，两者不能混。
 * - 其余 → ready（真空与否交给各组件按 items 长度判）
 */
export function bondBundleSectionState(input: {
  bundle: ApiEnvelope<BondDashboardBundlePayload> | undefined;
  bundleError: boolean;
  /** dates 查询已结束但拿不到可用报告日（失败或列表为空），bundle 查询因此未启用。 */
  reportDateUnavailable: boolean;
  section: BondDashboardBundleSectionId;
}): BondSectionDataState {
  const { bundle, bundleError, reportDateUnavailable, section } = input;
  if (bundleError) return { status: "error" };
  if (!bundle) {
    return reportDateUnavailable
      ? { status: "error", message: SECTION_BLOCKED_MESSAGE }
      : { status: "loading" };
  }

  const sectionStatus = bundle.result.section_statuses?.[section];
  if (sectionStatus?.status === "error") {
    return { status: "error", message: sectionStatus.message ?? SECTION_FAILED_MESSAGE };
  }
  if ((bundle.result.failed_sections ?? []).includes(section)) {
    return { status: "error", message: SECTION_FAILED_MESSAGE };
  }
  if (bundle.result.sections[section] === undefined) {
    return { status: "error", message: SECTION_MISSING_MESSAGE };
  }
  return BOND_SECTION_READY;
}

/**
 * 分区头状态：优先级与 `bondSectionStatus` 一致（loading > error > empty），
 * 保证「块里已经红了、分区头还写着暂无数据」这种自相矛盾不会出现。
 */
export function bondSectionStatusFromStates(
  states: readonly BondSectionDataState[],
  isEmpty: boolean,
): SurfaceStatus {
  return bondSectionStatus({
    loading: states.some((state) => state.status === "loading"),
    error: states.some((state) => state.status === "error"),
    empty: isEmpty,
  });
}
