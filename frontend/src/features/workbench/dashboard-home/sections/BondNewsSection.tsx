import { useState } from "react";
import type { QueryClient } from "@tanstack/react-query";

import type {
  HomeBondNewsModel,
  HomeBondNewsItem,
} from "../adapters/buildHomeBondNewsModel";
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

const HOME_NEWS_QUERY_PREFIXES = [
  ["dashboard", "macro-news"],
  ["dashboard", "macro-news-fallback"],
  ["dashboard", "bond-news"],
  ["dashboard", "choice-news-digest"],
  ["home", "research-reports"],
] as const;
const SOURCE_UPDATE_BOUNDARY_LABEL = "来源更新：后台受控";

function BondNewsItemRow({ item }: { item: HomeBondNewsItem }) {
  const itemTooltip = `${item.title} · ${item.hitLabel ?? item.sourceLabel} · ${item.timeLabel}`;
  return (
    <div
      data-layout-role="bond-news-item"
      className={styles.dhBondNewsItem}
      title={itemTooltip}
    >
      <span
        data-layout-role="bond-news-topic"
        className={styles.dhBondNewsTopic}
      >
        {item.topicLabel}
      </span>
      <span data-layout-role="bond-news-body" className={styles.dhBondNewsBody}>
        <strong title={item.title}>{item.title}</strong>
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
            <BondNewsItemRow key={item.id} item={item} />
          ))}
        </div>
      ) : (
        <p className={styles.dhBondNewsEmptyCompact}>{message}</p>
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
          >
            <span title={bondNews.sourceLabel}>{bondNews.sourceLabel}</span>
            <span title={SOURCE_UPDATE_BOUNDARY_LABEL}>
              {SOURCE_UPDATE_BOUNDARY_LABEL}
            </span>
            <span title={bondNews.asOfLabel}>{bondNews.asOfLabel}</span>
            <span title={bondNews.statusLabel}>{bondNews.statusLabel}</span>
            <span title={bondNews.refreshLabel}>{bondNews.refreshLabel}</span>
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
          {updatedAt ? <time>{`更新 ${updatedAt}`}</time> : null}
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
