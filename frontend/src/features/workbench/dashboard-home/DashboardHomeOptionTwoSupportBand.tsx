import { Link } from "react-router-dom";

import type { DashboardHomeBodyView } from "./dashboardHomeBodyView";
import type { HomeGovernanceStatusKind } from "./dashboardHomeFirstScreenTypes";
import type { HomeMarketTicker } from "./dashboardHomeMarket";
import { OptionTwoSparkline } from "./OptionTwoSparkline";
import styles from "./dashboardHomeOptionTwoSupportBand.module.css";

type DashboardHomeOptionTwoSupportBandProps = {
  view: DashboardHomeBodyView;
  dataStatusKind: HomeGovernanceStatusKind;
};

const GAP = "—";
const KEY_TENORS = ["1Y", "3Y", "5Y", "10Y"] as const;
/** 期限的真实年限，用于小图横轴按比例定位（1/3/5/10 年不是等距）。 */
const KEY_TENOR_YEARS = [1, 3, 5, 10] as const;
const FUNDING_PROXY_SERIES = [
  { id: "dr007", label: "DR007", seriesIds: ["M002", "CA.DR007"] },
  { id: "shibor-1m", label: "SHIBOR 1M", seriesIds: ["NCD.SHIBOR.1M"] },
  { id: "shibor-3m", label: "SHIBOR 3M", seriesIds: ["NCD.SHIBOR.3M"] },
  { id: "shibor-6m", label: "SHIBOR 6M", seriesIds: ["NCD.SHIBOR.6M"] },
] as const;

function governanceStatusLabel(kind: HomeGovernanceStatusKind): string {
  switch (kind) {
    case "ok":
      return "已同步";
    case "partial":
      return "部分可用";
    case "fallback":
      return "回退数据";
    case "stale":
      return "数据偏旧";
    case "loading":
      return "读取中";
    default:
      return "不可用";
  }
}

function displayOrGap(value: string | null | undefined): string {
  const normalized = value?.trim();
  return normalized && normalized !== "undefined" ? normalized : GAP;
}

/** 从已展示的收益率文案取数值（如 "1.60%"/"+1.12%" → 数值），格式不符则不取，仅用于同屏走势示意。 */
function parseCurveYield(label: string): number | null {
  const match = /^\s*([+-]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|[+-]?\d+(?:\.\d+)?)\s*%?\s*$/.exec(
    label,
  );
  if (!match) return null;
  const value = Number(match[1]!.replaceAll(",", ""));
  return Number.isFinite(value) ? value : null;
}

/** 微小变动被格式化成 "-0bp"/"+0bp" 时归零并转中性色，避免"负零标红"。 */
function neutralizeZeroDelta(
  delta: string,
  tone: HomeMarketTicker["deltaTone"],
): { delta: string; tone: HomeMarketTicker["deltaTone"] } {
  const trimmed = delta.trim();
  if (/^[-+]0(?:\.0+)?\s*(?:bp|pp|%)?$/.test(trimmed)) {
    return { delta: trimmed.replace(/^[-+]/, ""), tone: "flat" };
  }
  return { delta, tone };
}

function tickerBySeriesIds(
  tickers: readonly HomeMarketTicker[],
  ids: readonly string[],
): HomeMarketTicker | undefined {
  return ids
    .map((id) => tickers.find((ticker) => ticker.id === id))
    .find(isUsableFundingTicker);
}

function isUsableFundingTicker(
  ticker: HomeMarketTicker | undefined,
): ticker is HomeMarketTicker {
  return Boolean(
    ticker &&
      ticker.unit === "%" &&
      Number.isFinite(ticker.valueNumeric) &&
      (ticker.qualityFlag === "ok" ||
        ticker.qualityFlag === "warning" ||
        ticker.qualityFlag === "stale"),
  );
}

function fundingVendorLabel(ticker: HomeMarketTicker): string {
  return (
    ticker.vendorName?.trim() ||
    ticker.sourceVersion?.trim() ||
    "来源未标注"
  );
}

function fundingPolicyLabel(ticker: HomeMarketTicker): string {
  const policy = ticker.policyNote?.trim() ?? "";
  // 长政策说明由行内 title（fundingTickerTitle）全量披露；
  // 可见行只保留短代理标记，避免整列重复截断的英文长串。
  return /\bFDR007\b/.test(policy) ? "FDR007代理" : "";
}

function fundingTickerTitle(ticker: HomeMarketTicker): string {
  return [
    ticker.id,
    `行情日 ${ticker.tradeDate ?? "未返回"}`,
    `数值 ${ticker.value}`,
    `较前值 ${ticker.delta}`,
    `质量 ${ticker.qualityFlag ?? "未返回"}`,
    `来源 ${fundingVendorLabel(ticker)}`,
    ticker.policyNote ?? "未返回来源政策说明",
    "仅作为已落地资金代理展示，不推导资金松紧或评分",
  ].join("｜");
}

function MarketCurvePanel({ view }: { view: DashboardHomeBodyView }) {
  const context = view.marketContext;
  const curve = context.curveTable;
  const rows = KEY_TENORS.map((tenor) => {
    const row = curve.rows.find((candidate) => candidate.tenor === tenor);
    const yieldLabel = displayOrGap(row?.yieldLabel);
    const deltaLabel = displayOrGap(row?.deltaLabel);
    const hasValue = yieldLabel !== GAP || deltaLabel !== GAP;
    return {
      tenor,
      yieldLabel,
      deltaLabel,
      deltaTone: row?.deltaTone ?? "muted",
      state: hasValue ? "ready" : "backend-gap",
    } as const;
  });
  const hasAnyValue = rows.some((row) => row.state === "ready");

  return (
    <article
      className={styles.panel}
      data-testid="dashboard-home-market-context"
      aria-labelledby="option-two-market-curve-title"
    >
      <header className={styles.panelHeader}>
        <div>
          <h2 id="option-two-market-curve-title">{displayOrGap(curve.title)}</h2>
        </div>
        <time dateTime={curve.asOfLabel || undefined}>
          {displayOrGap(curve.asOfLabel)}
        </time>
      </header>

      <div className={styles.curveMeta}>
        <span
          className={styles.curveMetaSource}
          title={displayOrGap(context.sourceLabel)}
        >
          {displayOrGap(context.sourceLabel)}
        </span>
        <span title={displayOrGap(context.asOfLabel)}>
          {displayOrGap(context.asOfLabel)}
        </span>
        <span title={displayOrGap(context.statusLabel)}>
          {displayOrGap(context.statusLabel)}
        </span>
        <span title={displayOrGap(context.refreshLabel)}>
          {displayOrGap(context.refreshLabel)}
        </span>
      </div>

      {!hasAnyValue ? (
        <p className={styles.gapNotice} data-state="backend-gap">
          {curve.emptyMessage || "关键期限数据暂不可用"}
        </p>
      ) : (
        <div className={styles.curveSpark}>
          <OptionTwoSparkline
            values={rows.map((row) =>
              row.state === "ready" ? parseCurveYield(row.yieldLabel) : null,
            )}
            xValues={KEY_TENOR_YEARS}
            title={rows
              .map((row) => `${row.tenor} ${row.yieldLabel}`)
              .join(" / ")}
            endDot
          />
        </div>
      )}

      {view.krdState.kind === "ready" && view.krdBuckets.length > 0 ? (
        <div
          className={styles.krdStrip}
          data-testid="dashboard-home-krd-strip"
          aria-label="各期限 DV01 敞口"
        >
          <span className={styles.krdStripTitle}>
            各期限 DV01
            <small>万元/bp</small>
          </span>
          {(() => {
            const buckets = view.krdBuckets.slice(0, 8);
            const maxAbs = Math.max(
              1e-9,
              ...buckets.map((bucket) => Math.abs(bucket.dv01Raw ?? 0)),
            );
            return buckets.map((bucket) => (
              <div
                key={bucket.id}
                className={styles.krdRow}
                title={`${bucket.tenor} DV01 ${bucket.dv01Display}（利率上行 1bp 的估值敏感度）`}
              >
                <span>{bucket.tenor}</span>
                <i aria-hidden="true">
                  <b
                    style={{
                      width: `${Math.max(
                        2,
                        (Math.abs(bucket.dv01Raw ?? 0) / maxAbs) * 100,
                      ).toFixed(1)}%`,
                    }}
                  />
                </i>
                <strong>{bucket.dv01Display}</strong>
              </div>
            ));
          })()}
        </div>
      ) : null}

      <div className={styles.tableScroller}>
        <table
          className={styles.curveTable}
          data-testid="dashboard-home-market-curve-table"
          data-as-of={curve.asOfLabel}
        >
          <caption className={styles.srOnly}>四个关键期限收益率与前日变动</caption>
          <thead>
            <tr>
              <th scope="col">期限</th>
              <th scope="col">收益率</th>
              <th scope="col">前日变动</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.tenor} data-state={row.state}>
                <th scope="row">{row.tenor}</th>
                <td>{row.yieldLabel}</td>
                <td data-tone={row.deltaTone}>{row.deltaLabel}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
}

function FundingProxyPanel({
  view,
  dataStatusKind,
}: DashboardHomeOptionTwoSupportBandProps) {
  const fundingRows = FUNDING_PROXY_SERIES.map((item) => {
    const candidate = tickerBySeriesIds(
      view.marketContext.rateSeries,
      item.seriesIds,
    );
    return {
      ...item,
      ticker: isUsableFundingTicker(candidate) ? candidate : undefined,
    };
  });
  const landedCount = fundingRows.filter((row) => row.ticker).length;
  const state =
    dataStatusKind === "loading"
      ? "loading"
      : dataStatusKind === "error"
        ? "error"
        : landedCount > 0
          ? "ready"
          : "backend-gap";
  const statusLabel =
    state === "loading"
      ? "读取中"
      : state === "error"
        ? "来源不可用"
        : landedCount > 0
          ? `${landedCount} 条代理已落地`
          : "资金代理未落地";

  return (
    <article
      className={styles.panel}
      data-testid="dashboard-home-liquidity-panel"
      data-state={state}
      aria-labelledby="option-two-funding-title"
    >
      <header className={styles.panelHeader}>
        <div>
          <h2 id="option-two-funding-title">资金代理覆盖</h2>
        </div>
        <strong>{statusLabel}</strong>
      </header>

      <div
        className={styles.coverage}
        role="group"
        aria-label={`资金代理覆盖 ${landedCount} 条`}
        title="覆盖数量只表示已落地的正式资金代理行情行数，不代表资金松紧或流动性评分"
      >
        <strong>{landedCount > 0 ? landedCount : GAP}</strong>
        <span>已落地代理，不作松紧判断</span>
      </div>

      <dl className={styles.fundingRows}>
        {fundingRows.map((row) => {
          const ticker = row.ticker;
          const policyLabel = ticker ? fundingPolicyLabel(ticker) : "";
          const deltaDisplay = ticker
            ? neutralizeZeroDelta(ticker.delta, ticker.deltaTone)
            : null;
          return (
            <div
              key={row.id}
              data-state={ticker?.qualityFlag ?? "backend-gap"}
              title={
                ticker
                  ? fundingTickerTitle(ticker)
                  : `${row.label} 当前没有通过单位、有限数值与质量校验的正式代理行情`
              }
            >
              <dt>{row.label}</dt>
              {ticker ? (
                <dd
                  data-series-id={ticker.id}
                  data-trade-date={ticker.tradeDate}
                >
                  <strong>
                    {displayOrGap(ticker.value)}
                    <em data-tone={deltaDisplay?.tone ?? ticker.deltaTone}>
                      {displayOrGap(deltaDisplay?.delta ?? ticker.delta)}
                    </em>
                  </strong>
                  <small>
                    <time dateTime={ticker.tradeDate}>
                      {displayOrGap(ticker.tradeDate)}
                    </time>
                    <span>{fundingVendorLabel(ticker)}</span>
                    {policyLabel ? <span>{policyLabel}</span> : null}
                  </small>
                </dd>
              ) : (
                <dd>{GAP}</dd>
              )}
            </div>
          );
        })}
      </dl>

      <footer className={styles.gapFooter}>
        未接入：R007 / R001 / GC001；不以 DR007 或 SHIBOR 替代
      </footer>
    </article>
  );
}

function QuickDrilldownPanel({
  view,
  dataStatusKind,
}: DashboardHomeOptionTwoSupportBandProps) {
  const statusLabel = governanceStatusLabel(dataStatusKind);
  return (
    <section
      className={`${styles.panel} ${styles.quickPanel}`}
      data-testid="dashboard-home-bottom-grid"
      aria-labelledby="option-two-quick-drilldowns-title"
    >
      <header className={styles.panelHeader}>
        <div>
          <h2 id="option-two-quick-drilldowns-title">快捷下钻</h2>
        </div>
        <strong>{`${view.quickDrilldowns.length} 个入口`}</strong>
      </header>
      <nav className={styles.quickLinks} aria-label="经营日报快捷下钻">
        {view.quickDrilldowns.map((item, index) => (
          <Link key={item.id} to={item.path} className={styles.quickLink}>
            <span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
            <strong>{item.label}</strong>
            <small data-status-kind={dataStatusKind}>{statusLabel}</small>
            <em aria-hidden="true">→</em>
          </Link>
        ))}
      </nav>
    </section>
  );
}

export function DashboardHomeOptionTwoSupportBand(
  props: DashboardHomeOptionTwoSupportBandProps,
) {
  return (
    <section
      className={styles.supportBand}
      data-testid="dashboard-home-option-two-support-band"
      aria-label="市场来源、资金代理与快捷下钻"
    >
      <MarketCurvePanel view={props.view} />
      <FundingProxyPanel {...props} />
      <QuickDrilldownPanel {...props} />
    </section>
  );
}
