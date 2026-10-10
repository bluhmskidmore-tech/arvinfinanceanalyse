import { useMemo } from "react";
import { Link } from "react-router-dom";
import { Tabs } from "antd";
import type { CSSProperties, ReactNode } from "react";

import { LightIcon } from "../../../components/LightIcon";
import { SectionHead } from "../../../components/layout";
import kpiStyles from "../../../components/layout/KpiStrip.module.css";
import { EM_DASH } from "../../../utils/format";
import dhStyles from "../dashboard-home/dashboardHome.module.css";
import type {
  ModuleHomeDetailPanel,
  ModuleHomeDistributionPanel,
  ModuleHomeKpi,
  ModuleHomeTone,
  ModuleHomeView,
} from "./moduleHomeModel";
import type { ModuleWorkbenchHomeConfig } from "./moduleHomeConfig";
import { resolveMarketChangeDirection } from "./marketHomeChangeTone";
import { PortfolioAttributionWaterfall } from "./PortfolioAttributionWaterfall";
import { PortfolioHoldingsHeroBand } from "./PortfolioHoldingsHeroBand";
import { PortfolioRiskTickerBar } from "./PortfolioRiskTickerBar";
import { PortfolioStructureTabPanel } from "./PortfolioStructureTabPanel";
import styles from "./portfolioHome.module.css";

/** spread-analysis 内容是券种 median_yield（非对国债利差），页签按口径直呼「券种收益率」（与 B4 KPI 改名同理）。 */
const ANALYSIS_TABS = [
  { key: "portfolio-comparison", label: "子组合" },
  { key: "yield-distribution", label: "收益率" },
  { key: "spread-analysis", label: "券种收益率" },
  { key: "business-type-metrics", label: "业务类型" },
] as const;

/**
 * 结构页签 → 债券总览页真实分区锚点（bond-dashboard/sections/* 内的 <section id>）；
 * 子组合与券种收益率同在「组合与风险」分区，收益率在「资产结构」分区。
 */
const BOND_DASHBOARD_SECTION_ANCHORS: Record<(typeof ANALYSIS_TABS)[number]["key"], string> = {
  "portfolio-comparison": "bond-dashboard-section-portfolio-risk",
  "yield-distribution": "bond-dashboard-section-structure",
  "spread-analysis": "bond-dashboard-section-portfolio-risk",
  "business-type-metrics": "bond-dashboard-section-business-type",
};

/** 债券总览复核深链：日期为空时不拼 report_date 伪参数，仅保留分区锚点。 */
function bondDashboardGapLink(
  tabKey: (typeof ANALYSIS_TABS)[number]["key"],
  reportDate: string,
): string {
  const anchor = `#${BOND_DASHBOARD_SECTION_ANCHORS[tabKey]}`;
  return reportDate
    ? `/bond-dashboard?report_date=${encodeURIComponent(reportDate)}${anchor}`
    : `/bond-dashboard${anchor}`;
}

type PortfolioStructureTab = (typeof ANALYSIS_TABS)[number] & {
  panel?: ModuleHomeDetailPanel;
};

const WORKBENCH_NAV_ITEMS = [
  { href: "#portfolio-holdings-workbench", label: "持仓结构", detail: "组合结构与关键暴露" },
  { href: "#portfolio-risk-workbench", label: "收益与风险", detail: "收益、风险与日期复核" },
  { href: "#portfolio-structure-workbench", label: "结构拆解", detail: "分组合与业务类型" },
  { href: "#portfolio-action-workbench", label: "来源证据", detail: "使用说明" },
] as const;

type PortfolioHomeLayoutProps = {
  view: ModuleHomeView;
  config: ModuleWorkbenchHomeConfig;
  balanceReportDate: string;
  bondReportDate: string;
};

type PortfolioDecisionFact = NonNullable<ModuleHomeView["decision"]>["facts"][number];

const PORTFOLIO_TECHNICAL_FIELDS = new Set([
  "total_market_value", "total_dv01", "weighted_duration", "credit_ratio",
  "weighted_convexity", "total_spread_dv01", "reinvestment_ratio_1y",
  "weighted_ytm", "primary_driver", "key_findings",
]);

function portfolioSourceLabel(text: string) {
  return text.replaceAll("bond-dashboard", "债券总览")
    .replaceAll("balance-analysis", "资产负债分析")
    .replaceAll("pnl-attribution", "收益归因");
}

function portfolioStatusDetail(item: Pick<ModuleHomeView["statuses"][number], "detail">) {
  const knownDetails: Record<string, string> = {
    "正式 overview 已返回。": "资产负债数据可用。",
    "headline kpis 已返回。": "债券指标可用。",
    "risk-indicators 已返回。": "风险指标可用。",
    "券种/评级/期限/行业分布已挂接。": "券种、评级、期限和行业分布可用。",
    "bond.home_summary 为分析口径或未允许正式使用，不参与首屏决策 KPI。": "债券数据仅供分析，暂不能用于组合决策。",
    "bond.risk_indicators 为分析口径或未允许正式使用，不参与风险 ticker 或闭合判断。": "风险指标仅供分析，暂不能用于当前风险判断。",
    "risk-indicators 为分析口径或未允许正式使用，仅保留为明细复核，不参与风险 ticker 或闭合判断。": "风险指标仅供分析复核，不能用于正式风险判断。",
    "该读链路当前返回前端样例 envelope，不作为正式证据。": "当前为模拟数据，不可用于业务决策。",
  };
  return knownDetails[item.detail] ?? item.detail;
}

function toneClass(tone: ModuleHomeTone) {
  if (tone === "ok") return styles.toneOk;
  if (tone === "watch") return styles.toneWatch;
  if (tone === "error") return styles.toneError;
  return styles.toneMuted;
}

function briefCardClass(tone: ModuleHomeTone, primary = false) {
  const toneKey =
    tone === "ok"
      ? styles.briefCardOk
      : tone === "watch"
        ? styles.briefCardWatch
        : tone === "error"
          ? styles.briefCardError
          : "";
  return `${styles.briefCard} ${toneKey} ${primary ? styles.briefCardPrimary : ""}`.trim();
}

function statePillClass(tone: ModuleHomeTone) {
  if (tone === "ok") return `${styles.statePill} ${styles.stateOk}`;
  if (tone === "error") return `${styles.statePill} ${styles.stateError}`;
  if (tone === "watch") return `${styles.statePill} ${styles.stateWatch}`;
  return styles.statePill;
}

function panelByKey(panels: ModuleHomeDetailPanel[] | undefined, key: string) {
  return panels?.find((panel) => panel.key === key);
}

function detailPanelTestId(panelKey: string) {
  if (panelKey === "risk-indicators-detail") return "module-home-portfolio-risk";
  if (panelKey === "portfolio-comparison") return "module-home-portfolio-comparison";
  if (panelKey === "yield-distribution") return "module-home-portfolio-yield";
  if (panelKey === "spread-analysis") return "module-home-portfolio-spread";
  if (panelKey === "business-type-metrics") return "module-home-portfolio-business-type";
  if (panelKey === "balance-basis") return "module-home-balance-basis";
  if (panelKey === "pnl-attribution-summary") return "module-home-pnl-summary";
  return "module-home-detail-panels";
}

/** 叙述型读数（如归因发现）不是金融数字，右对齐等宽排版会破坏可读性。 */
function detailValueKind(value: string): "prose" | "metric" {
  const text = value.trim();
  return text.length >= 16 && !/^[+\-\d]/.test(text) ? "prose" : "metric";
}

const PNL_DRIVER_TOKEN_LABELS: Record<string, string> = {
  rate: "利率",
  volume: "规模",
  market: "市场",
};

/** 归因摘要 key_findings 是后端枚举直出句（如「主驱动归类为 rate」），展示层中文化（B7）。 */
function localizePnlFindingText(text: string) {
  return text.replace(
    /归类为\s*(rate|volume|market)\b/gi,
    (token, driver: string) =>
      `归类为${PNL_DRIVER_TOKEN_LABELS[driver.toLowerCase()] ?? driver}`,
  );
}

/** 日期闭合线（balance-basis）同名行说明：行键仅含来源/类型/计量口径，仓位与币种维度未展开。 */
const BASIS_DUPLICATE_LABEL_TITLE =
  "同名口径可能包含不同资产负债方向或币种，金额因此不同；请到资产负债分析页查看完整明细。";

function DetailPanelBody({
  panel,
  embedded = false,
}: {
  panel: ModuleHomeDetailPanel;
  embedded?: boolean;
}) {
  const isPnlPanel = panel.key === "pnl-attribution-summary";
  const isBasisPanel = panel.key === "balance-basis";
  const labelCounts = new Map<string, number>();
  if (isBasisPanel) {
    for (const row of panel.rows) {
      labelCounts.set(row.label, (labelCounts.get(row.label) ?? 0) + 1);
    }
  }
  const body = (
    <>
      <div className={embedded ? styles.embeddedPanelHead : dhStyles.dhTerminalPanelHead}>
        {!embedded ? <h3>{panel.title}</h3> : null}
        <span className={statePillClass(panel.tone)}>{panel.stateLabel}</span>
      </div>
      <p className={styles.detailSource}>{portfolioSourceLabel(panel.meta)}</p>
      {panel.rows.length > 0 ? (
        <ul className={styles.detailList}>
          {panel.rows.map((row) => {
            const displayValue = isPnlPanel ? localizePnlFindingText(row.value) : row.value;
            const duplicateLabel = isBasisPanel && (labelCounts.get(row.label) ?? 0) > 1;
            return (
              <li className={styles.detailRow} key={row.key}>
                <div className={styles.detailTop} data-value-kind={detailValueKind(row.value)}>
                  <span
                    className={styles.detailLabel}
                    title={duplicateLabel ? BASIS_DUPLICATE_LABEL_TITLE : undefined}
                  >
                    {row.label}
                  </span>
                  <span
                    className={`${styles.detailValue} ${toneClass(row.tone)}`}
                    title={displayValue === row.value ? undefined : row.value}
                  >
                    {displayValue}
                  </span>
                </div>
                {row.source && !PORTFOLIO_TECHNICAL_FIELDS.has(row.source) ? <span className={styles.detailSource}>{row.source}</span> : null}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className={`${styles.detailSource} ${toneClass(panel.tone)}`} data-empty>
          {panel.stateDetail}
        </p>
      )}
    </>
  );

  if (embedded) {
    return <div className={styles.embeddedPanel}>{body}</div>;
  }

  return body;
}

function snapshotRows(panel: ModuleHomeDistributionPanel) {
  return [...panel.rows].sort((left, right) => right.barPct - left.barPct).slice(0, 3);
}

function distributionContextLabel(panel: ModuleHomeDistributionPanel) {
  const readyPrefixes: Record<string, string> = {
    rating: "asset-structure / rating 已返回。",
    maturity: "maturity-structure 已返回。",
    industry: "industry-distribution 已返回；",
  };
  const prefix = readyPrefixes[panel.key];
  let detail = panel.stateDetail;
  if (prefix) {
    if (detail.startsWith(prefix)) detail = detail.slice(prefix.length).trim();
    const mockNote = "MOCK 模式保留结构样例用于页面视觉验收；不可作为正式组合读数或调仓依据。";
    if (detail.endsWith(mockNote)) {
      detail = `${detail.slice(0, -mockNote.length).trim()} 模拟数据，不可用于业务决策。`.trim();
    }
  }
  return [portfolioSourceLabel(panel.meta), detail].filter(Boolean).join(" ");
}

function PortfolioChartSnapshot({ panels }: { panels: ModuleHomeDistributionPanel[] | undefined }) {
  const visiblePanels = panels?.slice(0, 3) ?? [];

  if (visiblePanels.length === 0) {
    return null;
  }

  return (
    <section data-testid="module-home-portfolio-chart-snapshot" className={styles.chartSnapshot}>
      <div className={styles.chartSnapshotHead}>
        <span>结构分布</span>
        <strong>结构快照</strong>
      </div>
      <div className={styles.chartSnapshotGrid}>
        {visiblePanels.map((panel) => {
          const rows = snapshotRows(panel);
          return (
            <article
              className={styles.chartSnapshotCard}
              data-tone={panel.tone}
              data-testid={`module-home-distribution-${panel.key}`}
              key={panel.key}
            >
              <div className={styles.chartSnapshotCardHead}>
                <span title={panel.title}>{panel.title}</span>
                <strong>{panel.totalDisplay ?? panel.stateLabel}</strong>
              </div>
              <span className={styles.srOnly}>
                {distributionContextLabel(panel)}
              </span>
              {rows.length > 0 ? (
                <div className={styles.chartMiniBars}>
                  {rows.map((row, index) => {
                    const width = `${Math.max(5, Math.min(row.barPct, 100))}%`;
                    return (
                      <div className={styles.chartMiniRow} key={row.key}>
                        <span className={styles.chartMiniLabel} title={row.label}>
                          {row.label}
                        </span>
                        <span className={styles.chartMiniMetric}>
                          {row.share !== EM_DASH ? row.share : `${row.barPct.toFixed(2)}%`}
                        </span>
                        <span className={styles.chartMiniTrack} aria-hidden="true">
                          <span
                            className={styles.chartMiniFill}
                            data-color-index={index}
                            style={{ "--chart-mini-width": width } as CSSProperties}
                          />
                        </span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className={styles.chartMiniSkeleton} aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function WorkbenchSectionHead({
  titleId,
  title,
  detail,
  meta,
  action,
}: {
  titleId: string;
  index: string;
  title: string;
  detail: string;
  meta?: string | string[];
  action?: ReactNode;
}) {
  // 元信息逐条成徽标，避免把多个字段用 `·` 串成一行（DESIGN.md §7 配额）。
  const metaList = meta ? (Array.isArray(meta) ? meta : [meta]) : [];
  return (
    <div className={styles.workbenchSectionHead}>
      <div>
        <h2 id={titleId}>{title}</h2>
        <p>{detail}</p>
      </div>
      {metaList.length > 0 || action ? (
        <div className={styles.workbenchSectionMeta}>
          {metaList.map((item) => (
            <em key={item} title={item}>
              {item}
            </em>
          ))}
          {action}
        </div>
      ) : null}
    </div>
  );
}

const FACT_KPI_LABEL_MAP: Record<string, string> = {
  信用占比: "信用占比",
  DV01: "DV01 合计",
};

function isEmptyReading(value: string) {
  return value === EM_DASH;
}

/** muted 是缺数而非分析口径，不能与 watch 一样标成「仅分析」。 */
function exposureStateLabel(tone: ModuleHomeTone) {
  if (tone === "ok") return "可读";
  if (tone === "error") return "阻断";
  if (tone === "muted") return "缺数";
  return "仅分析";
}

function PortfolioExposureLedger({ view }: { view: ModuleHomeView }) {
  const exposureFacts = view.decision ? splitDecisionFacts(view.decision.facts).exposure : [];
  const matchedKpiLabels = new Set<string>();

  const factRows = exposureFacts.map((fact) => {
    const mappedLabel = FACT_KPI_LABEL_MAP[fact.label];
    const matchedKpi = mappedLabel ? view.kpis.find((item) => item.label === mappedLabel) : undefined;
    if (matchedKpi) {
      matchedKpiLabels.add(matchedKpi.label);
    }
    const fallbackKpi =
      isEmptyReading(fact.value) && matchedKpi && !isEmptyReading(matchedKpi.value)
        ? matchedKpi
        : undefined;
    const value = fallbackKpi ? fallbackKpi.value : compactFactValue(fact);
    const tone = fallbackKpi ? fallbackKpi.tone : fact.tone;
    return {
      key: `fact-${fact.label}`,
      label: fact.label,
      value,
      tone,
      state: exposureStateLabel(tone),
      action: tone === "ok" ? "持仓透视" : "风险复核",
    };
  });

  const kpiRows = view.kpis
    .filter((item) => !matchedKpiLabels.has(item.label))
    .slice(0, 5)
    .map((item) => ({
      key: `kpi-${item.key}`,
      label: item.label,
      value: item.value,
      tone: item.tone,
      state: exposureStateLabel(item.tone),
      action: item.detail || "组合复核",
    }));

  const rows = [...factRows, ...kpiRows].slice(0, 5);

  return (
    <div data-testid="module-home-portfolio-exposure-ledger" className={styles.exposureLedger}>
      {rows.length > 0 ? (
        <div className={styles.exposureLedgerTable} role="table" aria-label="关键暴露账本">
          <div className={styles.exposureLedgerHeader} role="row">
            <span role="columnheader">维度</span>
            <span role="columnheader">读数</span>
            <span role="columnheader">状态</span>
            <span role="columnheader">动作</span>
          </div>
          {rows.map((row) => (
            <div className={styles.exposureLedgerRow} data-tone={row.tone} role="row" key={row.key}>
              <span role="cell">{row.label}</span>
              <strong className={toneClass(row.tone)} role="cell">{row.value}</strong>
              <span role="cell">{row.state}</span>
              <em role="cell">{compactActionEvidence(row.action)}</em>
            </div>
          ))}
        </div>
      ) : (
        <p className={`${styles.dataNote} ${styles.toneWatch}`} data-empty>
          当前无可用暴露事实；不展示样例读数。
        </p>
      )}
    </div>
  );
}

function structureTabBadge(panel: ModuleHomeDetailPanel | undefined) {
  return panel && panel.rows.length > 0 ? String(panel.rows.length) : "空";
}

function structureStatusSummary(tabs: PortfolioStructureTab[]) {
  const emptyTabs = tabs.filter((tab) => !tab.panel || tab.panel.rows.length === 0);
  if (emptyTabs.length === 0) {
    return `${tabs.length}/${tabs.length} 个结构就绪`;
  }
  return `${emptyTabs.length} 个结构为空：${emptyTabs.map((tab) => tab.label).join("、")}`;
}

function StructureTabLabel({ tab }: { tab: PortfolioStructureTab }) {
  return (
    <span
      className={styles.structureTabLabel}
      data-testid={`module-home-analysis-tab-${tab.key}`}
    >
      <span>{tab.label}</span>
      <small className={styles.structureTabBadge}>{structureTabBadge(tab.panel)}</small>
    </span>
  );
}

function splitDecisionFacts(facts: PortfolioDecisionFact[]) {
  return {
    exposure: facts.slice(0, 6),
    evidence: facts.slice(6),
  };
}

function decisionUseLabel(decision: NonNullable<ModuleHomeView["decision"]>) {
  const decisionText = `${decision.conclusion} ${decision.detail}`;
  if (decisionText.includes("仅供分析")) return "仅供分析";
  if (decisionText.includes("仅供监控")) return "仅供监控";
  if (decisionText.includes("不可用于业务决策") || decision.tone === "error") return "不可用于业务决策";
  return "待复核";
}

const EVIDENCE_BASIS_LABELS: Record<string, string> = {
  formal: "正式口径",
  scenario: "情景口径",
  analytical: "分析口径",
  ledger: "台账口径",
  mock: "样例口径",
};

const EVIDENCE_QUALITY_LABELS: Record<string, string> = {
  ok: "正常",
  warning: "关注",
  error: "异常",
  stale: "陈旧",
  missing: "缺失",
};

/** 摘要「证据」列的中英混排句改完整中文短句（B7）；原文保留在 title。 */
function localizeBriefEvidence(text: string) {
  return localizeEvidenceTokens(text)
    .replace(/使用 pnl-attribution summary/g, "归因摘要见收益归因页")
    .replace(/完整瀑布图在 \/pnl-attribution/g, "完整瀑布图见收益归因页")
    .replace(/直接展示 headline \/ risk-indicators 字段，不以前端估算监管 DV01。/g, "风险指标口径见债券分析；监管 DV01 以已核验数据为准。")
    .replace(/使用 balance-analysis overview 字段展示，不做净额补算。/g, "按资产负债口径展示，资产与负债分别列示。")
    .replace(/已挂接 basis 分解 (\d+) 行；不做净额补算。/g, "按计量口径分解，共 $1 项；资产与负债分别列示。")
    .replace("正式展示以 API 来源元数据 的报告日、证据行数和来源表为准。", "请切换正式数据后查看报告日、组合读数和使用限制。");
}

/** 结论与读数位只出现业务语言；口径原文仍保留在 title 与屏幕阅读器文本中。 */
function localizeEvidenceTokens(text: string) {
  return compactActionEvidence(text)
    .replace(/\s*basis=([a-z_]+)/g, (token, basis: string) =>
      EVIDENCE_BASIS_LABELS[basis] ? `为${EVIDENCE_BASIS_LABELS[basis]}` : token,
    )
    .replace(/\s*quality=([a-z_]+)/g, (token, quality: string) =>
      EVIDENCE_QUALITY_LABELS[quality] ? `质量标记为${EVIDENCE_QUALITY_LABELS[quality]}` : token,
    )
    .replace(/\s*formal_use_allowed=true/g, "已允许正式使用")
    // 「风险闭合证据 meta_date=…」的标签已含「证据」，吞掉它避免「证据证据日期」叠词。
    .replace(/(?:证据)?\s*meta_date=(\d{4}-\d{2}-\d{2})/g, "证据日期 $1")
    .replace(/\s*report_date=(\d{4}-\d{2}-\d{2})/g, "报告日 $1")
    .replace(/\s*fallback=none/g, "无回退")
    .replace(/\s*fallback=([^\s；。，,]+)/g, "回退口径 $1")
    .replaceAll("风险张量未闭合至", "风险数据尚未更新至")
    .replaceAll("风险闭合证据", "风险数据")
    .replaceAll("风险张量未同日闭合", "风险数据与报告日尚不一致")
    .replaceAll("同日闭合", "数据日期一致")
    .replaceAll("读链路异常", "数据读取失败");
}

function compactDecisionDetail(detail: string) {
  const parts = [
    detail.includes("不生成调仓建议") ? "不生成调仓建议" : "",
    // 「风险闭合：风险闭合证据…」的标签与证据名同源，展示位去掉重复前缀。
    (detail.match(/风险闭合：([^；。]+)/)?.[0] ?? "").replace(/^风险闭合：(?=风险闭合)/, ""),
  ].filter(Boolean);
  return localizeEvidenceTokens(parts.join("；"))
    .replaceAll("风险闭合：", "风险数据：");
}

function compactFactValue(fact: PortfolioDecisionFact) {
  if (fact.label.includes("源日期")) {
    const entries = fact.value
      .split("；")
      .map((entry) => entry.match(/^(.+?)=(\d{4}-\d{2}-\d{2})$/))
      .filter((entry): entry is RegExpMatchArray => Boolean(entry));
    const dates = Array.from(new Set(entries.map((entry) => entry[2])));
    if (entries.length > 0 && dates.length === 1) return `${entries.length} 个来源 / ${dates[0]}`;
    if (entries.length > 0 && dates.length > 1) return `${entries.length} 个来源 / ${dates.join(" / ")}`;
  }
  return localizeEvidenceTokens(fact.value);
}

function compactActionEvidence(evidence: string) {
  return evidence
    .replace(/\s*basis=analytical/g, "为分析口径")
    .replace(/\s*formal_use_allowed=false/g, "尚未允许正式使用")
    .replace(/\s*quality=warning/g, "质量标记为关注")
    .replace(/\s*report_date 缺失/g, "报告日缺失")
    .replace(/bond-dashboard 的 result_meta、正式使用许可、质量标记和报告日/g, "债券总览的来源版本、使用许可、质量标记和报告日")
    .replace(/pnl-attribution 的正式口径、质量标记和报告日/g, "收益归因的正式口径、质量标记和报告日")
    .replace(/result_meta/g, "来源元数据");
}

function uniqueTextParts(parts: Array<string | null | undefined | false>) {
  return Array.from(new Set(parts.filter((part): part is string => Boolean(part))));
}

function compactKpiDetail(detail: string, valueCarriesUnit = false) {
  const movement = detail.match(/(?:环比|较前日)\s*[+＋−-]?\d+(?:\.\d+)?\s*(?:%|只|bp|亿)?/)?.[0];
  const parts = uniqueTextParts([
    detail.includes("资产负债口径") ? "资产负债口径" : null,
    detail.includes("风险指标") ? "风险指标" : null,
    // 值行已带单位时注行不再重复单位（B5）。
    !valueCarriesUnit && detail.includes("按亿元展示") ? "亿元" : null,
    !valueCarriesUnit && detail.includes("按万元展示") ? "万元" : null,
    detail.includes("未返回") ? "未返回" : null,
    movement,
  ]);

  if (parts.length > 0) {
    return parts.join(" · ");
  }
  // 注行原本只有单位 chip 时，去重后保留口径首段，避免注行（含 title 口径说明）整体消失。
  if (valueCarriesUnit && /按[亿万]元展示/.test(detail)) {
    return detail.split(/[，。]/)[0]?.trim() ?? "";
  }
  return "";
}

/**
 * 口径澄清（B4）：后端字段 credit_spread_median 实为信用债 YTM 中位数
 * （与 /bond-analysis、/bond-dashboard 同源同口径），按“信用利差”直呼会造成
 * 230bp 级利差误读，展示层统一改名并在 title 注明口径。
 */
const KPI_LABEL_OVERRIDES: Record<string, { label: string; title: string }> = {
  "bond-credit-spread": {
    label: "信用债收益率中位数",
    title:
      "信用债到期收益率（YTM）中位数，非对国债利差；与债券分析页同源同口径。",
  },
};

/** DV01 为每基点价值敏感度，单位口径与债券总览页一致为 万元/bp（B5）。 */
function kpiUnitDisplay(itemKey: string, unit: string) {
  if (itemKey === "bond-dv01" && unit === "万元") {
    return "万元/bp";
  }
  return unit;
}

const PRIMARY_KPI_KEYS = ["bond-market", "bond-duration", "bond-ytm", "bond-dv01", "bond-credit-ratio"] as const;

function splitKpisByPriority(kpis: ModuleHomeKpi[]) {
  const primaryKeySet = new Set<string>(PRIMARY_KPI_KEYS);
  const primary = PRIMARY_KPI_KEYS.map((key) => kpis.find((item) => item.key === key)).filter(
    (item): item is ModuleHomeKpi => Boolean(item),
  );
  const secondary = kpis.filter((item) => !primaryKeySet.has(item.key));
  return { primary, secondary };
}

function kpiScopeNote(kpis: ModuleHomeKpi[]) {
  const text = kpis.map((item) => item.detail).join(" ");
  return uniqueTextParts([
    text.includes("债券总览") ? "债券总览" : null,
    text.includes("分析/复核口径") ? "分析/复核口径" : null,
    text.includes("仅展示读数") ? "仅展示读数" : null,
    text.includes("不形成调仓建议") ? "不形成调仓建议" : null,
    text.includes("不纳入风险 ticker") ? "暂不用于当前风险判断" : null,
  ]);
}

function PortfolioKpiCard({ item, variant }: { item: ModuleHomeKpi; variant: "primary" | "secondary" }) {
  const value = splitKpiValue(item.value);
  const missingValue = value.number === EM_DASH;
  const changeDirection = resolveMarketChangeDirection(item.detail, item.sparkline);
  const unitDisplay = kpiUnitDisplay(item.key, value.unit);
  const detail = compactKpiDetail(item.detail, Boolean(unitDisplay));
  const labelOverride = KPI_LABEL_OVERRIDES[item.key];

  return (
    <article
      className={kpiStyles.cell}
      data-kpi-cell="true"
      data-priority={variant}
      data-has-detail={Boolean(detail || item.coverageNote)}
      data-tone={item.tone}
      data-empty={missingValue ? "true" : undefined}
      data-testid={`module-home-portfolio-kpi-${item.key}`}
    >
      <span className={kpiStyles.label} title={labelOverride?.title ?? item.label}>
        {labelOverride?.label ?? item.label}
      </span>
      <div className={kpiStyles.valueRow} data-compact={value.number.length >= 9 ? "true" : undefined}>
        <div
          className={kpiStyles.value}
          data-tone={!missingValue && item.tone === "error" ? "negative" : undefined}
          data-empty={missingValue ? "true" : undefined}
        >
          {/* 缺数时 value.number 本身即 EM_DASH；不用「待核验」暗示存在待验值。 */}
          <span>{value.number}</span>
        </div>
        {unitDisplay ? <small className={kpiStyles.unit}>{unitDisplay}</small> : null}
        {/* sparkline 数据仅有上期/本期两点，连线是一条误导性的伪曲线；
            待后端提供 KPI 历史序列后再恢复真实走势线，当前由涨跌文字承担方向语义。 */}
      </div>
      {detail ? (
        <div
          className={kpiStyles.delta}
          data-testid={`module-home-portfolio-kpi-${item.key}-detail`}
          data-change={changeDirection ?? "flat"}
          data-tone={changeDirection === "up" ? "positive" : changeDirection === "down" ? "negative" : "neutral"}
          title={localizeBriefEvidence(item.detail).replaceAll("不纳入风险 ticker", "暂不用于当前风险判断")}
          aria-label={`${item.label}: ${localizeBriefEvidence(item.detail).replaceAll("不纳入风险 ticker", "暂不用于当前风险判断")}`}
        >
          {detail}
        </div>
      ) : null}
      {item.coverageNote ? <p className={styles.coverageNote}>{item.coverageNote}</p> : null}
    </article>
  );
}

function sourceEvidenceSummary(lines: string[]) {
  const text = lines.join(" ");
  const reportDate = text.match(/report_date=\d{4}-\d{2}-\d{2}/)?.[0];
  const sources = Array.from(new Set(Array.from(text.matchAll(/\bfact_[a-z0-9_]+/g), (match) => match[0])));
  const fallback = text.includes("fallback=none") ? "无回退" : null;
  return uniqueTextParts([
    reportDate ? reportDate.replace("report_date=", "日期 ") : null,
    sources.length > 0 ? `${sources.length} 个正式来源` : `${lines.length} 条证据`,
    fallback,
  ]);
}

function splitKpiValue(value: string) {
  const trimmed = value.trim();
  const match = trimmed.match(/^([+-]?\d[\d,]*(?:\.\d+)?)(.*)$/);

  if (!match) {
    return { number: trimmed, unit: "" };
  }

  return {
    number: match[1],
    unit: match[2].trim(),
  };
}

function DecisionFact({ fact }: { fact: PortfolioDecisionFact }) {
  const displayValue = compactFactValue(fact);
  const displayLabel = ({ 数据链路: "数据状态", 风险闭合: "风险数据日期", 正式链路: "正式数据" } as Record<string, string>)[fact.label] ?? fact.label;

  return (
    <div
      className={styles.decisionFact}
      aria-label={`${displayLabel}: ${displayValue}`}
      title={`${displayLabel}: ${displayValue}`}
    >
      <span>{displayLabel}</span>
      <strong className={toneClass(fact.tone)}>{displayValue}</strong>
    </div>
  );
}

function DecisionPanel({ view }: { view: ModuleHomeView }) {
  if (!view.decision) {
    return null;
  }

  const actions = view.decision.actions ?? [];
  const factGroups = splitDecisionFacts(view.decision.facts);
  const useLabel = decisionUseLabel(view.decision);
  const headlineFacts = factGroups.evidence;
  const supportFacts = factGroups.exposure;

  return (
    <section
      data-testid="module-home-decision"
      className={`${dhStyles.dhCard} ${styles.decisionPanel}`}
      data-layout="banner"
      data-has-actions={actions.length > 0}
    >
      <div className={styles.decisionLedger}>
        <div className={styles.decisionLedgerHead}>
          <span className={`${styles.decisionStatusDot} ${toneClass(view.decision.tone)}`} aria-hidden="true" />
          <span className={styles.decisionKicker}>组合复核</span>
          <span hidden>{view.decision.title}</span>
        </div>
        <h2 className={styles.decisionTitle} data-testid={view.decision.conclusion.includes(useLabel) ? "module-home-decision-use-level" : undefined}>
          {localizeEvidenceTokens(view.decision.conclusion)}
        </h2>
        <p className={styles.decisionDetail} title={compactDecisionDetail(view.decision.detail)}>
          {compactDecisionDetail(view.decision.detail)}
        </p>
        {/* 使用级别全卡只此一处字段：结论标题承担唯一强调，这里保持安静读数。 */}
        {!view.decision.conclusion.includes(useLabel) ? <div className={styles.decisionReadinessBar} aria-label={`${view.decision.title}: ${useLabel}`}>
          <span>业务可用</span>
          <strong
            className={toneClass(view.decision.tone)}
            data-testid="module-home-decision-use-level"
          >
            {useLabel}
          </strong>
        </div> : null}
      </div>

      <div className={styles.decisionMatrix} data-testid="module-home-exposure-matrix">
        <div className={styles.terminalPanelHead}>
          <span>风险暴露</span>
          <strong>核心读数</strong>
        </div>
        <div className={styles.decisionFactGrid}>
          {supportFacts.map((fact) => (
            <DecisionFact fact={fact} key={fact.label} />
          ))}
        </div>
      </div>

      {headlineFacts.length > 0 || actions.length > 0 ? <div className={styles.evidenceConsole} data-testid="module-home-evidence-console">
        <div className={styles.terminalPanelHead}>
          <span>证据口径</span>
          <strong>来源 / 日期 / 可用范围</strong>
        </div>
        <div className={styles.evidenceFactList}>
          {headlineFacts.map((fact) => (
            <DecisionFact fact={fact} key={fact.label} />
          ))}
        </div>
        {actions.length > 0 ? (
          <div className={styles.decisionActionQueue}>
            <span className={styles.decisionActionLabel}>待复核</span>
            <div
              className={styles.decisionActionList}
              data-testid="module-home-portfolio-action-loop"
            >
              {actions.map((action, index) => (
                <Link
                  className={styles.decisionAction}
                  to={action.path}
                  key={action.title}
                  data-testid={index === 0 ? "module-home-portfolio-action-loop-primary" : undefined}
                >
                  <i data-row-index aria-hidden="true">
                    {String(index + 1).padStart(2, "0")}
                  </i>
                  <span className={`${styles.decisionActionDot} ${toneClass(action.tone)}`} />
                  <span className={styles.decisionActionText}>
                    <strong className={toneClass(action.tone)}>{action.title.replace("风险张量日期复核", "风险数据日期复核")}</strong>
                    <small>{localizeEvidenceTokens(action.evidence)}</small>
                  </span>
                  <span className={styles.decisionActionTarget}>
                    {action.label === "风险张量" ? "风险详情" : action.label ?? "下钻"}
                    <LightIcon name="arrow-right" />
                  </span>
                </Link>
              ))}
            </div>
          </div>
        ) : null}
      </div> : null}
    </section>
  );
}

function hasAnalyticalOnlySource(decision: ModuleHomeView["decision"]) {
  const readiness = decision?.readiness;
  return Boolean(
    readiness?.sourceFacts.some(
      (fact) =>
        fact.includes("basis=analytical") ||
        fact.includes("formal_use_allowed=false") ||
        fact.includes("quality=warning"),
    ) ||
      readiness?.blockingReasons.some(
        (reason) =>
          reason.includes("basis=analytical") ||
          reason.includes("formal_use_allowed=false") ||
          reason.includes("quality=warning"),
      ),
  );
}

const CLOSURE_GATE_VISIBLE_REASONS = 4;

function PortfolioClosureGate({ decision }: { decision: ModuleHomeView["decision"] }) {
  if (!decision?.readiness) {
    return null;
  }

  const { readiness } = decision;
  const riskBlocked = !readiness.riskClosureReady;
  const sourceBlocked = !readiness.decisionReady;
  const analyticalOnly = hasAnalyticalOnlySource(decision);
  const gateTone: ModuleHomeTone = riskBlocked || sourceBlocked ? "watch" : "ok";
  const gateTitle = riskBlocked
    ? "风险数据暂不可用"
    : sourceBlocked
      ? "决策口径未通过"
      : "风险数据与报告日一致";
  const gateDetail = riskBlocked
    ? readiness.riskClosureFact
    : sourceBlocked
      ? readiness.blockingReasons.join("；") || "来源证据未达到决策级口径。"
      : `同日闭合 ${readiness.sourceDates}`;
  const badges = [
    riskBlocked ? "暂不能判断当前风险" : "同日风险数据",
    analyticalOnly ? "仅供分析" : "正式口径",
  ];
  // 阻断原因是彼此独立的条目，逐条列出；拼成长句会失去可读性。
  const blockingList = !riskBlocked && sourceBlocked ? readiness.blockingReasons : [];
  const visibleReasons = blockingList.slice(0, CLOSURE_GATE_VISIBLE_REASONS);
  const hiddenReasonCount = blockingList.length - visibleReasons.length;

  return (
    <section
      className={`${dhStyles.dhCard} ${styles.closureGate} ${riskBlocked ? styles.closureGateBlocked : ""}`}
      data-testid="module-home-portfolio-closure-gate"
      data-state={riskBlocked ? "blocked" : sourceBlocked ? "source-review" : "ready"}
    >
      <div className={styles.closureGateHead}>
        <span>风险数据可用范围</span>
        <strong className={toneClass(gateTone)}>{gateTitle}</strong>
      </div>
      {blockingList.length > 0 ? (
        <ul
          className={styles.closureGateReasons}
          data-testid="module-home-portfolio-closure-reasons"
          title={blockingList.map((reason) => localizeEvidenceTokens(reason)).join("；")}
        >
          {visibleReasons.map((reason, index) => (
            <li key={`${reason}-${String(index)}`}>{localizeEvidenceTokens(reason)}</li>
          ))}
          {hiddenReasonCount > 0 ? <li data-more="">另有 {hiddenReasonCount} 项待复核</li> : null}
        </ul>
      ) : (
        <p className={styles.closureGateDetail}>{localizeEvidenceTokens(gateDetail)}</p>
      )}
      <div className={styles.closureGateBadges}>
        {badges.map((badge) => (
          <span key={badge}>{badge}</span>
        ))}
      </div>
    </section>
  );
}

export default function PortfolioHomeLayout({
  view,
  balanceReportDate,
  bondReportDate,
}: PortfolioHomeLayoutProps) {
  const stateTone: ModuleHomeTone =
    view.stateLabel === "读取失败" ? "error" : view.stateLabel === "读取中" ? "muted" : "ok";

  const riskPanel = panelByKey(view.detailPanels, "risk-indicators-detail");
  const basisPanel = panelByKey(view.detailPanels, "balance-basis");
  const pnlPanel = panelByKey(view.detailPanels, "pnl-attribution-summary");
  const assetTypePanel = view.distributionPanels?.find((panel) => panel.key === "asset-type");
  const portfolioComparisonPanel = panelByKey(view.detailPanels, "portfolio-comparison");
  const secondaryDistributionPanels =
    view.distributionPanels?.filter((panel) => panel.key !== "asset-type") ?? [];
  const readiness = view.decision?.readiness;
  const riskClosureBlocked = Boolean(readiness && !readiness.riskClosureReady);
  const analyticalOnlySource = hasAnalyticalOnlySource(view.decision);
  const riskTickerUnavailable = riskClosureBlocked || riskPanel?.tone !== "ok";
  const riskTickerUnavailableTitle = riskClosureBlocked ? "风险数据暂不可用" : "风险读数不可用";
  const riskTickerUnavailableDetail = riskClosureBlocked
    ? `${readiness?.riskClosureFact ?? "风险数据未返回"}；暂不能判断当前风险。`
    : riskPanel ? portfolioStatusDetail({ detail: riskPanel.stateDetail }) : undefined;
  const kpiGroups = useMemo(() => {
    const { primary, secondary } = splitKpisByPriority(view.kpis);
    return { primary, secondary, scopeNote: kpiScopeNote(view.kpis) };
  }, [view.kpis]);

  const structureTabs = useMemo<PortfolioStructureTab[]>(() => {
    const map = new Map(view.detailPanels?.map((panel) => [panel.key, panel]) ?? []);
    return ANALYSIS_TABS.map((tab) => ({
      ...tab,
      panel: map.get(tab.key),
    }));
  }, [view.detailPanels]);

  const structureGapTabs = structureTabs.filter((tab) => !tab.panel || tab.panel.rows.length === 0);
  const sourceIssues = view.statuses.slice(0, 4).filter((item) => item.tone !== "ok");
  const technicalFields = (view.detailPanels ?? []).flatMap((panel) => panel.rows
    .filter((row) => row.source)
    .map((row) => `${panel.title} / ${row.label}：${row.source}`));

  const tabItems = useMemo(() => {
    return structureTabs.map((tab) => {
      const panel = tab.panel;
      return {
        key: tab.key,
        label: <StructureTabLabel tab={tab} />,
        children: panel ? (
          <PortfolioStructureTabPanel panel={panel} />
        ) : (
          <p className={`${styles.structureEmptyState} ${styles.toneWatch}`} data-empty>
            当前无可用正式结构读数；样例明细不作为业务决策依据。
          </p>
        ),
      };
    });
  }, [structureTabs]);

  return (
    <>
      <header data-testid="module-home-toolbar" className={`${dhStyles.dhTopbar} ${styles.portfolioTopbar}`}>
        <div className={`${dhStyles.dhTopbarLeft} ${styles.portfolioTopbarLeft}`}>
          <div className={dhStyles.dhTitleBrand}>
            <h1 className={dhStyles.dhTitle}>{view.title}</h1>
          </div>
          <div className={styles.topbarCopy}>
            <p className={styles.topbarSubtitle}>关注组合规模、久期、结构与损益变化。</p>
          </div>
        </div>
        <div className={`${dhStyles.dhTopbarRight} ${styles.portfolioTopbarMeta}`}>
          <div className={styles.toolbarMeta}>
            {!/^(已同步|已接入|已就绪)$/.test(view.stateLabel) ? <span className={styles.toolbarState} data-tone={stateTone}>
              <i aria-hidden="true" />
              {view.stateLabel}
            </span> : null}
            {balanceReportDate && balanceReportDate === bondReportDate ? (
              <span className={styles.datePill}>
                报告日 <strong>{bondReportDate}</strong>
              </span>
            ) : <>
            <span className={styles.datePill}>
              资产负债日 <strong>{balanceReportDate || EM_DASH}</strong>
            </span>
            <span className={styles.datePill}>
              债券总览日 <strong>{bondReportDate || EM_DASH}</strong>
            </span>
            </>}
          </div>
        </div>
      </header>

      <div className={`${dhStyles.dhMain} ${styles.portfolioPageMain}`}>
        <section data-testid="module-home-portfolio-cockpit" className={styles.portfolioCockpit}>
          <section data-testid="module-home-portfolio-review-band" className={styles.portfolioReviewBand}>
            <section data-testid="module-home-portfolio-first-screen" className={styles.portfolioPrimaryGrid}>
              <div className={styles.portfolioPrimaryColumn}>
                <DecisionPanel view={view} />

                <section data-testid="module-home-kpi-strip" className={styles.sectionBlock}>
                  <SectionHead title="核心指标" numbered={false} />
                  {kpiGroups.scopeNote.length > 0 ? (
                    <p className={styles.kpiScopeNote} data-testid="module-home-portfolio-kpi-scope-note">
                      {kpiGroups.scopeNote.map((part) => (
                        <span key={part}>{part}</span>
                      ))}
                    </p>
                  ) : null}
                  <div
                    className={`${kpiStyles.strip} ${styles.portfolioKpiBand}`}
                    data-cols-xl="5"
                    data-cols-lg="5"
                    data-cols-md="3"
                    data-cols-base="2"
                    data-size="compact"
                    role="region"
                    aria-label="组合核心指标"
                  >
                      {kpiGroups.primary.map((item) => (
                        <PortfolioKpiCard item={item} variant="primary" key={item.key} />
                      ))}
                      {kpiGroups.secondary.map((item) => (
                        <PortfolioKpiCard item={item} variant="secondary" key={item.key} />
                      ))}
                  </div>
                </section>

                <PortfolioRiskTickerBar
                  riskPanel={riskPanel}
                  unavailable={riskTickerUnavailable}
                  unavailableTitle={riskTickerUnavailableTitle}
                  unavailableDetail={localizeEvidenceTokens(riskTickerUnavailableDetail ?? "")}
                />
              </div>
            </section>

            <section data-testid="module-home-portfolio-data-workbench" className={styles.portfolioDataWorkbench}>
              <div className={styles.workbenchMain}>
                  <nav
                    data-testid="module-home-portfolio-data-nav"
                    className={styles.workbenchNav}
                    aria-label="组合数据工作台"
                    title="结构、归因、明细按业务动作串联，保留来源状态与复核入口。"
                  >
                    {WORKBENCH_NAV_ITEMS.map((item) => (
                      <a href={item.href} key={item.href} title={item.detail}>
                        {item.label}
                      </a>
                    ))}
                  </nav>

                  <section
                    id="portfolio-holdings-workbench"
                    aria-labelledby="portfolio-holdings-workbench-title"
                    data-testid="module-home-portfolio-holdings-workbench"
                    className={`${styles.workbenchSection} ${styles.holdingsWorkbenchSection}`}
                  >
                    <WorkbenchSectionHead
                      titleId="portfolio-holdings-workbench-title"
                      index="01"
                      title="持仓结构全景"
                      detail="券种、子组合与关键暴露并排复核。"
                    />
                    <div className={styles.holdingsPanoramaGrid}>
                      <PortfolioHoldingsHeroBand
                        panel={assetTypePanel}
                        portfolioComparisonPanel={portfolioComparisonPanel}
                      />
                      <section
                        id="portfolio-exposure-workbench"
                        aria-labelledby="portfolio-exposure-workbench-title"
                        data-testid="module-home-portfolio-exposure-workbench"
                        className={styles.exposureWorkbenchSection}
                      >
                        <div className={styles.exposureWorkbenchHead}>
                          <h2 id="portfolio-exposure-workbench-title">关键暴露账本</h2>
                          <p>集中查看信用暴露、DV01、归因与数据可用范围。</p>
                        </div>
                        <PortfolioExposureLedger view={view} />
                      </section>
                    </div>
                  </section>

                  <section
                    id="portfolio-structure-workbench"
                    aria-labelledby="portfolio-structure-workbench-title"
                    data-testid="module-home-portfolio-structure-workbench"
                    className={`${styles.portfolioStructureWorkbench} ${styles.workbenchSection}`}
                  >
                    <WorkbenchSectionHead
                      titleId="portfolio-structure-workbench-title"
                      index="02"
                      title="结构拆解工作台"
                      detail="子组合、收益率、券种收益率、业务类型统一按表格核对。"
                      meta={`${structureTabs.length} 个结构维度`}
                    />
                    <section
                      data-testid="module-home-portfolio-terminal"
                      className={`${dhStyles.dhCard} ${styles.terminalCard} ${styles.sectionBlock} ${styles.structureTableWorkbench}`}
                    >
                      {/* data-gaps=0 时皮肤层隐藏冗余的「4/4 就绪」表头；有缺口时必须可见。 */}
                      <div className={styles.structureTableHead} data-gaps={structureGapTabs.length}>
                        <div
                          className={styles.structureStatusBar}
                          data-testid="module-home-structure-status-summary"
                        >
                          {structureStatusSummary(structureTabs)}
                        </div>
                        <span>结构明细按页签核对</span>
                      </div>
                      {structureGapTabs.length > 0 ? (
                        <div className={styles.structureGapActions} data-testid="module-home-structure-gap-actions">
                          {structureGapTabs.map((tab) => (
                            <Link
                              key={tab.key}
                              className={styles.structureGapAction}
                              to={bondDashboardGapLink(tab.key, bondReportDate)}
                              data-testid={`module-home-structure-gap-action-${tab.key}`}
                            >
                              {tab.label}为空 · 去债券总览复核
                            </Link>
                          ))}
                        </div>
                      ) : null}
                      <Tabs items={tabItems} />
                    </section>
                  </section>

                  <section
                    id="portfolio-risk-workbench"
                    aria-labelledby="portfolio-risk-workbench-title"
                    data-testid="module-home-portfolio-closure-band"
                    className={`${styles.portfolioClosureBand} ${styles.workbenchSection}`}
                  >
                    <WorkbenchSectionHead
                      titleId="portfolio-risk-workbench-title"
                      index="03"
                      title={riskClosureBlocked || analyticalOnlySource ? "分析读数与归因" : "收益与风险"}
                      detail="核对风险读数、收益归因及各项数据日期。"
                      meta={riskClosureBlocked ? "风险数据待核验" : "可进入复核"}
                    />
                    <div className={styles.closureWorkbenchGrid}>
                      <PortfolioClosureGate decision={view.decision} />
                      {riskPanel ? (
                        <article className={`${styles.closureReviewCard} ${styles.closureReviewCardRisk}`} data-testid={detailPanelTestId(riskPanel.key)}>
                          <SectionHead category="风险" title="风险读数" numbered={false} />
                          <DetailPanelBody panel={riskPanel} embedded />
                        </article>
                      ) : null}
                      {pnlPanel ? (
                        <article className={styles.closureReviewCard} data-testid={detailPanelTestId(pnlPanel.key)}>
                          <SectionHead category="归因" title="收益归因" numbered={false} />
                          <DetailPanelBody panel={pnlPanel} embedded />
                        </article>
                      ) : null}
                      {basisPanel ? (
                        <article className={styles.closureReviewCard} data-testid={detailPanelTestId(basisPanel.key)}>
                          <SectionHead category="来源" title="资产负债口径" numbered={false} />
                          <DetailPanelBody panel={basisPanel} embedded />
                        </article>
                      ) : null}
                    </div>
                    <PortfolioAttributionWaterfall payload={view.pnlWaterfall} state={view.pnlWaterfallState} />
                  </section>

                  <section
                    id="portfolio-source-workbench"
                    aria-labelledby="portfolio-source-workbench-title"
                    data-testid="module-home-portfolio-source-workbench"
                    className={`${styles.sourceWorkbenchSection} ${styles.workbenchSection}`}
                  >
                    <WorkbenchSectionHead
                      titleId="portfolio-source-workbench-title"
                      index="04"
                      title="组合复盘摘要"
                      detail="分布、摘要与来源状态并排收口。"
                    />
                    <div className={styles.summaryLedgerGrid}>
                      <section data-testid="module-home-holdings-structure" className={styles.summaryLedgerCard}>
                        <SectionHead title="评级 / 期限 / 行业分布" numbered={false} />
                        <PortfolioChartSnapshot panels={secondaryDistributionPanels} />
                      </section>

                      <section data-testid="module-home-briefing" className={styles.summaryLedgerCard}>
                        <SectionHead title="组合摘要" numbered={false} />
                        <div className={styles.briefGrid} data-testid="module-home-briefing-ledger">
                          {view.briefings.map((item, index) => (
                            <article
                              className={`${dhStyles.dhCard} ${briefCardClass(item.tone, index === 0)}`}
                              key={item.title}
                            >
                              <span className={styles.briefTitle}>{item.title}</span>
                              <strong
                                className={`${styles.briefConclusion} ${toneClass(item.tone)}`}
                                title={item.conclusion}
                              >
                                {item.conclusion}
                              </strong>
                              <span className={styles.briefEvidence} title={localizeBriefEvidence(item.evidence)}>
                                {localizeBriefEvidence(item.evidence)}
                              </span>
                            </article>
                          ))}
                        </div>
                      </section>

                      {sourceIssues.length > 0 ? <section
                        data-testid="module-home-status-strip"
                        className={`${dhStyles.dhCard} ${styles.summaryLedgerCard} ${styles.statusStrip}`}
                      >
                        <SectionHead title="数据使用提示" numbered={false} />
                        <div className={styles.statusGrid} data-testid="module-home-status-ledger">
                          {sourceIssues.map((item) => (
                            <div className={styles.statusCell} key={item.key}>
                              <span>{item.label}</span>
                              <b className={toneClass(item.tone)} title={item.value}>
                                {item.value}
                              </b>
                              <em title={portfolioStatusDetail(item)}>{portfolioStatusDetail(item)}</em>
                            </div>
                          ))}
                        </div>
                      </section> : null}
                    </div>
                  </section>

                  <section
                    id="portfolio-action-workbench"
                    aria-labelledby="portfolio-action-workbench-title"
                    data-testid="module-home-portfolio-action-workbench"
                    className={`${styles.workbenchSection} ${styles.actionWorkbenchSection}`}
                  >
                    <WorkbenchSectionHead
                      titleId="portfolio-action-workbench-title"
                      index="05"
                      title="来源与使用说明"
                      detail="待复核事项可从本日结论进入；完整页面入口统一见顶部导航。"
                    />
                    {view.dataNote.lines.length > 0 || technicalFields.length > 0 || (view.distributionPanels?.length ?? 0) > 0 ? (
                      <details
                        className={`${styles.dataNote} ${styles.dataNoteDisclosure}`}
                        data-testid="module-home-data-note"
                      >
                        <summary>
                          <span>来源证据摘要</span>
                          <strong>
                            {sourceEvidenceSummary(view.dataNote.lines).map((part) => (
                              <span key={part}>{part}</span>
                            ))}
                          </strong>
                        </summary>
                        <div className={styles.dataNoteBody}>
                          <p>来源范围：债券总览、资产负债分析与收益归因。{view.decision ? `当前使用范围：${decisionUseLabel(view.decision)}。` : "请按各项数据日期和使用提示复核。"}</p>
                          <details>
                            <summary>技术诊断</summary>
                            {view.decision ? <p>{view.decision.detail}</p> : null}
                            {view.decision?.facts.map((fact) => <p key={`fact-${fact.label}`}>{fact.label}：{fact.value}</p>)}
                            {view.dataNote.lines.map((line, index) => <p key={`note-${index}`}>{line}</p>)}
                            {view.statuses.map((item) => <p key={item.key}>{item.label}：{item.value}；{item.detail}</p>)}
                            {view.detailPanels?.map((panel) => <p key={`panel-${panel.key}`}>{panel.title}：{panel.stateDetail}；{panel.meta}</p>)}
                            {view.distributionPanels?.map((panel) => <p key={`distribution-${panel.key}`}>{panel.title}：{panel.meta}；{panel.stateDetail}</p>)}
                            {technicalFields.map((line) => <p key={line}>{line}</p>)}
                            {view.briefings.map((item) => <p key={item.title}>{item.title}：{item.evidence}</p>)}
                            {view.kpis.map((item) => <p key={item.key}>{item.label}：{item.detail}</p>)}
                          </details>
                        </div>
                      </details>
                    ) : null}
                  </section>
                </div>
            </section>
          </section>
        </section>
      </div>
    </>
  );
}
