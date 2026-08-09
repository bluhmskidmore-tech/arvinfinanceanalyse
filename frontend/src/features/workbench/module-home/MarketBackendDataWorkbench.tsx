import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Pagination, Tabs } from "antd";

import { useApiClient } from "../../../api/client";
import type {
  ApiEnvelope,
  ChoiceNewsEvent,
  ChoiceNewsEventsPayload,
  ResultMeta,
} from "../../../api/contracts";
import type { ModuleHomeSourceQueries } from "./moduleHomeModel";
import styles from "./marketBackendDataWorkbench.module.css";

const NEWS_PAGE_SIZE = 50;
const LOCAL_PAGE_SIZE = 20;
const LONG_VALUE_THRESHOLD = 72;
const PRIMARY_META_FIELDS = [
  "trace_id",
  "basis",
  "result_kind",
  "formal_use_allowed",
  "amount_currency_basis",
  "source_version",
  "vendor_version",
  "quality_flag",
  "vendor_status",
  "fallback_mode",
  "as_of_date",
  "resolved_report_date",
  "fallback_date",
  "date_basis",
] as const;

type EnvelopeQuery<T = unknown> = {
  data?: ApiEnvelope<T>;
  isLoading?: boolean;
  isFetching?: boolean;
  isError?: boolean;
  error?: unknown;
};

type MarketBackendDataWorkbenchProps = {
  queries: ModuleHomeSourceQueries;
};

type PayloadNodeProps = {
  value: unknown;
  path: string;
  depth?: number;
};

type ScalarContext = {
  fieldKey?: string;
  path?: string;
};

const FIELD_LABELS: Record<string, string> = {
  default_data_sources: "默认数据源",
  as_of_date: "数据日期",
  conclusion: "市场结论",
  coverage: "覆盖情况",
  indicators: "指标明细",
  signal_cards: "信号卡",
  hason_strategy: "Hason 策略",
  a_share_risk: "A 股风险",
  capability_results: "能力计算结果",
  strategy_summaries: "策略摘要",
  shadow_portfolio_report: "影子组合报告",
  output_files: "输出文件",
  report_bundle: "报告包",
  source_checks: "数据源检查",
  capabilities: "能力目录",
  cffex_member_rank: "中金所会员持仓",
  choice_stock_refresh: "Choice 股票刷新状态",
  runtime_status: "运行状态",
  data_health: "数据健康",
  model_readiness: "模型就绪度",
  readiness_summary: "就绪度汇总",
  warnings: "告警",
  compare: "事件比较",
  events: "事件明细",
  trace_id: "追踪编号",
  basis: "数据口径",
  result_kind: "结果类型",
  formal_use_allowed: "允许正式使用",
  amount_currency_basis: "金额币种口径",
  source_version: "来源版本",
  vendor_version: "供应方版本",
  quality_flag: "质量状态",
  vendor_status: "供应方状态",
  fallback_mode: "回退模式",
  fallback_date: "回退数据日",
  resolved_report_date: "实际报告日",
  requested_report_date: "请求报告日",
  date_basis: "日期口径",
};

const QUALITY_STATE_LABELS: Record<ResultMeta["quality_flag"], string> = {
  ok: "质量正常",
  warning: "质量预警",
  error: "质量异常",
  stale: "数据过期",
  missing: "数据缺失",
};

const VENDOR_STATE_LABELS: Record<ResultMeta["vendor_status"], string> = {
  ok: "供应方正常",
  vendor_stale: "供应方数据过期",
  vendor_unavailable: "供应方不可用",
};

const BASIS_LABELS: Record<ResultMeta["basis"], string> = {
  formal: "正式口径",
  scenario: "情景口径",
  analytical: "分析口径",
  ledger: "账本口径",
  mock: "模拟口径",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function fieldLabel(key: string) {
  return FIELD_LABELS[key] ?? key;
}

function businessDiagnosticText(value: string) {
  const normalized = value.trim();
  if (/permission|not allowed|forbidden|denied|无权限|权限不足/i.test(normalized)) {
    return "部分数据源权限不足，相关数据暂不可用";
  }
  if (/timeout|timed out|超时/i.test(normalized)) {
    return "数据源响应超时，当前结果可能不完整";
  }
  if (/vendor|供应方/i.test(normalized)) {
    return "供应方数据异常，当前结果可能不完整";
  }
  if (/supplement|gate[_\s-]?supplement|补充数据/i.test(normalized)) {
    return "补充数据获取失败，当前结果可能不完整";
  }
  if (
    /macro_vendor\.choice_series|traceback|stack trace|exception|failed|error/i.test(
      normalized,
    )
  ) {
    return "技术告警已记录，当前结果可能不完整";
  }
  if (/[\u3400-\u9fff]/u.test(normalized)) return normalized;
  return "技术告警已记录，当前结果可能不完整";
}

function scalarContextKey({ fieldKey, path }: ScalarContext) {
  return [path, fieldKey].filter(Boolean).join(".").toLocaleLowerCase("en-US");
}

function safeStringValue(value: string, context: ScalarContext) {
  const key = scalarContextKey(context);
  if (
    /(?:^|\.)(?:warnings?|warning_code|error|error_message|exception)(?:\.|$)/i.test(
      key,
    )
  ) {
    return businessDiagnosticText(value);
  }
  if (
    /(?:^|\.)(?:source_surface|endpoint|api_path|route|cache_key)(?:\.|$)/i.test(
      key,
    ) ||
    /^(?:https?:\/\/(?:localhost|127\.0\.0\.1)|\/?api\/)/i.test(value.trim())
  ) {
    return "内部数据地址或标识已隐藏";
  }
  if (
    /(?:^|\.)(?:output_files?|report_bundle|file_path|output_path|path)(?:\.|$)/i.test(
      key,
    )
  ) {
    const basename = value
      .trim()
      .replace(/[?#].*$/, "")
      .split(/[\\/]/)
      .filter(Boolean)
      .at(-1);
    return basename || "文件记录已返回";
  }
  if (
    /^(?:[a-z]:[\\/]|\/(?:home|users|var|tmp|app|workspace|repo|backend|frontend)\/)/i.test(
      value.trim(),
    )
  ) {
    return "内部文件位置已隐藏";
  }
  return value;
}

function primitiveText(value: unknown, context: ScalarContext = {}) {
  if (value === undefined) return "字段未返回";
  if (value === null) return "无值";
  if (value === "") return "空文本";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "number")
    return Number.isFinite(value)
      ? value.toLocaleString("zh-CN")
      : "无有效数值";
  if (typeof value === "string") return safeStringValue(value, context);
  return String(value);
}

function searchableText(value: unknown) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (
    typeof value === "number" ||
    typeof value === "boolean" ||
    typeof value === "bigint"
  ) {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function valueSummary(value: unknown) {
  if (Array.isArray(value)) return `${value.length} 条`;
  if (isRecord(value)) return `${Object.keys(value).length} 个字段`;
  return primitiveText(value);
}

function BackendScalarValue({
  value,
  compact = false,
  fieldKey,
  path,
}: {
  value: unknown;
  compact?: boolean;
  fieldKey?: string;
  path?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const text = primitiveText(value, { fieldKey, path });
  const isLong = text.length > LONG_VALUE_THRESHOLD || text.includes("\n");

  if (!isLong) {
    return <span className={styles.scalarValue}>{text}</span>;
  }

  const copyValue = async () => {
    try {
      if (!navigator.clipboard?.writeText) return;
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <span
      className={`${styles.longValue} ${compact ? styles.longValueCompact : ""}`}
      data-expanded={expanded}
    >
      <code>{text}</code>
      <span className={styles.longValueActions}>
        <button
          type="button"
          aria-expanded={expanded}
          onClick={() => setExpanded((current) => !current)}
        >
          {expanded ? "收起" : "展开"}
        </button>
        <button type="button" onClick={() => void copyValue()}>
          {copied ? "已复制" : "复制"}
        </button>
      </span>
    </span>
  );
}

function errorText(error: unknown) {
  const message =
    error instanceof Error
      ? error.message
      : typeof error === "string"
        ? error
        : "";
  return message.trim()
    ? businessDiagnosticText(message)
    : "市场数据读取失败，请稍后重试";
}

function queryState(query: EnvelopeQuery | undefined) {
  if (!query) return { label: "未初始化", tone: "muted" };
  if (query.isError && !query.data) return { label: "读取失败", tone: "error" };
  if (!query.data)
    return { label: query.isLoading ? "读取中" : "等待数据", tone: "muted" };
  const { result_meta: meta } = query.data;
  const labels: string[] = [];
  let tone = "ok";

  if (meta.quality_flag !== "ok") {
    labels.push(QUALITY_STATE_LABELS[meta.quality_flag]);
    tone =
      meta.quality_flag === "warning" || meta.quality_flag === "stale"
        ? "watch"
        : "error";
  }
  if (meta.vendor_status !== "ok") {
    labels.push(VENDOR_STATE_LABELS[meta.vendor_status]);
    if (tone !== "error") {
      tone = meta.vendor_status === "vendor_unavailable" ? "error" : "watch";
    }
  }
  if (meta.fallback_mode !== "none") {
    labels.push("使用回退数据");
    if (tone === "ok") tone = "watch";
  }
  if (query.isError) {
    labels.push("刷新失败，保留已返回数据");
    tone = "error";
  }
  if (query.isFetching) {
    labels.push("后台刷新");
    if (tone === "ok") tone = "watch";
  }
  return {
    label: labels.length > 0 ? labels.join(" · ") : "已返回",
    tone,
  };
}

function ScalarGrid({
  entries,
  path,
}: {
  entries: Array<[string, unknown]>;
  path: string;
}) {
  if (entries.length === 0) return null;
  return (
    <dl className={styles.scalarGrid}>
      {entries.map(([key, value]) => (
        <div key={key}>
          <dt>{fieldLabel(key)}</dt>
          <dd>
            <BackendScalarValue
              fieldKey={key}
              path={`${path}.${key}`}
              value={value}
            />
          </dd>
        </div>
      ))}
    </dl>
  );
}

function ArrayNode({
  items,
  path,
  depth,
}: {
  items: unknown[];
  path: string;
  depth: number;
}) {
  const [page, setPage] = useState(1);
  const pageSize =
    items.length > LOCAL_PAGE_SIZE
      ? LOCAL_PAGE_SIZE
      : Math.max(items.length, 1);
  const pageCount = Math.max(Math.ceil(items.length / pageSize), 1);
  const safePage = Math.min(page, pageCount);
  const visibleItems = items.slice(
    (safePage - 1) * pageSize,
    safePage * pageSize,
  );

  if (items.length === 0)
    return <div className={styles.emptyValue}>空数组 · 0 条</div>;

  return (
    <div className={styles.arrayNode}>
      <div className={styles.arraySummary}>
        <span>{items.length} 条记录</span>
        {items.length > pageSize ? (
          <em>当前 {visibleItems.length} 条</em>
        ) : null}
      </div>
      <div className={styles.arrayItems}>
        {visibleItems.map((item, index) => {
          const absoluteIndex = (safePage - 1) * pageSize + index;
          return (
            <article
              className={styles.arrayItem}
              key={`${path}-${absoluteIndex}`}
            >
              <span className={styles.arrayIndex}>#{absoluteIndex + 1}</span>
              <MarketPayloadNode
                value={item}
                path={`${path}.${absoluteIndex}`}
                depth={depth + 1}
              />
            </article>
          );
        })}
      </div>
      {items.length > pageSize ? (
        <Pagination
          current={safePage}
          pageSize={pageSize}
          showSizeChanger={false}
          total={items.length}
          onChange={setPage}
        />
      ) : null}
    </div>
  );
}

/**
 * 递归展示后端对象的所有字段；长数组分页，但不丢弃任何可访问记录。
 */
export function MarketPayloadNode({
  value,
  path,
  depth = 0,
}: PayloadNodeProps) {
  if (Array.isArray(value)) {
    return <ArrayNode items={value} path={path} depth={depth} />;
  }
  if (!isRecord(value)) {
    return <BackendScalarValue path={path} value={value} />;
  }

  const entries = Object.entries(value);
  const scalarEntries = entries.filter(
    ([, item]) => !Array.isArray(item) && !isRecord(item),
  );
  const nestedEntries = entries.filter(
    ([, item]) => Array.isArray(item) || isRecord(item),
  );

  return (
    <div className={styles.objectNode}>
      <ScalarGrid entries={scalarEntries} path={path} />
      <div className={styles.nestedList}>
        {nestedEntries.map(([key, item]) => (
          <details
            className={styles.nestedBlock}
            key={`${path}.${key}`}
            open={depth === 0}
          >
            <summary>
              <span>{fieldLabel(key)}</span>
              <em>{valueSummary(item)}</em>
            </summary>
            <MarketPayloadNode
              value={item}
              path={`${path}.${key}`}
              depth={depth + 1}
            />
          </details>
        ))}
      </div>
    </div>
  );
}

function ResultMetaPanel({ meta }: { meta: ResultMeta }) {
  const entries = Object.entries(meta as unknown as Record<string, unknown>);
  const primaryEntries = PRIMARY_META_FIELDS.map((key) =>
    entries.find(([entryKey]) => entryKey === key),
  ).filter((entry): entry is [string, unknown] => Boolean(entry));
  const primaryKeys = new Set(primaryEntries.map(([key]) => key));
  const additionalEntries = entries.filter(([key]) => !primaryKeys.has(key));

  return (
    <details className={styles.metaPanel} open>
      <summary>
        <span>结果口径与来源</span>
        <em>
          {BASIS_LABELS[meta.basis]} · {meta.result_kind} ·{" "}
          {QUALITY_STATE_LABELS[meta.quality_flag]}
        </em>
      </summary>
      <div className={styles.metaBody}>
        <ScalarGrid entries={primaryEntries} path="result_meta.primary" />
        {additionalEntries.length > 0 ? (
          <details className={styles.additionalMeta}>
            <summary>
              <span>其余来源与口径字段</span>
              <em>{additionalEntries.length} 个字段 · 展开核验</em>
            </summary>
            <MarketPayloadNode
              value={Object.fromEntries(additionalEntries)}
              path="result_meta.additional"
              depth={1}
            />
          </details>
        ) : null}
      </div>
    </details>
  );
}

function EnvelopeBoundary<T>({
  query,
  children,
}: {
  query: EnvelopeQuery<T> | undefined;
  children: (envelope: ApiEnvelope<T>) => ReactNode;
}) {
  const state = queryState(query);
  if (query?.isError && !query.data) {
    return (
      <div className={styles.queryMessage} data-tone="error">
        <strong>读取失败</strong>
        <span>{errorText(query.error)}</span>
      </div>
    );
  }
  if (!query?.data) {
    return (
      <div className={styles.queryMessage}>
        <strong>{state.label}</strong>
        <span>等待后端返回完整数据。</span>
      </div>
    );
  }
  return (
    <div className={styles.envelope}>
      <div className={styles.envelopeState}>
        <span data-tone={state.tone}>{state.label}</span>
        <em>
          {query.data.result_meta.fallback_mode !== "none" ||
          query.data.result_meta.fallback_date
            ? `回退数据日：${
                query.data.result_meta.fallback_date ?? "未返回"
              } · 主数据日：${
                query.data.result_meta.as_of_date ??
                query.data.result_meta.resolved_report_date ??
                "未返回"
              }`
            : `数据日：${
                query.data.result_meta.as_of_date ??
                query.data.result_meta.resolved_report_date ??
                "未返回"
              }`}
        </em>
      </div>
      {children(query.data)}
      <ResultMetaPanel meta={query.data.result_meta} />
    </div>
  );
}

function recordKeys(rows: unknown[]) {
  const keys = new Set<string>();
  rows.forEach((row) => {
    if (isRecord(row)) Object.keys(row).forEach((key) => keys.add(key));
  });
  const preferred = [
    "series_name",
    "series_id",
    "trade_date",
    "value_numeric",
    "unit",
    "latest_change",
    "frequency",
    "quality_flag",
    "vendor_name",
    "refresh_tier",
    "fetch_mode",
    "fetch_granularity",
    "policy_note",
    "source_version",
    "vendor_version",
    "recent_points",
  ];
  return [
    ...preferred.filter((key) => keys.has(key)),
    ...[...keys].filter((key) => !preferred.includes(key)),
  ];
}

function RecordTable({
  rows,
  title,
  path,
}: {
  rows: unknown[];
  title: string;
  path: string;
}) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [searchTerm, setSearchTerm] = useState("");
  const keys = useMemo(() => recordKeys(rows), [rows]);
  const filteredRows = useMemo(() => {
    const normalized = searchTerm.trim().toLocaleLowerCase("zh-CN");
    if (!normalized) return rows;
    return rows.filter((row) =>
      searchableText(row).toLocaleLowerCase("zh-CN").includes(normalized),
    );
  }, [rows, searchTerm]);
  const pageCount = Math.max(Math.ceil(filteredRows.length / pageSize), 1);
  const safePage = Math.min(page, pageCount);
  const visibleRows = filteredRows.slice(
    (safePage - 1) * pageSize,
    safePage * pageSize,
  );

  return (
    <section className={styles.recordTableSection}>
      <header>
        <div>
          <strong>{title}</strong>
          <span>
            {filteredRows.length.toLocaleString("zh-CN")}
            {searchTerm ? ` / ${rows.length.toLocaleString("zh-CN")}` : ""} 条
            {" · "}
            {keys.length} 个返回字段
          </span>
        </div>
        <div className={styles.tableTools}>
          <label className={styles.searchField}>
            <span>搜索字段</span>
            <input
              type="search"
              value={searchTerm}
              placeholder="series_id / 名称 / vendor"
              onChange={(event) => {
                setSearchTerm(event.currentTarget.value);
                setPage(1);
              }}
            />
          </label>
          <em>横向滚动查看全部字段</em>
        </div>
      </header>
      {rows.length === 0 ? (
        <div className={styles.emptyValue}>后端返回 0 条记录。</div>
      ) : filteredRows.length === 0 ? (
        <div className={styles.emptyValue}>没有匹配当前搜索条件的记录。</div>
      ) : (
        <>
          <div className={styles.tableScroll}>
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  {keys.map((key) => (
                    <th key={key}>{fieldLabel(key)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((row, rowIndex) => {
                  const record = isRecord(row) ? row : { value: row };
                  const absoluteIndex = (safePage - 1) * pageSize + rowIndex;
                  return (
                    <tr key={`${path}-${absoluteIndex}`}>
                      <td>{absoluteIndex + 1}</td>
                      {keys.map((key) => {
                        const value = record[key];
                        return (
                          <td key={key}>
                            {Array.isArray(value) || isRecord(value) ? (
                              <details className={styles.cellDetails}>
                                <summary>{valueSummary(value)}</summary>
                                <MarketPayloadNode
                                  value={value}
                                  path={`${path}.${absoluteIndex}.${key}`}
                                  depth={2}
                                />
                              </details>
                            ) : (
                              <BackendScalarValue
                                compact
                                fieldKey={key}
                                path={`${path}.${absoluteIndex}.${key}`}
                                value={value}
                              />
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Pagination
            current={safePage}
            pageSize={pageSize}
            pageSizeOptions={[25, 50, 100]}
            showSizeChanger
            showTotal={(total) =>
              `共 ${total.toLocaleString("zh-CN")} 条${
                searchTerm ? "匹配记录" : ""
              }`
            }
            total={filteredRows.length}
            onChange={(nextPage, nextPageSize) => {
              setPage(nextPageSize === pageSize ? nextPage : 1);
              setPageSize(nextPageSize);
            }}
          />
        </>
      )}
    </section>
  );
}

function SeriesEnvelope({
  query,
  title,
  path,
}: {
  query: EnvelopeQuery<{ series: unknown[] }> | undefined;
  title: string;
  path: string;
}) {
  return (
    <EnvelopeBoundary query={query}>
      {(envelope) => {
        const { series, ...rest } = envelope.result;
        return (
          <>
            <MarketPayloadNode value={rest} path={`${path}.summary`} />
            <RecordTable rows={series} title={title} path={`${path}.series`} />
          </>
        );
      }}
    </EnvelopeBoundary>
  );
}

function GenericEnvelope({
  query,
  path,
}: {
  query: EnvelopeQuery | undefined;
  path: string;
}) {
  return (
    <EnvelopeBoundary query={query}>
      {(envelope) => <MarketPayloadNode value={envelope.result} path={path} />}
    </EnvelopeBoundary>
  );
}

function eventTitle(event: ChoiceNewsEvent, index: number) {
  const payload = event.payload_text?.trim();
  return [
    `#${index + 1}`,
    event.received_at || "时间未返回",
    event.topic_code || "未分类",
    payload ? payload.slice(0, 72) : event.event_key,
  ].join(" · ");
}

function NewsEnvelope({
  query,
  page,
  onPageChange,
}: {
  query: EnvelopeQuery<ChoiceNewsEventsPayload>;
  page: number;
  onPageChange: (page: number) => void;
}) {
  return (
    <EnvelopeBoundary query={query}>
      {(envelope) => {
        const { events, ...context } = envelope.result;
        const offset = envelope.result.offset;
        return (
          <>
            <MarketPayloadNode value={context} path="news.context" />
            <section className={styles.newsList}>
              <header>
                <strong>事件明细</strong>
                <span>
                  第 {offset + 1}–
                  {Math.min(offset + events.length, envelope.result.total_rows)}{" "}
                  条 / 共 {envelope.result.total_rows.toLocaleString("zh-CN")}{" "}
                  条
                </span>
              </header>
              {events.map((event, index) => (
                <details
                  className={styles.newsEvent}
                  key={event.event_key || `${offset}-${index}`}
                >
                  <summary>{eventTitle(event, offset + index)}</summary>
                  <MarketPayloadNode
                    value={event}
                    path={`news.events.${offset + index}`}
                  />
                </details>
              ))}
              {events.length === 0 ? (
                <div className={styles.emptyValue}>当前分页没有事件。</div>
              ) : null}
              <Pagination
                current={page}
                pageSize={NEWS_PAGE_SIZE}
                showSizeChanger={false}
                showTotal={(total) =>
                  `后端共 ${total.toLocaleString("zh-CN")} 条`
                }
                total={envelope.result.total_rows}
                onChange={onPageChange}
              />
            </section>
          </>
        );
      }}
    </EnvelopeBoundary>
  );
}

function tabCount(value: number | undefined) {
  return value === undefined ? "…" : value.toLocaleString("zh-CN");
}

export function MarketBackendDataWorkbench({
  queries,
}: MarketBackendDataWorkbenchProps) {
  const client = useApiClient();
  const [activeKey, setActiveKey] = useState("choice");
  const [newsPage, setNewsPage] = useState(1);
  const newsPageQuery = useQuery({
    queryKey: [
      "module-home",
      "market-backend-data",
      "news",
      newsPage,
      client.mode,
    ],
    queryFn: () =>
      client.getChoiceNewsEvents({
        limit: NEWS_PAGE_SIZE,
        offset: (newsPage - 1) * NEWS_PAGE_SIZE,
        includePayloadJson: true,
      }),
    enabled: activeKey === "news",
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 5 * 60_000,
  });

  const choiceCount = queries.choiceLatest?.data?.result.series.length;
  const rateCount = queries.marketRates?.data?.result.series.length;
  const catalogCount = queries.marketCatalog?.data?.result.series.length;
  const macroSectionCount = queries.macroToolkitAnalysis?.data
    ? Object.keys(queries.macroToolkitAnalysis.data.result).length
    : undefined;
  const strategySectionCount = queries.macroToolkitStrategySummaries?.data
    ? Object.keys(queries.macroToolkitStrategySummaries.data.result).length
    : undefined;
  const newsCount =
    newsPageQuery.data?.result.total_rows ??
    queries.newsEvents?.data?.result.total_rows;
  const returnedSourceCount = [
    queries.choiceLatest,
    queries.marketRates,
    queries.marketCatalog,
    queries.macroToolkitAnalysis,
    queries.macroToolkitStrategySummaries,
    queries.newsEvents,
  ].filter((query) => Boolean(query?.data)).length;
  const macroKeys = queries.macroToolkitAnalysis?.data
    ? Object.keys(queries.macroToolkitAnalysis.data.result)
    : [];
  const strategyKeys = queries.macroToolkitStrategySummaries?.data
    ? Object.keys(queries.macroToolkitStrategySummaries.data.result)
    : [];
  const newsSamples = queries.newsEvents?.data?.result.events?.slice(0, 3) ?? [];
  const verificationAsOf =
    queries.choiceLatest?.data?.result_meta.as_of_date ??
    queries.choiceLatest?.data?.result_meta.resolved_report_date ??
    queries.choiceLatest?.data?.result_meta.fallback_date ??
    "日期未返回";
  const sourceAuditRows = [
    {
      key: "choice",
      label: "最新行情",
      count: tabCount(choiceCount),
      query: queries.choiceLatest,
    },
    {
      key: "rates",
      label: "正式利率",
      count: tabCount(rateCount),
      query: queries.marketRates,
    },
    {
      key: "catalog",
      label: "数据目录",
      count: tabCount(catalogCount),
      query: queries.marketCatalog,
    },
    {
      key: "macro",
      label: "宏观全量",
      count: tabCount(macroSectionCount),
      query: queries.macroToolkitAnalysis,
    },
    {
      key: "strategies",
      label: "策略全量",
      count: tabCount(strategySectionCount),
      query: queries.macroToolkitStrategySummaries,
    },
    {
      key: "news",
      label: "新闻事件",
      count: tabCount(newsCount),
      query: queries.newsEvents,
    },
  ].map((row) => ({ ...row, state: queryState(row.query) }));

  const items = [
    {
      key: "choice",
      label: `最新行情 ${tabCount(choiceCount)}`,
      children: (
        <SeriesEnvelope
          query={queries.choiceLatest}
          title="Choice 最新行情序列"
          path="choice"
        />
      ),
    },
    {
      key: "rates",
      label: `正式利率 ${tabCount(rateCount)}`,
      children: (
        <SeriesEnvelope
          query={queries.marketRates}
          title="市场利率完整序列"
          path="rates"
        />
      ),
    },
    {
      key: "catalog",
      label: `数据目录 ${tabCount(catalogCount)}`,
      children: (
        <SeriesEnvelope
          query={queries.marketCatalog}
          title="市场数据完整目录"
          path="catalog"
        />
      ),
    },
    {
      key: "macro",
      label: `宏观全量 ${tabCount(macroSectionCount)}`,
      children: (
        <GenericEnvelope query={queries.macroToolkitAnalysis} path="macro" />
      ),
    },
    {
      key: "strategies",
      label: `策略全量 ${tabCount(strategySectionCount)}`,
      children: (
        <GenericEnvelope
          query={queries.macroToolkitStrategySummaries}
          path="strategies"
        />
      ),
    },
    {
      key: "news",
      label: `新闻事件 ${tabCount(newsCount)}`,
      children: (
        <NewsEnvelope
          query={newsPageQuery}
          page={newsPage}
          onPageChange={setNewsPage}
        />
      ),
    },
  ];

  return (
    <section
      id="market-backend-data-all"
      className={styles.workbench}
      data-testid="module-home-market-backend-data"
    >
      <header className={styles.workbenchHeader}>
        <div>
          <span>04</span>
          <h2>数据核验 · 6 来源</h2>
          <p>
            六条后端读链路保留全部返回字段；左侧核对数据，右侧固定查看口径、质量、回退与日期依据。
          </p>
        </div>
        <div className={styles.coverageSummary}>
          <span>数据日期</span>
          <em>{verificationAsOf}</em>
          <em data-tone={returnedSourceCount === 6 ? "ok" : "watch"}>
            {returnedSourceCount} / 6 读取已返回
          </em>
        </div>
      </header>
      <Tabs activeKey={activeKey} items={items} onChange={setActiveKey} />
      <div
        className={styles.auditSummary}
        data-testid="module-home-market-backend-audit-summary"
      >
        <article className={styles.auditPanel}>
          <header>
            <strong>宏观 / 策略对象</strong>
            <span>跨来源结构预览</span>
          </header>
          <div className={styles.auditTree}>
            <div>
              <span>macro</span>
              <strong>{tabCount(macroSectionCount)}</strong>
              <em>{macroKeys.slice(0, 3).join(" / ") || "等待返回"}</em>
            </div>
            <div>
              <span>strategy</span>
              <strong>{tabCount(strategySectionCount)}</strong>
              <em>{strategyKeys.slice(0, 3).join(" / ") || "等待返回"}</em>
            </div>
          </div>
        </article>

        <article className={styles.auditPanel}>
          <header>
            <strong>新闻分页预览</strong>
            <span>母查询最新 3 条</span>
          </header>
          <div className={styles.auditNews}>
            {newsSamples.length > 0 ? (
              newsSamples.map((event: ChoiceNewsEvent, index: number) => (
                <div key={event.event_key}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <strong>
                    {event.payload_text || event.error_msg || event.event_key}
                  </strong>
                  <em>{event.received_at.slice(0, 10)}</em>
                </div>
              ))
            ) : (
              <div>
                <span>--</span>
                <strong>等待新闻母查询返回</strong>
                <em>--</em>
              </div>
            )}
          </div>
        </article>

        <article className={styles.auditPanel}>
          <header>
            <strong>数据源状态</strong>
            <span>{returnedSourceCount} / 6 已返回</span>
          </header>
          <div className={styles.sourceChecklist}>
            {sourceAuditRows.map((row) => (
              <div
                data-testid={`module-home-market-backend-source-status-${row.key}`}
                data-tone={row.state.tone}
                key={row.key}
              >
                <span>{row.label}</span>
                <strong>{row.count}</strong>
                <em>{row.state.label}</em>
              </div>
            ))}
          </div>
        </article>
      </div>
    </section>
  );
}
