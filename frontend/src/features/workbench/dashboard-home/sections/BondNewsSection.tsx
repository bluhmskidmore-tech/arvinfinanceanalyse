import { useState } from "react";
import type { QueryClient } from "@tanstack/react-query";

import type {
  HomeBondNewsModel,
  HomeBondNewsItem,
} from "../adapters/buildHomeBondNewsModel";
import { formatResearchTitleDisplay } from "../lib/researchTitleDisplay";
import styles from "../dashboardHomeOptionTwoDeferred.module.css";

type BondNewsSectionProps = {
  bondNews: HomeBondNewsModel;
  actions?: BondNewsActions;
  sectionIndex?: string;
  updatedAt?: string;
};

export type BondNewsActions = {
  queryClient: QueryClient;
};

type BondNewsGroupProps = {
  testId: string;
  title: string;
  count: number;
  items: readonly HomeBondNewsItem[];
  message: string | null;
};

/** 空组消息与组头标题同名时剥离「{组名}：」前缀，避免「持仓命中 0 条 持仓命中：…」重复。 */
function emptyMessageDisplay(message: string | null, groupTitle: string): string | null {
  if (!message) return message;
  const prefix = new RegExp(`^${groupTitle}\\s*[：:]\\s*`, "u");
  return message.replace(prefix, "").trim() || message;
}

const HOME_NEWS_QUERY_PREFIXES = [
  ["dashboard", "macro-news"],
  ["dashboard", "macro-news-fallback"],
  ["dashboard", "bond-news"],
  ["dashboard", "choice-news-digest"],
  ["home", "research-reports"],
] as const;
const SOURCE_UPDATE_BOUNDARY_LABEL = "来源更新：后台受控";

function BondNewsItemRow({
  item,
  groupTitle,
}: {
  item: HomeBondNewsItem;
  groupTitle: string;
}) {
  const itemTooltip = `${item.title} · ${item.hitLabel ?? item.sourceLabel} · ${item.timeLabel}`;
  // 与分组标题重复的分类不再逐行渲染；仅保留有业务差异的分类作轻量文本。
  const showTopic = Boolean(item.topicLabel) && item.topicLabel !== groupTitle;
  return (
    <div
      data-layout-role="bond-news-item"
      className={`${styles.dhBondNewsItem} ${showTopic ? "" : styles.dhBondNewsItemBare}`}
      title={itemTooltip}
    >
      {showTopic ? (
        <span
          data-layout-role="bond-news-topic"
          className={styles.dhBondNewsTopic}
        >
          {item.topicLabel}
        </span>
      ) : null}
      <span data-layout-role="bond-news-body" className={styles.dhBondNewsBody}>
        <strong title={item.title}>{formatResearchTitleDisplay(item.title)}</strong>
        <small>
          {item.hitLabel ?? item.sourceLabel} · {item.timeLabel}
        </small>
      </span>
    </div>
  );
}

function BondNewsGroup({
  testId,
  title,
  count,
  items,
  message,
}: BondNewsGroupProps) {
  const isEmpty = items.length === 0;
  return (
    <div
      data-testid={testId}
      data-layout-role="bond-news-group"
      data-empty={isEmpty ? "true" : "false"}
      className={`${styles.dhBondNewsGroup} ${isEmpty ? styles.dhBondNewsGroupEmpty : ""}`}
    >
      <div
        data-layout-role="bond-news-group-header"
        className={styles.dhBondNewsGroupHeader}
      >
        <span>{title}</span>
        <small>{count} 条</small>
      </div>
      {items.length > 0 ? (
        <div
          data-layout-role="bond-news-list"
          className={styles.dhBondNewsList}
        >
          {items.map((item) => (
            <BondNewsItemRow key={item.id} item={item} groupTitle={title} />
          ))}
        </div>
      ) : (
        <p className={styles.dhBondNewsEmptyCompact} title={message ?? undefined}>
          {emptyMessageDisplay(message, title)}
        </p>
      )}
    </div>
  );
}

export function BondNewsSection({
  bondNews,
  actions,
  sectionIndex,
  updatedAt,
}: BondNewsSectionProps) {
  const [isRereading, setIsRereading] = useState(false);
  const [actionStatus, setActionStatus] = useState("");
  const [actionError, setActionError] = useState("");

  // 卡头元信息最多两枚：数据截止 + 异常态状态；来源/边界/刷新说明与全页更新时间收进悬浮说明。
  const isStatusAbnormal = !bondNews.statusLabel.includes("正常");
  const headerTooltip = [
    bondNews.sourceLabel,
    SOURCE_UPDATE_BOUNDARY_LABEL,
    bondNews.statusLabel,
    bondNews.refreshLabel,
    updatedAt ? `更新 ${updatedAt}` : "",
  ]
    .filter(Boolean)
    .join(" · ");

  const handleReread = async () => {
    if (!actions) {
      return;
    }
    setActionError("");
    setActionStatus("正在重新读取已落库新闻与研报…");
    setIsRereading(true);
    try {
      await Promise.all(
        HOME_NEWS_QUERY_PREFIXES.map((queryKey) =>
          actions.queryClient.invalidateQueries({
            queryKey,
            exact: false,
            refetchType: "active",
          }),
        ),
      );
      setActionStatus("已重新读取当前已落库新闻与研报。");
    } catch (error) {
      const detail =
        error instanceof Error && error.message.trim()
          ? `：${error.message.trim()}`
          : "";
      setActionError(`重新读取失败${detail}。`);
      setActionStatus("");
    } finally {
      setIsRereading(false);
    }
  };

  return (
    <section
      data-testid="dashboard-home-bond-news"
      data-layout-role="bond-news"
      className={styles.dhBondNewsSection}
    >
      <article
        data-layout-role="bond-news-card"
        className={`${styles.dhCard} ${styles.dhBondNewsCard}`}
      >
        <div
          data-layout-role="bond-news-internal-header"
          className={styles.dhBondNewsHeader}
        >
          <div data-layout-role="bond-news-title">
            {sectionIndex ? (
              <small aria-hidden="true">{sectionIndex}</small>
            ) : null}
            <span>债券信息新闻</span>
          </div>
          <div
            data-layout-role="bond-news-trust-strip"
            className={styles.dhMacroTrustStrip}
            aria-label="债券新闻数据状态"
            title={headerTooltip}
          >
            <span title={bondNews.asOfLabel}>{bondNews.asOfLabel}</span>
            {isStatusAbnormal ? (
              // 「偏旧」状态词与治理台账状态列重复（§6 两处上限），卡头收敛为
              // 琥珀点，全文保留在点与卡头 title；其余异常态保留文字。
              bondNews.statusLabel.includes("偏旧") ? (
                <span
                  data-tone="warning"
                  data-testid="dashboard-home-bond-news-stale-dot"
                  title={bondNews.statusLabel}
                  aria-label={bondNews.statusLabel}
                >
                  <i aria-hidden="true" className={styles.dhBondNewsStaleDot} />
                </span>
              ) : (
                <span data-tone="warning" title={bondNews.statusLabel}>
                  {bondNews.statusLabel}
                </span>
              )
            ) : null}
          </div>
          <div
            data-layout-role="bond-news-actions"
            className={styles.dhBondNewsActions}
          >
            <button
              type="button"
              className={styles.dhBondNewsRereadButton}
              disabled={isRereading || !actions}
              onClick={() => void handleReread()}
              aria-label="重新读取已落库新闻与研报"
              title="重新读取已落库新闻与研报，不触发外部来源更新"
            >
              {isRereading ? "读取中…" : "重新读取"}
            </button>
            <button
              type="button"
              className={styles.dhBondNewsSourceButton}
              disabled
              aria-label="来源更新由后台受控任务维护"
              title="外部来源更新当前不对前端开放，由后台受控任务维护"
            >
              更新来源
            </button>
          </div>
        </div>
        {actionStatus || actionError ? (
          <p
            data-layout-role="bond-news-action-status"
            className={`${styles.dhBondNewsActionStatus} ${
              actionError ? styles.dhBondNewsActionStatusError : ""
            }`}
            role="status"
            aria-live="polite"
          >
            {actionError || actionStatus}
          </p>
        ) : null}
        <div
          data-layout-role="bond-news-grid"
          className={styles.dhBondNewsGrid}
        >
          <BondNewsGroup
            testId="dashboard-home-bond-news-holding"
            title="持仓命中"
            count={bondNews.holdingHits.length}
            items={bondNews.holdingHits}
            message={bondNews.holdingMessage}
          />
          <BondNewsGroup
            testId="dashboard-home-bond-news-market"
            title="债券市场"
            count={bondNews.marketNews.length}
            items={bondNews.marketNews}
            message={bondNews.marketMessage}
          />
          <BondNewsGroup
            testId="dashboard-home-bond-news-credit"
            title="发行/评级"
            count={bondNews.creditAndIssuanceNews.length}
            items={bondNews.creditAndIssuanceNews}
            message={bondNews.creditMessage}
          />
        </div>
      </article>
    </section>
  );
}
