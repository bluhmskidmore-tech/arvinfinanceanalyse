/**
 * PnlAttributionView 与其 tab 容器共享的展示基元。
 *
 * SectionLead 承担首页 Nocturne 编号分区头语言（2026-08-13 重构）：
 * - 默认 `section` 变体：页根 counter-reset，分区头 ::before 输出 01/02…，
 *   标题 14px/700，右侧留状态位，底部发丝线（样式见 PnlAttributionView.css）。
 * - `card` 变体：卡片级小节头（眉标 + 13px 标题），不参与页级编号，
 *   供口径卡与页签内面板沿用，调用方接口保持兼容。
 *
 * PnlAttributionErrorRegion 承担错误态收敛（2026-08-14）：同一次 loadData 失败
 * 会同时打空当前页签的全部面板，此前每个面板各自渲染整条英文错误共 5 次
 * （§11.3 一票否决）；现在收敛为区级一条中文横幅 + 面板收缩为标题一行。
 */

import { EvidencePanel, PageStateSurface } from "../../../components/page/PagePrimitives";
import type {
  PnlAttributionErrorSummary,
  PnlAttributionTab,
} from "./pnlAttributionViewModel";

export function SectionLead(props: {
  eyebrow?: string;
  title: string;
  description: string;
  testId?: string;
  variant?: "section" | "card";
}) {
  if (props.variant === "card") {
    return (
      <div
        data-testid={props.testId}
        className="pnl-attribution-section-lead pnl-attribution-section-lead--card"
      >
        {props.eyebrow ? (
          <span className="pnl-attribution-section-lead__eyebrow">
            {props.eyebrow}
          </span>
        ) : null}
        <h2 className="pnl-attribution-section-lead__title">{props.title}</h2>
        {props.description ? (
          <p className="pnl-attribution-section-lead__description">
            {props.description}
          </p>
        ) : null}
      </div>
    );
  }
  return (
    <div
      data-testid={props.testId}
      className="pnl-attribution-section-lead pnl-attribution-section-head"
    >
      <h2 className="pnl-attribution-section-head__title">{props.title}</h2>
      {props.description ? (
        <p className="pnl-attribution-section-lead__description">
          {props.description}
        </p>
      ) : null}
    </div>
  );
}

/**
 * 区级错误横幅：正文为中文结论句；原始错误（含接口路径）属证据层，
 * 只进 title 悬浮提示（§6 溯源标识分层、§7 一页一语域）。
 */
export function PnlAttributionErrorBanner(props: {
  summary: PnlAttributionErrorSummary;
  onRetry: () => void;
  testId?: string;
}) {
  return (
    <PageStateSurface
      variant="error"
      testId={props.testId ?? "pnl-attribution-error-banner"}
      title="当前视图数据载入失败。"
      description={
        <span title={props.summary.detail}>{props.summary.message}</span>
      }
      actions={
        <button
          type="button"
          onClick={props.onRetry}
          className="pnl-attribution-tab-button"
        >
          重试
        </button>
      }
    />
  );
}

/** 各页签在错误态下收缩展示的面板标题（与正常态 PageDataSection 标题一致）。 */
const TAB_PANEL_TITLES: Record<PnlAttributionTab, readonly string[]> = {
  "product-category": ["产品分类归因工作台", "产品分类来源元信息"],
  "volume-rate": ["损益变动归因分解", "量价归因明细"],
  "tpl-market": ["FVTPL 公允价值变动 vs 10Y"],
  composition: ["损益构成"],
  advanced: [
    "Campisi 决策级解释",
    "Campisi 四效应归因（组合）",
    "Campisi 六效应归因（扩展）",
    "Campisi 到期桶拆解",
    "Carry / 利差 / KRD 高级归因",
    "高级归因结果元信息",
  ],
};

/**
 * 错误态区级收敛：一条错误横幅 + 当前页签各面板收缩为「标题 + 一行指引」。
 * 错误正文全页只出现一次（§6 状态信息去重）。
 */
export function PnlAttributionErrorRegion(props: {
  activeTab: PnlAttributionTab;
  summary: PnlAttributionErrorSummary;
  onRetry: () => void;
}) {
  return (
    <>
      <PnlAttributionErrorBanner
        summary={props.summary}
        onRetry={props.onRetry}
      />
      {TAB_PANEL_TITLES[props.activeTab].map((title) => (
        <EvidencePanel
          key={title}
          heading={title}
          testId="pnl-attribution-collapsed-panel"
        >
          <p className="pnl-attribution-collapsed-note">见上方错误说明。</p>
        </EvidencePanel>
      ))}
    </>
  );
}
