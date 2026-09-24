import type { ResultMeta } from "../../../api/contracts";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import BondDashboardSectionLead from "../components/BondDashboardSectionLead";
import type { BondDashboardSectionStatusItem } from "../model/bondDashboardPageModel";
import { formatEvidenceTimestamp } from "../utils/format";
import "./BondDashboardEvidenceSection.css";

/**
 * 生成时间原值为微秒 ISO（如 2026-08-13T19:24:06.752770Z），在窄卡内折行
 * 断字；进共享面板前收敛为本地 YYYY-MM-DD HH:mm:ss 展示串。完整原值披露
 * 需共享 FormalResultMetaPanel 支持字段级 title，暂不在本页范围内。
 */
function withDisplayGeneratedAt(meta: ResultMeta | undefined): ResultMeta | undefined {
  if (!meta?.generated_at) return meta;
  const formatted = formatEvidenceTimestamp(meta.generated_at);
  return formatted === meta.generated_at ? meta : { ...meta, generated_at: formatted };
}

type EvidenceSectionProps = {
  datesMeta: ResultMeta | undefined;
  bundleMeta: ResultMeta | undefined;
  headlineMeta: ResultMeta | undefined;
  riskMeta: ResultMeta | undefined;
  datesEmpty: boolean;
  sectionStatusItems: BondDashboardSectionStatusItem[];
};

/**
 * 06 证据与口径：页面请求与首屏 result_meta 证据 + 治理边界（文案逐字锁定）+
 * 指标口径静态披露 + bundle 分区读取状态披露（全 ok 收敛为一行摘要，
 * 存在失败时才逐行展开失败项，避免 12 行 ok 噪音占屏）。
 */
export default function EvidenceSection({
  datesMeta,
  bundleMeta,
  headlineMeta,
  riskMeta,
  datesEmpty,
  sectionStatusItems,
}: EvidenceSectionProps) {
  const hasResultMeta = Boolean(datesMeta || bundleMeta || headlineMeta || riskMeta);
  const failedItems = sectionStatusItems.filter((item) => item.status === "error");
  const knownDurations = sectionStatusItems
    .map((item) => item.durationMs)
    .filter((value): value is number => value !== null);
  // 各分区串行读取耗时的合计披露；全部缺失时整段省略而非补占位。
  const totalDurationMs =
    knownDurations.length > 0
      ? Math.round(knownDurations.reduce((sum, value) => sum + value, 0))
      : null;
  const statusSummaryText =
    failedItems.length > 0
      ? `${sectionStatusItems.length} 个分区中 ${failedItems.length} 个读取失败`
      : `${sectionStatusItems.length} 个分区全部读取成功`;

  return (
    <section
      className="bond-dashboard-section bond-dashboard-evidence"
      id="bond-dashboard-section-evidence"
    >
      <BondDashboardSectionLead title="证据与口径" />
      {hasResultMeta ? (
        <FormalResultMetaPanel
          testId="bond-dashboard-first-screen-result-meta"
          title="债券总览读取证据"
          sections={[
            {
              key: "dates",
              title: "报告日清单",
              meta: withDisplayGeneratedAt(datesMeta),
            },
            {
              key: "bundle",
              title: "页面批量读取",
              meta: withDisplayGeneratedAt(bundleMeta),
            },
            {
              key: "headline",
              title: "首屏指标",
              meta: withDisplayGeneratedAt(headlineMeta),
            },
            {
              key: "risk",
              title: "风险指标",
              meta: withDisplayGeneratedAt(riskMeta),
            },
          ]}
        />
      ) : null}
      {!datesEmpty ? (
        <details className="bond-dashboard-evidence__notes">
          <summary>口径与指标边界（证据层）</summary>
          <p data-testid="bond-dashboard-headline-candidate-boundary">
            MTR-BOND-001~004 仍为 candidate，pending_confirmation=true；GS-BOND-HEADLINE-A 是页面样本，非字典级批准。
          </p>
          <p data-testid="bond-dashboard-risk-source-boundary">
            GAP-BOND-DASH-RISK 尚未冻结 MTR-RSK-* 同源关系；风险指标面板不自动继承 GS-RISK-A。
          </p>
        </details>
      ) : null}
      {!datesEmpty ? (
        <details
          className="bond-dashboard-evidence__notes"
          data-testid="bond-dashboard-caliber-notes"
        >
          <summary>指标口径说明</summary>
          <ul className="bond-dashboard-evidence__notes-list">
            <li>信用债收益率中位数为信用债 YTM 中位数，不代表相对国债的信用利差。</li>
            <li>
              加权到期收益率与加权久期仅统计利率债与信用债中有到期日、修正久期大于 0 且市值不为 0
              的持仓，其余持仓不计入分子与分母。
            </li>
            <li>行业占比分母为行业分布表内前 10 大行业的市值合计（行业缺失持仓不计入），非全组合总市值。</li>
            <li>数据来源：债券分析事实表（fact_formal_bond_analytics_daily），与余额分析页可能存在口径差异。</li>
          </ul>
        </details>
      ) : null}
      {sectionStatusItems.length > 0 ? (
        <div
          className="bond-dashboard-evidence__statuses"
          data-testid="bond-dashboard-section-statuses"
        >
          <p className="bond-dashboard-evidence__status-summary">
            <span
              className="bond-dashboard-evidence__status-dot"
              data-tone={failedItems.length > 0 ? "error" : "ok"}
              aria-hidden="true"
            />
            <span className="bond-dashboard-evidence__status-text">{statusSummaryText}</span>
            {totalDurationMs !== null ? (
              <span className="bond-dashboard-evidence__status-duration">
                合计 {totalDurationMs} ms
              </span>
            ) : null}
          </p>
          {failedItems.length > 0 ? (
            <ul className="bond-dashboard-evidence__status-list">
              {failedItems.map((item) => (
                <li key={item.section} className="bond-dashboard-evidence__status-row">
                  <span
                    className="bond-dashboard-evidence__status-dot"
                    data-tone="error"
                    aria-hidden="true"
                  />
                  <span className="bond-dashboard-evidence__status-label">{item.label}</span>
                  {item.message ? (
                    <span className="bond-dashboard-evidence__status-message">{item.message}</span>
                  ) : null}
                  {item.durationMs !== null ? (
                    <span className="bond-dashboard-evidence__status-duration">
                      {item.durationMs} ms
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
