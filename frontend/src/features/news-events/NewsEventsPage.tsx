import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../api/client";
import { PageAsyncSection } from "../../components/page/PageAsyncSection";
import {
  getChoiceNewsTopicPresentation,
  listChoiceNewsTopicFilterOptions,
} from "../agent/lib/choiceNewsTopicDictionary";
import { KpiCard } from "../../components/KpiCard";
import type { ChoiceNewsComparePayload, ResultMeta } from "../../api/contracts";
import { EM_DASH } from "../../utils/format";

import "./NewsEventsPage.css";

const NEWS_EVENTS_PAGE_SIZE = 50;

/** 摘要列优先展示解析出的 headline / summary；未解析原文收进 title。 */
function summarizeNewsPayload(event: {
  payload_text: string | null;
  payload_json: string | null;
  error_code: number;
  error_msg: string;
}): { text: string; raw?: string } {
  if (event.payload_text?.trim()) {
    return { text: event.payload_text };
  }
  if (event.payload_json?.trim()) {
    const raw = event.payload_json.trim();
    try {
      const parsed = JSON.parse(raw) as Record<string, unknown>;
      const headline =
        typeof parsed.headline === "string" ? parsed.headline.trim() : "";
      const summary =
        typeof parsed.summary === "string" ? parsed.summary.trim() : "";
      const text = headline || summary;
      if (text) {
        return {
          text: headline && summary ? `${headline}：${summary}` : text,
          raw,
        };
      }
    } catch {
      // 无法解析时原样透出，不猜测业务含义。
    }
    return { text: raw };
  }
  if (event.error_code !== 0) {
    return { text: event.error_msg || "供应商回调返回了空错误信封。" };
  }
  return { text: "空回调信封。" };
}

/** 接收时间列展示 MM-DD HH:mm，ISO 原值收进 title。 */
const RECEIVED_AT_PATTERN = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/;

function formatReceivedAt(value: string): { display: string; raw?: string } {
  const match = RECEIVED_AT_PATTERN.exec(value);
  if (!match) {
    return { display: value };
  }
  return {
    display: `${match[2]}-${match[3]} ${match[4]}:${match[5]}`,
    raw: value,
  };
}

/** 目录外的常见来源 token → 中文展示；原始 token 收进 title。 */
const NEWS_TOPIC_TOKEN_LABELS: Record<string, string> = {
  __callback__: "供应商回调",
  "tushare.npr": "政策要闻（Tushare）",
  "tushare.news": "市场快讯（Tushare）",
  "tushare.cctv": "新闻联播（Tushare）",
  "tushare.major": "长篇报道（Tushare）",
  "tushare.research": "研究报告（Tushare）",
};

/**
 * Tushare 摄取任务的 topic 形态（tushare_news_ingest.py）：
 * `tushare.news.{src}` / `tushare.cctv_news.{date}` / `tushare.major_news`
 * / `tushare.research_report.{range}`；来源子代号保留为证据引用。
 */
function mapTushareTopicToken(code: string): string | null {
  if (code.startsWith("tushare.news.")) {
    const src = code.slice("tushare.news.".length);
    return src ? `市场快讯（Tushare·${src}）` : "市场快讯（Tushare）";
  }
  if (code.startsWith("tushare.cctv_news")) {
    return "新闻联播（Tushare）";
  }
  if (code.startsWith("tushare.major_news")) {
    return "长篇报道（Tushare）";
  }
  if (code.startsWith("tushare.research_report")) {
    return "研究报告（Tushare）";
  }
  return null;
}

function presentTopicCode(event: {
  group_id: string;
  topic_code: string;
}): { display: string; raw: string } {
  const override =
    NEWS_TOPIC_TOKEN_LABELS[event.topic_code] ??
    mapTushareTopicToken(event.topic_code);
  if (override) {
    return { display: override, raw: event.topic_code };
  }
  const presentation = getChoiceNewsTopicPresentation({
    groupId: event.group_id,
    topicCode: event.topic_code,
  });
  return presentation.topicName
    ? { display: presentation.topicName, raw: event.topic_code }
    : { display: event.topic_code, raw: event.topic_code };
}

function clampOffset(offset: number) {
  return Math.max(0, offset);
}

function pagerDisabled(offset: number, pageSize: number, totalRows: number) {
  return offset + pageSize >= totalRows;
}

function currentPage(offset: number, pageSize: number) {
  return Math.floor(offset / pageSize) + 1;
}

function totalPages(totalRows: number, pageSize: number) {
  return Math.max(1, Math.ceil(totalRows / pageSize));
}

function formatMetaList(values?: string[]) {
  const joined = values?.filter(Boolean).join(" / ");
  return joined || EM_DASH;
}

function resultMetaBasisLabel(value: ResultMeta["basis"]): string {
  if (value === "formal") return "正式口径";
  if (value === "scenario") return "情景口径";
  if (value === "analytical") return "分析口径";
  if (value === "mock") return "演示口径";
  return value;
}

function formatResultMetaLine(meta: ResultMeta): string {
  return [
    `口径=${resultMetaBasisLabel(meta.basis)}`,
    `正式可用=${meta.formal_use_allowed ? "是" : "否"}`,
    `质量=${meta.quality_flag || EM_DASH}`,
    `降级=${meta.fallback_mode || EM_DASH}`,
    `请求日=${meta.requested_report_date || EM_DASH}`,
    `实际日=${meta.resolved_report_date || EM_DASH}`,
    `结果类型=${meta.result_kind || EM_DASH}`,
    `来源面=${meta.source_surface ?? EM_DASH}`,
    `来源版本=${meta.source_version || EM_DASH}`,
    `规则版本=${meta.rule_version || EM_DASH}`,
    `缓存版本=${meta.cache_version || EM_DASH}`,
    `数据表=${formatMetaList(meta.tables_used)}`,
    `生成时间=${meta.generated_at || EM_DASH}`,
  ].join(" · ");
}

/** fallback 非 none 或 quality 非 ok 视为降级，首屏需要琥珀提示。 */
function isMetaDegraded(meta: ResultMeta | undefined): meta is ResultMeta {
  return meta != null && (meta.fallback_mode !== "none" || meta.quality_flag !== "ok");
}

function NewsEventsBoundary({ meta }: { meta: ResultMeta }) {
  return (
    <section
      data-testid="news-events-analytical-boundary"
      className="news-events-page__analytical-boundary"
    >
      <strong className="news-events-page__boundary-code">PAGE-CONTRACT-PENDING:/news-events</strong>
      <span>
        GAP-NEWS-EVENTS-PAGE 为分析读面临时例外事件上下文；标题、专题计数、事件计数、筛选与错误行均非业务事实、非交易指令，亦不构成来源数据质量审批。
      </span>
      <details
        data-testid="news-events-result-meta"
        className="news-events-page__meta-fold"
        title={formatResultMetaLine(meta)}
      >
        <summary className="news-events-page__meta-summary">
          结果元信息（口径 / 质量 / 版本，共 13 项）
        </summary>
        <div className="news-events-page__meta-grid">
          <span>口径={resultMetaBasisLabel(meta.basis)}</span>
          <span>正式可用={meta.formal_use_allowed ? "是" : "否"}</span>
          <span>质量={meta.quality_flag || EM_DASH}</span>
          <span>降级={meta.fallback_mode || EM_DASH}</span>
          <span>请求日={meta.requested_report_date || EM_DASH}</span>
          <span>实际日={meta.resolved_report_date || EM_DASH}</span>
          <span>结果类型={meta.result_kind || EM_DASH}</span>
          <span>来源面={meta.source_surface ?? EM_DASH}</span>
          <span>来源版本={meta.source_version || EM_DASH}</span>
          <span>规则版本={meta.rule_version || EM_DASH}</span>
          <span>缓存版本={meta.cache_version || EM_DASH}</span>
          <span>数据表={formatMetaList(meta.tables_used)}</span>
          <span>生成时间={meta.generated_at || EM_DASH}</span>
        </div>
      </details>
    </section>
  );
}

function CompareBucket(props: {
  title: string;
  rows: ChoiceNewsComparePayload["same_direction"];
  emptyText: string;
}) {
  return (
    <div className="news-events-page__compare-card">
      <strong className="news-events-page__compare-card-title">{props.title}</strong>
      {props.rows.length > 0 ? (
        <ul className="news-events-page__compare-list">
          {props.rows.map((row, index) => (
            <li key={`${props.title}-${row.event_family ?? row.conflict_type ?? index}`}>
              <span>{row.event_family ?? row.conflict_type ?? "待复核"}</span>
              <span> · </span>
              <span>{row.summary ?? row.review_reason ?? `${row.source_event_ids?.length ?? 0} 条事件`}</span>
            </li>
          ))}
        </ul>
      ) : (
        <span className="news-events-page__compare-empty">{props.emptyText}</span>
      )}
    </div>
  );
}

function NewsEventsCompare({ compare }: { compare?: ChoiceNewsComparePayload }) {
  if (!compare) {
    return null;
  }
  return (
    <section data-testid="news-events-compare" className="news-events-page__compare-section">
      <div className="news-events-page__section-header-row">
        <span className="news-events-page__section-header-title">跨篇对比</span>
        <span
          className="news-events-page__section-header-meta"
          title={`规则版本 ${compare.rule_version}`}
        >
          规则版本 {compare.rule_version}
        </span>
      </div>
      <div className="news-events-page__compare-grid">
        <CompareBucket title="同向线索" rows={compare.same_direction} emptyText="暂无同向线索" />
        <CompareBucket title="冲突线索" rows={compare.conflicting} emptyText="暂无冲突线索" />
        <CompareBucket title="待复核" rows={compare.review_needed} emptyText="暂无待复核项" />
      </div>
      <div className="news-events-page__compare-card">
        <strong className="news-events-page__compare-card-title">候选情景建议</strong>
        {compare.candidate_scenarios.length > 0 ? (
          <ul className="news-events-page__compare-list">
            {compare.candidate_scenarios.map((item) => (
              <li
                key={item.mapping_rule_id}
                title={`情景模板 ${item.scenario_template_id} · 需人工复核：${item.human_review_required ? "是" : "否"}`}
              >
                <span>
                  {item.event_family} · {item.scenario_template_id}
                </span>
                <br />
                <span>需人工复核：{item.human_review_required ? "是" : "否"}</span>
              </li>
            ))}
          </ul>
        ) : (
          <span className="news-events-page__compare-empty">暂无候选情景建议</span>
        )}
      </div>
    </section>
  );
}

function SectionLead(props: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div className="news-events-page__section-lead">
      <span className="news-events-page__section-eyebrow">{props.eyebrow}</span>
      <h2 className="news-events-page__section-title">{props.title}</h2>
      <p className="news-events-page__section-description">{props.description}</p>
    </div>
  );
}

export default function NewsEventsPage() {
  const client = useApiClient();
  const topicOptions = useMemo(() => listChoiceNewsTopicFilterOptions(), []);
  const [topicCode, setTopicCode] = useState("");
  const [errorOnly, setErrorOnly] = useState(false);
  const [offset, setOffset] = useState(0);

  const eventsQuery = useQuery({
    queryKey: [
      "news-events",
      "choice-events",
      client.mode,
      topicCode,
      errorOnly,
      offset,
    ],
    queryFn: () =>
      client.getChoiceNewsEvents({
        limit: NEWS_EVENTS_PAGE_SIZE,
        offset,
        topicCode: topicCode.trim() || undefined,
        errorOnly,
      }),
    retry: false,
  });

  const events = useMemo(
    () => eventsQuery.data?.result.events ?? [],
    [eventsQuery.data?.result.events],
  );
  const totalRows = eventsQuery.data?.result.total_rows ?? 0;
  const resultMeta = eventsQuery.data?.result_meta;
  const isEmpty =
    !eventsQuery.isLoading &&
    !eventsQuery.isError &&
    events.length === 0;
  const errorRowsOnPage = useMemo(
    () => events.filter((event) => event.error_code !== 0).length,
    [events],
  );
  const activeTopicLabel = topicCode || "全部专题";
  const pageLabel = `${currentPage(offset, NEWS_EVENTS_PAGE_SIZE)} / ${totalPages(totalRows, NEWS_EVENTS_PAGE_SIZE)}`;

  // KPI 数值由查询状态驱动：loading/error 一律 EM_DASH 并保留状态注记，
  // 仅在成功且服务端明确返回数值时才显示 0，禁止请求失败冒充“0 行”。
  const kpiReady = !eventsQuery.isLoading && !eventsQuery.isError && eventsQuery.data != null;
  const kpiStateDetail =
    eventsQuery.isLoading ? "查询进行中，数值待返回"
    : eventsQuery.isError ? "查询失败，数值不可用"
    : null;
  const totalRowsDisplay = kpiReady ? String(totalRows) : EM_DASH;
  const pageDisplay = kpiReady ? pageLabel : EM_DASH;
  const errorRowsDisplay = kpiReady ? String(errorRowsOnPage) : EM_DASH;
  const metaDegraded = isMetaDegraded(resultMeta) ? resultMeta : null;

  return (
    <section className="news-events-page" data-moss-theme-scope="news-events">
      <div className="news-events-page__header">
        <div>
          <h1 data-testid="news-events-page-title" className="news-events-page__title">
            新闻事件
          </h1>
          <p className="news-events-page__intro">
            查看 Choice 新闻回调事件流水，可按专题与错误筛选；数据来自服务端最新事件接口。本页为分析读面（临时例外路由，非正式指标主链）。
          </p>
        </div>
        <span className="news-events-page__mode-badge" data-mode={client.mode}>
          {client.mode === "real" ? "真实只读链路" : "本地演示数据"}
        </span>
      </div>

      {metaDegraded ? (
        <p
          data-testid="news-events-quality-hint"
          role="status"
          className="news-events-page__quality-hint"
        >
          数据状态提示：质量={metaDegraded.quality_flag || EM_DASH}，降级=
          {metaDegraded.fallback_mode || EM_DASH}，请求日=
          {metaDegraded.requested_report_date || EM_DASH}，实际日=
          {metaDegraded.resolved_report_date || EM_DASH}，引用本页计数前请先核对数据状态。
        </p>
      ) : null}

      <SectionLead
        eyebrow="总览"
        title="事件概览"
        description="先看事件总数、当前页和错误行，再进入筛选与明细列表，保持新闻事件页的阅读顺序和其他标准壳层一致。"
      />
      <div className="news-events-page__summary-grid">
        <div data-testid="news-events-total-count">
          <KpiCard
            title="事件总数"
            value={totalRowsDisplay}
            detail={kpiStateDetail ?? "当前查询返回的总行数"}
            valueVariant="text"
          />
        </div>
        <div data-testid="news-events-current-page-kpi">
          <KpiCard
            title="当前页"
            value={pageDisplay}
            detail={kpiStateDetail ?? "按固定分页窗口展示"}
            valueVariant="text"
          />
        </div>
        <div data-testid="news-events-error-count">
          <KpiCard
            title="错误行数"
            value={errorRowsDisplay}
            detail={kpiStateDetail ?? "当前页含非零错误码的行数"}
            valueVariant="text"
          />
        </div>
        <div data-testid="news-events-active-topic">
          <KpiCard title="当前专题" value={activeTopicLabel} detail="切换专题后分页会自动归零" valueVariant="text" />
        </div>
      </div>
      {resultMeta ? <NewsEventsBoundary meta={resultMeta} /> : null}
      <NewsEventsCompare compare={eventsQuery.data?.result.compare} />

      {/* 分区头 + 筛选控件右置 + 表格拍平为单层 panel；卡头不再与页 h1 重名。 */}
      <PageAsyncSection
        title="筛选与事件列表"
        extra={
          <div className="news-events-page__filter-inline">
            <label className="news-events-page__filter-label">
              <span title="topic_code">专题</span>
              <select
                aria-label="news-events-topic-code"
                value={topicCode}
                onChange={(e) => {
                  setTopicCode(e.target.value);
                  setOffset(0);
                }}
              >
                <option value="">全部</option>
                {topicOptions.map((opt) => (
                  <option key={opt.topicCode} value={opt.topicCode}>
                    {opt.label} ({opt.topicCode})
                  </option>
                ))}
              </select>
            </label>
            <label className="news-events-page__filter-checkbox-label">
              <input
                type="checkbox"
                aria-label="news-events-error-only"
                checked={errorOnly}
                onChange={(e) => {
                  setErrorOnly(e.target.checked);
                  setOffset(0);
                }}
              />
              <span title="error_only">仅错误</span>
            </label>
          </div>
        }
        fillHeight={false}
        isLoading={eventsQuery.isLoading}
        isError={eventsQuery.isError}
        isEmpty={isEmpty}
        onRetry={() => void eventsQuery.refetch()}
      >
          <div className="news-events-page__table-scroll">
            <table data-testid="news-events-table" className="news-events-page__table">
              <thead>
                <tr className="news-events-page__table-head-row">
                  <th scope="col" className="news-events-page__table-head-cell" title="received_at">
                    接收时间
                  </th>
                  <th scope="col" className="news-events-page__table-head-cell" title="topic_code">
                    专题代码
                  </th>
                  <th scope="col" className="news-events-page__table-head-cell" title="group_id">
                    分组 ID
                  </th>
                  <th
                    scope="col"
                    className="news-events-page__table-head-cell news-events-page__table-head-cell--wrap"
                  >
                    内容摘要
                  </th>
                  <th scope="col" className="news-events-page__table-head-cell" title="error_code">
                    错误码
                  </th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => {
                  const isErrorRow = event.error_code !== 0;
                  const receivedAt = formatReceivedAt(event.received_at);
                  const topic = presentTopicCode(event);
                  const summary = summarizeNewsPayload(event);
                  return (
                    <tr
                      key={event.event_key}
                      className={
                        isErrorRow
                          ? "news-events-page__table-row news-events-page__table-row--error"
                          : "news-events-page__table-row"
                      }
                    >
                      <td
                        className="news-events-page__table-cell news-events-page__table-cell--nowrap"
                        title={receivedAt.raw}
                      >
                        {receivedAt.display}
                      </td>
                      <td
                        className="news-events-page__table-cell news-events-page__table-cell--nowrap"
                        title={
                          topic.display !== topic.raw ? topic.raw : undefined
                        }
                      >
                        {topic.display}
                      </td>
                      <td className="news-events-page__table-cell news-events-page__table-cell--nowrap">
                        {event.group_id}
                      </td>
                      <td
                        className="news-events-page__table-cell news-events-page__table-cell--summary"
                        title={summary.raw}
                      >
                        {summary.text}
                      </td>
                      <td className="news-events-page__table-cell news-events-page__table-cell--nowrap news-events-page__error-code-cell">
                        {event.error_code}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="news-events-page__pager-row">
            {totalPages(totalRows, NEWS_EVENTS_PAGE_SIZE) > 1 ? (
              <>
                <button
                  type="button"
                  data-testid="news-events-prev"
                  disabled={offset === 0}
                  onClick={() =>
                    setOffset((current) =>
                      clampOffset(current - NEWS_EVENTS_PAGE_SIZE),
                    )
                  }
                >
                  上一页
                </button>
                <button
                  type="button"
                  data-testid="news-events-next"
                  disabled={pagerDisabled(
                    offset,
                    NEWS_EVENTS_PAGE_SIZE,
                    totalRows,
                  )}
                  onClick={() =>
                    setOffset((current) => current + NEWS_EVENTS_PAGE_SIZE)
                  }
                >
                  下一页
                </button>
              </>
            ) : null}
            <span data-testid="news-events-page">
              {currentPage(offset, NEWS_EVENTS_PAGE_SIZE)} /{" "}
              {totalPages(totalRows, NEWS_EVENTS_PAGE_SIZE)}
            </span>
            <span data-testid="news-events-total">事件数 {totalRows}</span>
          </div>
      </PageAsyncSection>
    </section>
  );
}
