import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import {
  DataTable,
  SECTION_HEAD_STACK_CLASSNAME,
  SectionHead,
  StateSurface,
  type DataTableColumn,
  type SectionMetaField,
  type SectionState,
  type SectionStateTone,
  type SurfaceStatus,
} from "../../../components/layout";
import {
  buildModuleHomeView,
  type ModuleHomeDataState,
  type ModuleHomeDetailPanel,
  type ModuleHomeDetailRow,
  type ModuleHomeTone,
} from "./moduleHomeModel";
import {
  moduleWorkbenchHomeConfigs,
  type ModuleWorkbenchHomeKind,
} from "./moduleHomeConfig";
import styles from "./moduleWorkbenchHome.module.css";

type ModuleWorkbenchHomePageProps = {
  kind: ModuleWorkbenchHomeKind;
};

function toneClassName(tone: ModuleHomeTone) {
  if (tone === "ok") {
    return styles.toneOk;
  }
  if (tone === "watch") {
    return styles.toneWatch;
  }
  if (tone === "error") {
    return styles.toneError;
  }
  return styles.toneMuted;
}

function statePillClassName(tone: ModuleHomeTone) {
  if (tone === "ok") {
    return `${styles.pill} ${styles.pillOk}`;
  }
  if (tone === "error") {
    return `${styles.pill} ${styles.pillError}`;
  }
  if (tone === "watch") {
    return `${styles.pill} ${styles.pillWatch}`;
  }
  return styles.pill;
}

function pageStateTone(
  dataState: ModuleHomeDataState | undefined,
  stateLabel: string,
): ModuleHomeTone {
  if (dataState === "error" || stateLabel === "读取失败") return "error";
  if (
    dataState === "empty" ||
    dataState === "partial" ||
    dataState === "stale" ||
    stateLabel === "部分失败" ||
    stateLabel === "部分无权限"
  ) {
    return "watch";
  }
  if (dataState === "loading" || stateLabel === "读取中") return "muted";
  return "ok";
}

function performanceStateMessage(status: SurfaceStatus) {
  if (status === "loading") return "正在读取绩效工作台";
  if (status === "empty") return "本年暂无可展示绩效数据";
  if (status === "error") return "绩效数据读取失败";
  if (status === "partial") return "绩效数据部分可用";
  if (status === "stale") return "绩效数据已经过期";
  return "绩效数据已就绪";
}

function currentYear() {
  return new Date().getFullYear();
}

/** detail panel key → 页面既有 testid（kind 无关映射，/performance 与 /reports 共用）。 */
function detailPanelTestId(panelKey: string) {
  if (panelKey === "kpi-metric-detail") {
    return "module-home-kpi-detail";
  }
  if (panelKey === "business-pnl-detail") {
    return "module-home-business-pnl";
  }
  if (panelKey === "source-status") {
    return "module-home-source-status";
  }
  if (panelKey === "cube-dimensions") {
    return "module-home-cube-dimensions";
  }
  if (panelKey === "health-checks") {
    return "module-home-health-checks";
  }
  return "module-home-detail-panels";
}

/**
 * 长读数降号防截断（首页 compact 先例的长度判据）：nowrap + ellipsis 下
 * 被截断的数字会被读成另一个数字，比降号更危险。中文状态词（读取失败等）
 * 通常 ≤6 字不触发，保持 §3 主值 20px 下限。
 */
function isCompactKpiValue(value: string) {
  return value.length >= 9;
}

/**
 * 分区状态：页面的四档 tone 里只有 ok 在原语的 SectionState 词表外——原语把
 * ready 定义成「不渲染状态位」，没有「绿色的已就绪徽标」这一档。为了不丢掉
 * 面板头上那句状态读数（§6 状态即内容），ok 档改由 meta 承载文案，只有颜色
 * 语义从绿降为中性；其余三档逐档同色（红 / 琥珀 / 中性）。
 */
const PANEL_STATE_TONE: Record<ModuleHomeTone, SectionStateTone | null> = {
  ok: null,
  watch: "partial",
  error: "error",
  muted: "loading",
};

function panelSectionState(panel: ModuleHomeDetailPanel): SectionState {
  const tone = PANEL_STATE_TONE[panel.tone];
  if (tone === null || !panel.stateLabel) return null;
  return { label: panel.stateLabel, tone };
}

/**
 * 面板 meta 是「标签 值」形状的展示串（如 `来源 kpi`）；这里只做一次拆分，
 * "·" 配额与竖线分栏交给 SectionHead 内部按字段数推导。ok 档的状态读数作为
 * 第一个字段并入，保证迁移前后没有任何一句文案从页面上消失。
 */
function panelSectionMeta(panel: ModuleHomeDetailPanel): SectionMetaField[] {
  const fields: SectionMetaField[] = [];
  if (PANEL_STATE_TONE[panel.tone] === null && panel.stateLabel) {
    fields.push({ label: "状态", value: panel.stateLabel, title: panel.stateDetail });
  }
  if (panel.meta) {
    const separator = panel.meta.indexOf(" ");
    fields.push(
      separator < 0
        ? { label: panel.meta, value: "" }
        : { label: panel.meta.slice(0, separator), value: panel.meta.slice(separator + 1) },
    );
  }
  return fields;
}

/*
 * 明细表列。读数列此前靠 `.detailValue` 的 nowrap + ellipsis 单行省略，对应
 * DataTable 的 `ellipsis`（它会把整表切到 table-layout: fixed，与原来
 * `.detailTable { table-layout: fixed }` 一致）；日期列 88px 宽度保持不变。
 */
const DETAIL_COLUMNS: readonly DataTableColumn<ModuleHomeDetailRow>[] = [
  { key: "label", title: "字段" },
  {
    key: "value",
    title: "读数",
    align: "numeric",
    ellipsis: true,
    render: (row) => <span className={toneClassName(row.tone)}>{row.value}</span>,
  },
  { key: "tradeDate", title: "日期", align: "numeric", width: 88 },
  { key: "source", title: "来源" },
];

function DetailRowsTable({
  rows,
  ariaLabel,
}: {
  rows: ModuleHomeDetailPanel["rows"];
  ariaLabel: string;
}) {
  return (
    <DataTable<ModuleHomeDetailRow>
      rows={rows}
      rowKey="key"
      columns={DETAIL_COLUMNS}
      emptyPolicy="collapse"
      ariaLabel={ariaLabel}
    />
  );
}

function DetailPanelBody({ panel }: { panel: ModuleHomeDetailPanel }) {
  const sections = panel.sections?.filter((section) => section.rows.length > 0) ?? [];

  if (sections.length > 0) {
    return (
      <div className={styles.detailSections}>
        {sections.map((section) => (
          <section className={styles.detailSection} key={section.key}>
            <div className={styles.detailSectionHeader}>
              <span className={styles.detailSectionTitle}>{section.title}</span>
              {section.subtitle ? (
                <span className={styles.detailSectionMeta}>{section.subtitle}</span>
              ) : null}
            </div>
            <DetailRowsTable
              rows={section.rows}
              ariaLabel={`${panel.title} · ${section.title}`}
            />
          </section>
        ))}
      </div>
    );
  }
  if (panel.rows.length > 0) {
    return <DetailRowsTable rows={panel.rows} ariaLabel={panel.title} />;
  }
  return (
    <p className={`${styles.detailEmpty} ${toneClassName(panel.tone)}`}>{panel.stateDetail}</p>
  );
}

export default function ModuleWorkbenchHomePage({
  kind,
}: ModuleWorkbenchHomePageProps) {
  const client = useApiClient();

  const choiceLatestQuery = useQuery({
    queryKey: ["module-home", "choice-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    enabled: kind === "market",
    retry: false,
    staleTime: 60_000,
  });
  const marketRatesQuery = useQuery({
    queryKey: ["module-home", "market-rates", client.mode],
    queryFn: () => client.getMarketDataRates(),
    enabled: kind === "market",
    retry: false,
    staleTime: 60_000,
  });
  const marketCatalogQuery = useQuery({
    queryKey: ["module-home", "market-catalog", client.mode],
    queryFn: () => client.getMarketDataCatalog(),
    enabled: kind === "market",
    retry: false,
    staleTime: 60_000,
  });

  const riskDatesQuery = useQuery({
    queryKey: ["module-home", "risk-dates", client.mode],
    queryFn: () => client.getRiskTensorDates(),
    enabled: kind === "risk",
    retry: false,
    staleTime: 60_000,
  });
  const riskReportDate = riskDatesQuery.data?.result.report_dates[0] ?? "";
  const riskTensorQuery = useQuery({
    queryKey: ["module-home", "risk-tensor", client.mode, riskReportDate],
    queryFn: () => client.getRiskTensor(riskReportDate),
    enabled: kind === "risk" && Boolean(riskReportDate),
    retry: false,
    staleTime: 60_000,
  });
  const cashflowQuery = useQuery({
    queryKey: ["module-home", "cashflow", client.mode, riskReportDate],
    queryFn: () => client.getCashflowProjection(riskReportDate),
    enabled: kind === "risk" && Boolean(riskReportDate),
    retry: false,
    staleTime: 60_000,
  });

  const year = useMemo(() => currentYear(), []);
  const kpiOwnersQuery = useQuery({
    queryKey: ["module-home", "kpi-owners", client.mode, year],
    queryFn: () => client.getKpiOwners({ year, is_active: true }),
    enabled: kind === "performance",
    retry: false,
    staleTime: 60_000,
  });
  const firstOwnerId = kpiOwnersQuery.data?.owners[0]?.owner_id;
  const kpiSummaryQuery = useQuery({
    queryKey: ["module-home", "kpi-summary", client.mode, year, firstOwnerId ?? "none"],
    queryFn: () =>
      client.getKpiValuesSummary({
        owner_id: firstOwnerId ?? 0,
        year,
        period_type: "YEAR",
      }),
    enabled: kind === "performance" && firstOwnerId !== undefined,
    retry: false,
    staleTime: 60_000,
  });
  const pnlYtdQuery = useQuery({
    queryKey: ["module-home", "pnl-ytd", client.mode, year],
    queryFn: () => client.getPnlByBusinessYtd(year),
    enabled: kind === "performance",
    retry: false,
    staleTime: 60_000,
  });

  const healthLiveQuery = useQuery({
    queryKey: ["module-home", "health-live", client.mode],
    queryFn: () => client.getHealthLive(),
    enabled: kind === "governance",
    retry: false,
    staleTime: 60_000,
  });
  const healthSummaryQuery = useQuery({
    queryKey: ["module-home", "health-summary", client.mode],
    queryFn: () => client.getHealthSummary(),
    enabled: kind === "governance",
    retry: false,
    staleTime: 60_000,
  });
  const sourceFoundationQuery = useQuery({
    queryKey: ["module-home", "source-foundation", client.mode],
    queryFn: () => client.getSourceFoundation(),
    enabled: kind === "governance",
    retry: false,
    staleTime: 60_000,
  });
  const cubeDimensionsQuery = useQuery({
    queryKey: ["module-home", "cube-dimensions", client.mode, "bond_analytics"],
    queryFn: () => client.getCubeDimensions("bond_analytics"),
    enabled: kind === "governance",
    retry: false,
    staleTime: 60_000,
  });

  // queries 对象包进 useMemo：只有任一 query 结果变化才更新引用，
  // 让下方 view 的 useMemo 能直接依赖 queries 本身（可静态校验）。
  const queries = useMemo(
    () => ({
      choiceLatest: choiceLatestQuery,
      marketRates: marketRatesQuery,
      marketCatalog: marketCatalogQuery,
      riskDates: riskDatesQuery,
      riskTensor: riskTensorQuery,
      cashflow: cashflowQuery,
      kpiOwners: kpiOwnersQuery,
      kpiSummary: kpiSummaryQuery,
      pnlYtd: pnlYtdQuery,
      healthLive: healthLiveQuery,
      healthSummary: healthSummaryQuery,
      sourceFoundation: sourceFoundationQuery,
      cubeDimensions: cubeDimensionsQuery,
    }),
    [
      choiceLatestQuery,
      marketRatesQuery,
      marketCatalogQuery,
      riskDatesQuery,
      riskTensorQuery,
      cashflowQuery,
      kpiOwnersQuery,
      kpiSummaryQuery,
      pnlYtdQuery,
      healthLiveQuery,
      healthSummaryQuery,
      sourceFoundationQuery,
      cubeDimensionsQuery,
    ],
  );
  const config = moduleWorkbenchHomeConfigs[kind];
  const view = useMemo(
    () => buildModuleHomeView(kind, client, queries),
    [kind, client, queries],
  );
  const hasFailedQuery = Object.values(queries).some((query) => query.isError);
  const retryFailedQueries = () => {
    for (const query of Object.values(queries)) {
      if (query.isError) {
        void query.refetch();
      }
    }
  };
  const stateTone = pageStateTone(view.dataState, view.stateLabel);
  const performanceState = kind === "performance" ? view.dataState : undefined;
  const performanceBlockingState =
    performanceState === "loading" ||
    performanceState === "empty" ||
    performanceState === "error"
      ? performanceState
      : undefined;
  const performanceAdvisoryState =
    performanceState === "partial" || performanceState === "stale"
      ? performanceState
      : undefined;

  return (
    <section
      className={`${styles.moduleHome} theme-dh-api`}
      data-moss-theme-scope="module-workbench-home"
      data-state={view.dataState}
      data-testid="module-workbench-home"
    >
      {/* 工具栏 — 首页 dhTopbar 语言：左标题 + 一问副题与状态说明，右来源/状态胶囊 */}
      <header className={styles.topbar} data-testid="module-home-toolbar">
        <div className={styles.topbarLeft}>
          <h1 className={styles.pageTitle}>{view.title}</h1>
          <div className={styles.topbarMeta}>
            <span title={view.question}>{view.question}</span>
            <span title={view.stateDetail}>{view.stateDetail}</span>
            {/* 口径边界声明是业务文案（§6），保持可见，不收进 tooltip。 */}
            <span title={view.summary}>{view.summary}</span>
          </div>
        </div>
        <div className={styles.topbarRight}>
          <span className={styles.pill} title={view.sourceScope}>
            来源 {view.sourceScope}
          </span>
          <span className={statePillClassName(stateTone)} title={view.stateDetail}>
            <i aria-hidden="true" />
            {view.stateLabel}
          </span>
          {hasFailedQuery ? (
            <button
              type="button"
              className={styles.pill}
              // 复用状态胶囊样式的一次性按钮化重置（非重复布局块）
              style={{ background: "transparent", cursor: "pointer" }}
              onClick={retryFailedQueries}
              data-testid="module-home-retry"
            >
              重试
            </button>
          ) : null}
        </div>
      </header>

      <div className={styles.layout}>
        {/* 一个 stack 容器 = 一个独立编号域：01 主结论区与 02+ 明细区块的序号
            由 SectionHead 的 CSS counter 按 DOM 顺序生成，页面不再手写 index。 */}
        <main className={`${styles.main} ${SECTION_HEAD_STACK_CLASSNAME}`}>
          {performanceBlockingState ? (
            <StateSurface
              status={performanceBlockingState}
              message={performanceStateMessage(performanceBlockingState)}
              reason={performanceBlockingState === "loading" ? undefined : view.stateDetail}
              minHeight={performanceBlockingState === "loading" ? 224 : undefined}
              testId="module-home-primary-state"
              actions={
                performanceBlockingState === "empty" ? (
                  <Link className={styles.stateAction} to="/kpi">
                    前往绩效考核核验配置
                  </Link>
                ) : undefined
              }
            />
          ) : (
            <>
              {performanceAdvisoryState ? (
                <StateSurface
                  status={performanceAdvisoryState}
                  message={performanceStateMessage(performanceAdvisoryState)}
                  reason={view.stateDetail}
                  density="compact"
                  testId="module-home-primary-state"
                />
              ) : null}
          {/* KPI 单框横带（首页 kpiRail 语言：等高分格 + 发丝竖缝 + 等宽数字） */}
          <section className={styles.kpiStrip} data-testid="module-home-kpi-strip">
            {view.kpis.map((item) => (
              <article
                className={styles.kpi}
                data-compact-value={isCompactKpiValue(item.value) ? "true" : undefined}
                key={item.key}
              >
                <span className={styles.kpiLabel} title={item.label}>
                  {item.label}
                </span>
                <strong
                  className={`${styles.kpiValue} ${styles.num} ${toneClassName(item.tone)}`}
                  title={item.value}
                >
                  {item.value}
                </strong>
                {/* 端点/函数名等证据引用收 tooltip（§7），正文保持中文业务语言 */}
                <span className={styles.kpiDetail} title={item.detailTitle ?? item.detail}>
                  {item.detail}
                </span>
              </article>
            ))}
          </section>

          {/* 读链路状态条带（首页产品分类摘要条语言：单框分格 + 语义状态位） */}
          <section className={styles.statusStrip} data-testid="module-home-status-strip">
            {view.statuses.map((item) => (
              <article className={styles.statusItem} key={item.key}>
                <div className={styles.statusTop}>
                  <span className={styles.statusLabel}>{item.label}</span>
                  <strong
                    className={`${styles.statusValue} ${styles.num} ${toneClassName(item.tone)}`}
                  >
                    {item.value}
                  </strong>
                </div>
                <span className={styles.statusDetail} title={item.detail}>
                  {item.detail}
                </span>
              </article>
            ))}
          </section>

          {/* 01 主结论区 */}
          <section className={styles.card} data-testid="module-home-briefing">
            <SectionHead title="主结论区" />
            <div className={styles.briefGrid}>
              {view.briefings.map((item) => (
                <article className={styles.brief} key={item.title}>
                  <span className={styles.briefTitle}>{item.title}</span>
                  <strong className={`${styles.briefConclusion} ${toneClassName(item.tone)}`}>
                    {item.conclusion}
                  </strong>
                  <span className={styles.briefEvidence}>{item.evidence}</span>
                </article>
              ))}
            </div>
          </section>

          {/* 02+ 明细区块（performance：KPI 指标明细 / 业务种类损益；
              governance：数据源状态 / Cube 维度与度量 / 健康检查明细） */}
          {(view.detailPanels ?? []).map((panel) => (
            <section
              className={styles.card}
              data-testid={detailPanelTestId(panel.key)}
              key={panel.key}
            >
              <SectionHead
                title={panel.title}
                state={panelSectionState(panel)}
                meta={panelSectionMeta(panel)}
              />
              <DetailPanelBody panel={panel} />
            </section>
          ))}
            </>
          )}
        </main>

        <aside className={styles.rail}>
          <section className={styles.railCard} data-testid="module-home-drilldowns">
            <div className={styles.railCardHeader}>
              <span>下钻入口</span>
            </div>
            <div className={styles.railCardBody}>
              <p className={styles.railLead}>
                首页只做摘要和状态聚合，明细解释进入对应页面继续看。
              </p>
              <div className={styles.drillList}>
                {config.drilldowns.map((item) => (
                  <Link className={styles.drill} to={item.path} key={item.key}>
                    <span className={styles.drillHead}>
                      <strong className={styles.drillTitle}>{item.label}</strong>
                      <span className={styles.drillBadge}>{item.statusLabel}</span>
                    </span>
                    <span className={styles.drillDesc}>{item.description}</span>
                  </Link>
                ))}
              </div>
            </div>
          </section>

          <section className={styles.railCard} data-testid="module-home-data-note">
            <div className={styles.railCardHeader}>
              <span>{view.dataNote.title}</span>
            </div>
            <div className={styles.railCardBody}>
              <ul className={styles.dataNote}>
                {view.dataNote.lines.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          </section>
        </aside>
      </div>
    </section>
  );
}
