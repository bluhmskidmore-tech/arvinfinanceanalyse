import type { BalanceMovementReadState } from "../hooks/useBalanceMovementAnalysis";
import type { BalanceMovementDatesPayload, ResultMeta } from "../../../api/contracts";
import { SectionHead } from "../../../components/layout";
import { EM_DASH } from "../../../utils/format";
import type { ReactNode } from "react";
import { SupplementaryEvidenceDetails } from "./SupplementaryEvidenceDetails";
import { formatMetaList } from "../lib/balanceMovementPresentation";

type BalanceMovementFreshnessStatus = NonNullable<BalanceMovementDatesPayload["freshness_status"]>;

function freshnessStatusLabel(status: BalanceMovementFreshnessStatus | undefined, readStatus: BalanceMovementReadState = "confirmed") {
  if (readStatus === "cached_after_error") return "读取或刷新失败 · 新鲜度待确认";
  if (readStatus === "refreshing") return "新鲜度确认中";
  switch (status) {
    case "fresh":
      return "数据已同步";
    case "read_model_lagging":
      return "读模型落后上游";
    case "read_model_empty":
      return "读模型未生成";
    case "upstream_empty":
      return "上游暂无控制账";
    default:
      return "新鲜度待确认";
  }
}

function freshnessStatusDetail(status: BalanceMovementFreshnessStatus | undefined) {
  switch (status) {
    case "fresh":
      return "上游控制账与页面读模型日期一致。";
    case "read_model_lagging":
      return "上游已有更晚月份，当前页面仍停留在读模型已有月份。";
    case "read_model_empty":
      return "上游已有控制账数据，但页面读模型尚未生成可选日期。";
    case "upstream_empty":
      return "页面有读模型日期，但未发现同口径上游控制账。";
    default:
      return "当前接口未返回上游与读模型的日期对齐信息。";
  }
}

function freshnessStatusTone(status: BalanceMovementFreshnessStatus | undefined) {
  if (status === "fresh") {
    return "ok";
  }
  if (status === "read_model_lagging" || status === "read_model_empty") {
    return "warn";
  }
  return "info";
}

export function FreshnessStrip({
  dates,
  readStatus,
  selectedDate,
  reconciliationLabel,
  currencyBasis,
}: {
  dates: BalanceMovementDatesPayload;
  readStatus: BalanceMovementReadState;
  selectedDate: string;
  reconciliationLabel: string;
  currencyBasis: string;
}) {
  const status = dates.freshness_status;
  const latestReadModelDate = dates.latest_read_model_report_date ?? dates.report_dates[0] ?? null;
  const latestUpstreamDate = dates.latest_upstream_control_report_date ?? null;
  const tone = readStatus === "confirmed" ? freshnessStatusTone(status) : "warn";
  const statusDetail = readStatus === "cached_after_error"
    ? "本次读取或刷新失败，保留上次读取的日期与来源；尚未确认最新数据。"
    : readStatus === "refreshing" ? "读取或刷新尚未完成；尚未确认最新数据。" : freshnessStatusDetail(status);
  return (
    <aside
      className={`balance-movement-data-trust balance-movement-data-trust--${tone} balance-movement-freshness-strip balance-movement-freshness-strip--${tone}`}
      data-testid="balance-movement-analysis-freshness"
      aria-label="余额变动分析数据新鲜度"
    >
      <header className="balance-movement-data-trust__header">
        <span>数据可信度</span>
        <strong title={statusDetail}>{freshnessStatusLabel(status, readStatus)}</strong>
      </header>
      <dl className="balance-movement-data-trust__facts">
        <div>
          <dt>读模型</dt>
          <dd>{selectedDate || latestReadModelDate || "未生成"}</dd>
        </div>
        <div>
          <dt>上游控制</dt>
          <dd>{latestUpstreamDate ?? "未发现"}</dd>
        </div>
        <div>
          <dt>对账</dt>
          <dd>{reconciliationLabel === "三桶一致" ? "3 / 3 一致" : reconciliationLabel}</dd>
        </div>
        <div>
          <dt>币种口径</dt>
          <dd>{currencyBasis}</dd>
        </div>
      </dl>
    </aside>
  );
}

export function EvidenceStrip({
  meta,
  reportDate,
  currencyBasis,
}: {
  meta: ResultMeta;
  reportDate: string;
  currencyBasis: string;
}) {
  return (
    <section
      className="balance-movement-provenance"
      data-testid="balance-movement-analysis-evidence-strip"
      aria-label="余额变动分析证据与出处"
    >
      <SectionHead
        title="证据与数据出处"
        numbered={{ counter: "bm-section", increment: true }}
        contentGap="flush"
        testId="balance-movement-analysis-evidence-heading"
      />
      <div className="balance-movement-provenance__grid">
        <article>
          <span>新鲜度</span>
          <strong>{reportDate || meta.resolved_report_date || EM_DASH}</strong>
          <p>当前视图严格锚定读模型报告日，不在浏览器端补算其他月份。</p>
        </article>
        <article>
          <span>血缘</span>
          <strong>{meta.source_version || EM_DASH}</strong>
          <p>{formatMetaList(meta.tables_used)}；规则 {meta.rule_version || EM_DASH}；质量 {meta.quality_flag}</p>
        </article>
        <article>
          <span>控制口径</span>
          <strong>{currencyBasis} · 141 / 142 / 143 / 1440101</strong>
          <p>总账控制口径；排除 144020 股权 OCI，ZQTZ 仅用于诊断核对。</p>
        </article>
      </div>
      <div className="balance-movement-provenance__export-note">
        <span>导出边界</span>
        <p>导出仅包含当前报告日与当前页面证据快照。</p>
        <strong>{meta.trace_id || EM_DASH} · {meta.evidence_rows ?? 0} 行</strong>
      </div>
    </section>
  );
}

export function DataStatesGovernancePanel({
  isLoading,
  hasReportDates,
  hasRows,
  freshnessStatus,
  requestedReportDate,
  resolvedReportDate,
  readStatus,
  hasError,
  datesReadFailed,
  datesReadConfirmed,
  refreshError,
  resultMeta,
  governanceMeta,
  supplementary,
}: {
  isLoading: boolean;
  hasReportDates: boolean;
  hasRows: boolean;
  freshnessStatus: BalanceMovementDatesPayload["freshness_status"] | undefined;
  requestedReportDate: string;
  resolvedReportDate: string;
  readStatus: BalanceMovementReadState;
  hasError: boolean;
  datesReadFailed: boolean;
  datesReadConfirmed: boolean;
  refreshError: string | null;
  resultMeta: ResultMeta | null;
  governanceMeta: { reportDate: string; ruleVersions: string[]; sourceVersions: string[] };
  supplementary?: () => ReactNode;
}) {
  const hasFallbackDate = Boolean(
    resultMeta?.fallback_date ||
      (requestedReportDate && resolvedReportDate && requestedReportDate !== resolvedReportDate),
  );
  const detailReadConfirmed = datesReadConfirmed && !hasError && !isLoading && resultMeta !== null;
  const freshnessConfirmed = readStatus === "confirmed" && datesReadConfirmed && freshnessStatus !== undefined;
  const freshnessUnknownNote = readStatus === "cached_after_error" ? "本次读取或刷新失败，无法确认读模型新鲜度" : "尚未完成本次读取，无法确认读模型新鲜度";
  const states = [
    {
      label: "加载中",
      value: isLoading ? "请求中" : hasError ? "读取失败" : "已完成",
      note: isLoading ? "筛选与操作保持可理解" : "不把旧数据伪装成新结果",
    },
    {
      label: "无报告日",
      value: datesReadConfirmed ? hasReportDates ? "否" : "是" : "未知",
      note: datesReadFailed
        ? "本次读取失败，无法确认可选报告日"
        : !datesReadConfirmed ? "正在读取，尚无法确认可选报告日"
          : hasReportDates ? "已返回可选报告日" : "提示先物化读模型",
    },
    {
      label: "无明细行",
      value: detailReadConfirmed ? hasRows ? "否" : "是" : "未知",
      note: !detailReadConfirmed
        ? hasError ? "本次读取失败，无法确认明细行状态" : "尚未完成本次读取，无法确认明细行状态"
        : hasRows ? "AC / OCI / TPL 行已返回" : "正文显式展示空态",
    },
    {
      label: "读模型滞后",
      value: freshnessConfirmed ? freshnessStatus === "read_model_lagging" ? "是" : "否" : "未知",
      note: freshnessConfirmed ? freshnessStatusDetail(freshnessStatus) : freshnessUnknownNote,
    },
    {
      label: "回退日期",
      value: !detailReadConfirmed ? "未知" : hasFallbackDate ? resolvedReportDate || resultMeta?.fallback_date || "是" : "无",
      note: !detailReadConfirmed
        ? hasError ? "本次读取失败，无法确认日期回退" : "尚未完成本次读取，无法确认日期回退"
        : hasFallbackDate ? "requested 与 resolved 分开呈现" : "当前未发生日期回退",
    },
    {
      label: "加载 / 刷新失败",
      value: hasError || refreshError ? "是" : "否",
      note: refreshError ?? (hasError ? "显示错误，不回填演示数据" : "当前没有加载或刷新错误"),
    },
  ];
  const sourceVersion =
    resultMeta?.source_version ||
    (governanceMeta.sourceVersions.length ? governanceMeta.sourceVersions.join("、") : EM_DASH);
  const ruleVersion =
    resultMeta?.rule_version ||
    (governanceMeta.ruleVersions.length ? governanceMeta.ruleVersions.join("、") : EM_DASH);
  const fields = [
    ["quality_flag", resultMeta?.quality_flag ?? EM_DASH],
    ["fallback_mode", resultMeta?.fallback_mode ?? EM_DASH],
    ["generated_at", resultMeta?.generated_at ?? EM_DASH],
    ["trace_id", resultMeta?.trace_id ?? EM_DASH],
    ["tables_used", formatMetaList(resultMeta?.tables_used)],
    ["evidence_rows", resultMeta?.evidence_rows ?? EM_DASH],
    ["source_version", sourceVersion],
    ["rule_version", ruleVersion],
  ];
  const rules = [
    ["日期语义", "requested_report_date 与 resolved_report_date 分开呈现"],
    ["单位语义", "后端 yuan；页面仅换算为亿元，不重算正式指标"],
    ["空值语义", "null / undefined 保持缺失；0 仅表示正式零值"],
    ["回退语义", "fallback / stale 不得隐藏在调试面板"],
    ["CSV 边界", "基于当前响应本地生成，不调用独立导出 API"],
  ];

  return (
    <section
      className="balance-movement-data-states"
      data-testid="balance-movement-analysis-data-states"
    >
      <header className="balance-movement-figma-header balance-movement-sec-no">
        <div>
          <h2>数据状态、回退语义与证据闭环</h2>
        </div>
        <dl className="balance-movement-data-states__meta">
          <div><dt>质量</dt><dd>{resultMeta?.quality_flag ?? EM_DASH}</dd></div>
          <div><dt>新鲜度</dt><dd>{freshnessStatusLabel(freshnessStatus, readStatus)}</dd></div>
          <div><dt>回退</dt><dd>{resultMeta?.fallback_mode ?? EM_DASH}</dd></div>
          <div><dt>策略</dt><dd>fail-closed</dd></div>
        </dl>
      </header>

      <div className="balance-movement-data-states__evidence">
        <header>
          <span>结果证据条 · 必显字段</span>
          <code>ApiEnvelope.result_meta + payload governance</code>
        </header>
        <div className="balance-movement-data-states__fields">
          {fields.map(([key, value]) => (
            <div key={String(key)}>
              <code>{key}</code>
              <span title={String(value)}>{value}</span>
            </div>
          ))}
        </div>
      </div>

      <details className="balance-movement-data-states__glossary">
        <summary>字段与状态语义说明</summary>
        <div className="balance-movement-data-states__states">
          {states.map((state) => (
            <article key={state.label} className="balance-movement-data-states__state">
              <strong>{state.label}</strong>
              <span>{state.value}</span>
              <small>{state.note}</small>
            </article>
          ))}
        </div>
        <div className="balance-movement-data-states__rules">
          {rules.map(([label, value]) => (
            <div key={label}>
              <strong>{label}</strong>
              <span>{value}</span>
            </div>
          ))}
        </div>
      </details>

      {supplementary ? (
        <SupplementaryEvidenceDetails renderContent={supplementary} />
      ) : (
        <div className="balance-movement-data-states__pass">
          <strong>契约通过条件</strong>
          <span>
            所有无数据、过期、回退日期、失败和口径待确认状态均在页面正文可见；不依赖调试工具。
          </span>
        </div>
      )}
    </section>
  );
}
