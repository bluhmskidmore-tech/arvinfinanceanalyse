import type {
  SectionHeadExternalCounter,
  SectionState,
  SectionStateTone,
} from "../../../components/layout";
import type {
  MacroObservationSectionState,
  MacroObservationSectionStateKind,
} from "../model/macroObservationPageModel";

/**
 * 本页的编号域是 `mo-section`：`counter-reset` 在 `.macro-observation-view`
 * 页根，`counter-increment` 在 `.macro-observation-view__section` 分区容器
 * 上（不是分区头自己身上）——迁移前由页面私有的 `MacroObservationSectionLead`
 * 读同一个 CSS counter 打印编号（`::before { content: counter(mo-section,
 * decimal-leading-zero) }`）。
 *
 * 迁移到共享 `SectionHead` 后改用其外接编号域能力（`numbered={{ counter }}`），
 * `increment` 保持缺省 `false`：递增位继续留在页面既有的分区容器上，序号逐字
 * 不变，只是渲染样式（原自绘 11px/tabular/muted `::before`）改为 SectionHead
 * 的原语默认样式（同规格，来源收拢到组件，见 SectionHead.module.css）。
 */
export const MACRO_OBSERVATION_SECTION_NUMBERING: SectionHeadExternalCounter = {
  counter: "mo-section",
};

/**
 * 分区状态四态（loading/empty/error/deferred）→ SectionHead 的 `SectionState`。
 *
 * SectionHead 的 tone 词表（loading/error/empty/stale/partial）没有
 * "deferred"：本页的 deferred 表示「core 首发已到，该分区证据要等完整分析
 * 才确认」，既不是仍在请求（loading）也不是确认没有数据（empty），但也不该
 * 套「stale」（不是过期数据）或「partial」（不是部分可用）附带的琥珀告警色——
 * 迁移前的页面 CSS 里 loading 与 deferred 恰好共享同一档缺省 muted 呈现
 * （`.macro-observation-view__section-state` 只单独覆盖了 error 与 empty
 * 两档颜色）。这里把 deferred 落到 "loading"，是与原视觉最接近、且不会像
 * stale/partial 那样附带告警色的现成选项；不是完全对等的映射，见报告
 * 「原语层缺口」一节。
 */
const SECTION_STATE_TONE: Record<MacroObservationSectionStateKind, SectionStateTone> = {
  loading: "loading",
  error: "error",
  empty: "empty",
  deferred: "loading",
};

export function macroObservationSectionHeadState(
  state: MacroObservationSectionState,
): SectionState {
  if (!state) {
    return null;
  }
  return { label: state.note, tone: SECTION_STATE_TONE[state.state] };
}
