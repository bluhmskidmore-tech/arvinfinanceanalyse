import { useId, useMemo, useState } from "react";

import type {
  StockThemeBreakoutCard,
  StockThemeBreakoutLeader,
  StockThemeBreakoutReviewItem,
  StockThemeEvidenceStateRow,
} from "../lib/stockAnalysisPageModel";
import { buildStockThemeGroups, type StockThemeGroup } from "../lib/stockAnalysisThemeGroupsModel";
import "./StockAnalysisThemeGroupedView.css";

/**
 * 题材突破分组视图（多题材时代的 ThemeBreakoutPanel 替代实现，尚未接线）。
 *
 * - props 与 StockAnalysisThemeBreakoutPanel 同形态，可整体替换（见
 *   ThemeGroupedView.handoff.md）；evidenceRows / reviewItems 可省略。
 * - 行渲染是现有 ThemeBreakoutPanel 行逻辑的最小必要子集的内联实现：
 *   不 import 被并行会话占用的文件（PageImpl / chartModel / 页面 css /
 *   pageModel/index / tokens.css / tone.ts），类型仅取自干净的
 *   lib/stockAnalysisPageModel.ts。
 * - 分组/排序纯函数与 POLICY_THEME_ORDER 题材目录在
 *   lib/stockAnalysisThemeGroupsModel.ts。
 */

type StockAnalysisThemeGroupedViewProps = {
  /** 与 StockAnalysisThemeBreakoutPanel 的 cards 同形态的题材信号行数组。 */
  cards: StockThemeBreakoutCard[];
  emptyMessage: string;
  evidenceRows?: StockThemeEvidenceStateRow[];
  reviewItems?: StockThemeBreakoutReviewItem[];
};

export function StockAnalysisThemeGroupedView({
  cards,
  emptyMessage,
  evidenceRows = [],
  reviewItems = [],
}: StockAnalysisThemeGroupedViewProps) {
  const [selectedThemeKey, setSelectedThemeKey] = useState<string | null>(null);
  const [idleOpen, setIdleOpen] = useState(false);
  const idleListId = useId();

  const { active, idle } = useMemo(() => buildStockThemeGroups(cards), [cards]);

  // cards 变化后选中题材可能不复存在，派生回退到「全部」，不依赖 effect。
  const effectiveSelectedKey = active.some((group) => group.key === selectedThemeKey)
    ? selectedThemeKey
    : null;
  const visibleGroups = effectiveSelectedKey
    ? active.filter((group) => group.key === effectiveSelectedKey)
    : active;

  const evidenceLimited = evidenceRows.some((row) => row.status === "current_overlay");

  return (
    <div className="stock-analysis-theme-grouped" data-testid="stock-analysis-theme-grouped">
      {cards.length === 0 ? (
        <p
          className="stock-analysis-theme-grouped__empty"
          data-testid="stock-analysis-theme-grouped-empty"
        >
          {emptyMessage}
        </p>
      ) : (
        <>
          <div
            className="stock-analysis-theme-grouped__chips"
            role="group"
            aria-label="题材筛选"
            data-testid="stock-analysis-theme-grouped-chips"
          >
            <button
              type="button"
              className="stock-analysis-theme-grouped__chip"
              aria-pressed={effectiveSelectedKey === null}
              onClick={() => setSelectedThemeKey(null)}
              data-testid="stock-analysis-theme-chip-all"
            >
              全部
              <span className="stock-analysis-theme-grouped__chip-count">{cards.length}</span>
            </button>
            {active.map((group) => (
              <button
                key={group.key}
                type="button"
                className="stock-analysis-theme-grouped__chip"
                aria-pressed={effectiveSelectedKey === group.key}
                onClick={() =>
                  setSelectedThemeKey((current) => (current === group.key ? null : group.key))
                }
                data-testid={`stock-analysis-theme-chip-${group.key}`}
              >
                {group.name}
                <span className="stock-analysis-theme-grouped__chip-count">
                  {group.rows.length}
                </span>
              </button>
            ))}
            {idle.map((theme) => (
              <button
                key={theme.key}
                type="button"
                className="stock-analysis-theme-grouped__chip"
                disabled
                title="该题材当前没有信号行"
                data-testid={`stock-analysis-theme-chip-${theme.key}`}
              >
                {theme.name}
                <span className="stock-analysis-theme-grouped__chip-count">0</span>
              </button>
            ))}
          </div>

          {visibleGroups.map((group) => (
            <ThemeGroupSection group={group} key={group.key} />
          ))}

          {effectiveSelectedKey === null && idle.length > 0 && (
            <div
              className="stock-analysis-theme-grouped__idle"
              data-testid="stock-analysis-theme-grouped-idle"
            >
              <button
                type="button"
                className="stock-analysis-theme-grouped__idle-toggle"
                aria-expanded={idleOpen}
                aria-controls={idleListId}
                onClick={() => setIdleOpen((open) => !open)}
              >
                <span
                  className="stock-analysis-theme-grouped__dot"
                  data-state="idle"
                  aria-hidden="true"
                />
                无信号题材 {idle.length} 个
                <span className="stock-analysis-theme-grouped__idle-hint">
                  {idleOpen ? "收起" : "展开"}
                </span>
              </button>
              {idleOpen && (
                <ul className="stock-analysis-theme-grouped__idle-list" id={idleListId}>
                  {idle.map((theme) => (
                    <li className="stock-analysis-theme-grouped__idle-item" key={theme.key}>
                      <span className="stock-analysis-theme-grouped__idle-name">{theme.name}</span>
                      <span
                        className="stock-analysis-theme-grouped__proxy"
                        title="申万一级行业代理篮子代码"
                      >
                        {theme.proxyCode}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </>
      )}

      {evidenceRows.length > 0 && (
        <div
          className="stock-analysis-theme-grouped__section"
          data-testid="stock-analysis-theme-evidence-state"
        >
          <div className="stock-analysis-theme-grouped__section-head">
            <strong
              className={
                evidenceLimited
                  ? "stock-analysis-theme-grouped__section-title stock-analysis-theme-grouped__section-title--warning"
                  : "stock-analysis-theme-grouped__section-title"
              }
            >
              {evidenceLimited ? "题材证据受限" : "题材证据就绪"}
            </strong>
            <span
              className="stock-analysis-theme-grouped__pill"
              data-tone={evidenceLimited ? "warning" : "neutral"}
            >
              {evidenceRows.length} 项证据
            </span>
          </div>
          <ul className="stock-analysis-theme-grouped__evidence-list">
            {evidenceRows.map((row) => (
              <li className="stock-analysis-theme-grouped__evidence-item" key={row.key}>
                <div className="stock-analysis-theme-grouped__evidence-main">
                  <strong>{row.label}</strong>
                  <span>
                    {row.statusLabel} / {row.rowCountLabel}
                  </span>
                </div>
                <span className="stock-analysis-theme-grouped__evidence-detail">{row.detail}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {reviewItems.length > 0 && (
        <div
          className="stock-analysis-theme-grouped__section"
          data-testid="stock-analysis-theme-review-items"
        >
          <div className="stock-analysis-theme-grouped__section-head">
            <strong className="stock-analysis-theme-grouped__section-title stock-analysis-theme-grouped__section-title--warning">
              题材未入选复核
            </strong>
            <span className="stock-analysis-theme-grouped__pill" data-tone="warning">
              待排查 {reviewItems.length} 项
            </span>
          </div>
          <ul className="stock-analysis-theme-grouped__review-list">
            {reviewItems.map((item) => (
              <ThemeReviewRow item={item} key={`${item.themeKey}-${item.rank}`} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ThemeGroupSection({ group }: { group: StockThemeGroup }) {
  return (
    <section
      className="stock-analysis-theme-grouped__group"
      aria-label={`题材分组 ${group.name}`}
      data-testid={`stock-analysis-theme-group-${group.key}`}
    >
      <header className="stock-analysis-theme-grouped__group-head">
        <span
          className="stock-analysis-theme-grouped__dot"
          data-state="active"
          aria-hidden="true"
        />
        <h3 className="stock-analysis-theme-grouped__group-name">{group.name}</h3>
        <span
          className="stock-analysis-theme-grouped__pill"
          data-tone="accent"
          data-testid={`stock-analysis-theme-count-${group.key}`}
        >
          信号 {group.rows.length} 行
        </span>
        {group.proxyCode && (
          <span
            className="stock-analysis-theme-grouped__proxy"
            title="申万一级行业代理篮子代码"
          >
            {group.proxyCode}
          </span>
        )}
      </header>
      <ul className="stock-analysis-theme-grouped__rows">
        {group.rows.map((row) => (
          <ThemeSignalRow key={`${row.themeKey}-${row.rank}`} row={row} />
        ))}
      </ul>
    </section>
  );
}

function ThemeSignalRow({ row }: { row: StockThemeBreakoutCard }) {
  const statLabels = [
    row.strongCountLabel,
    row.limitCountLabel,
    row.advanceRatioLabel,
    row.avgPctChangeLabel,
    row.movementLabel,
  ];
  return (
    <li
      className="stock-analysis-theme-grouped__row"
      data-testid={`stock-analysis-theme-grouped-row-${row.themeKey}-${row.rank}`}
    >
      <div className="stock-analysis-theme-grouped__row-head">
        <span className="stock-analysis-theme-grouped__row-rank">#{row.rank}</span>
        <span className="stock-analysis-theme-grouped__row-sector">{row.parentSectorLabel}</span>
        {row.summary && (
          <span className="stock-analysis-theme-grouped__pill" data-tone="neutral">
            {row.summary}
          </span>
        )}
        <span
          className="stock-analysis-theme-grouped__pill stock-analysis-theme-grouped__row-source"
          data-tone={row.sourceKindLabel === "时点概念成分" ? "success" : "warning"}
        >
          {row.sourceKindLabel ?? "观察"}
        </span>
      </div>
      <div className="stock-analysis-theme-grouped__row-stats">
        {statLabels.map((label) => (
          <span className="stock-analysis-theme-grouped__stat" key={label}>
            {label}
          </span>
        ))}
      </div>
      <p className="stock-analysis-theme-grouped__row-reason">{row.reason}</p>
      <p className="stock-analysis-theme-grouped__row-event">{row.latestEventLabel}</p>
      <p className="stock-analysis-theme-grouped__row-boundary">{row.boundaryLabel}</p>
      {row.leaders.length > 0 && <ThemeLeaderList fallbackTag="观察" leaders={row.leaders} />}
    </li>
  );
}

function ThemeReviewRow({ item }: { item: StockThemeBreakoutReviewItem }) {
  return (
    <li className="stock-analysis-theme-grouped__review-item">
      <div className="stock-analysis-theme-grouped__row-head">
        <strong className="stock-analysis-theme-grouped__review-title">
          复核 #{item.rank} {item.themeName}
        </strong>
        <span className="stock-analysis-theme-grouped__row-sector">{item.parentSectorLabel}</span>
        <span
          className="stock-analysis-theme-grouped__pill stock-analysis-theme-grouped__row-source"
          data-tone="warning"
        >
          {item.sourceKindLabel}
        </span>
      </div>
      {item.summary && (
        <span className="stock-analysis-theme-grouped__pill" data-tone="warning">
          {item.summary}
        </span>
      )}
      <span className="stock-analysis-theme-grouped__pill" data-tone="danger">
        {item.failedGateLabel}
      </span>
      <p className="stock-analysis-theme-grouped__row-reason">{item.reason}</p>
      {item.leaders.length > 0 && <ThemeLeaderList fallbackTag="复核" leaders={item.leaders} />}
    </li>
  );
}

function ThemeLeaderList({
  leaders,
  fallbackTag,
}: {
  leaders: StockThemeBreakoutLeader[];
  fallbackTag: string;
}) {
  return (
    <ul className="stock-analysis-theme-grouped__leaders">
      {leaders.map((leader) => (
        <li className="stock-analysis-theme-grouped__leader" key={leader.stockCode}>
          <div className="stock-analysis-theme-grouped__leader-main">
            <strong className="stock-analysis-theme-grouped__leader-name">
              {leader.stockName}
            </strong>
            <span className="stock-analysis-theme-grouped__leader-meta">
              {leader.stockCode} / {leader.pctChange} / 换手 {leader.turn} / 收盘强度{" "}
              {leader.closeStrength}
            </span>
            {leader.sourceKindLabel && (
              <span className="stock-analysis-theme-grouped__leader-meta">
                {leader.sourceKindLabel}
              </span>
            )}
          </div>
          <span className="stock-analysis-theme-grouped__pill" data-tone="neutral">
            {leader.tags.join(" / ") || fallbackTag}
          </span>
        </li>
      ))}
    </ul>
  );
}
