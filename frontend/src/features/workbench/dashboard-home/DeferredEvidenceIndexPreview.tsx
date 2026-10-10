import styles from "./dashboardHomeShell.module.css";

const DEFERRED_INDEX_ITEMS = [
  { code: "01", title: "持仓账本", detail: "余额 / 市值 / 久期" },
  { code: "02", title: "风险归因", detail: "敞口 / 拖累 / 贡献" },
  { code: "03", title: "资金政策", detail: "事件 / 央行 / 利率" },
  { code: "04", title: "研究快讯", detail: "市场 / 新闻 / 摘要" },
  { code: "05", title: "凭证链路", detail: "来源 / 版本 / 状态" },
  { code: "06", title: "待办闭环", detail: "动作 / 责任 / 时点" },
  { code: "07", title: "保留缺口", detail: "不推断 / 待接入" },
] as const;

export function DeferredEvidenceIndexPreview() {
  return (
    <section
      className={styles.dhDeferredIndex}
      data-testid="dashboard-home-deferred-index"
      aria-label="证据索引加载中"
    >
      <div className={styles.dhDeferredIndexHead}>
        <span>证据索引</span>
        <strong>下半屏模块按来源延迟展开，未落源部分保持缺口态</strong>
      </div>
      <div className={styles.dhDeferredIndexGrid}>
        {DEFERRED_INDEX_ITEMS.map((item) => (
          <article key={item.code} className={styles.dhDeferredIndexItem}>
            <span>{item.code}</span>
            <strong>{item.title}</strong>
            <small>{item.detail}</small>
          </article>
        ))}
      </div>
    </section>
  );
}
