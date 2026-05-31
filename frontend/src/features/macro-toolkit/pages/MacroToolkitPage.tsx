import { useCallback, useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  LineChartOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  ToolOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Alert, Button, Select, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useQuery } from "@tanstack/react-query";

import { runPollingTask } from "../../../app/jobs/polling";
import { useApiClient } from "../../../api/client";
import type {
  MacroToolkitCapability,
  MacroToolkitCapabilityResult,
  MacroToolkitChoiceStockRefreshRun,
  MacroToolkitAShareRiskPayload,
  MacroToolkitIndicator,
  MacroToolkitOutputFile,
  MacroToolkitRunResponse,
  MacroToolkitScriptRecord,
  MacroToolkitSignalCard,
  MacroToolkitShadowPortfolio,
  MacroToolkitShadowPortfolioHolding,
  MacroToolkitShadowPortfolioPeriodReturn,
  MacroToolkitShadowPortfolioReport,
  MacroToolkitSourceCheck,
  MacroToolkitStrategySummary,
} from "../../../api/macroToolkitClient";
import {
  DataStatusStrip,
  PageSectionLead,
  PageStateSurface,
} from "../../../components/page/PagePrimitives";

import "./MacroToolkitPage.css";

const GROUP_LABELS: Record<string, string> = {
  allocation: "配置",
  credit: "信用",
  diagnostic: "诊断",
  macro_signal: "宏观信号",
  market_regime: "市场状态",
  news: "新闻",
  rates: "利率",
  report: "报告",
  risk: "风险",
};

const EMPTY_SCRIPTS: MacroToolkitScriptRecord[] = [];
const MACRO_TOOLKIT_ANALYSIS_KIND = "macro_toolkit.analysis";
const MACRO_TOOLKIT_UI_RULE_VERSION = "rv_macro_toolkit_ui_v1";

function groupLabel(group: string) {
  return GROUP_LABELS[group] ?? group;
}

function formatSize(size: number) {
  if (size >= 1024 * 1024) {
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
  }
  if (size >= 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${size} B`;
}

function formatSourceCheck(check: MacroToolkitSourceCheck) {
  if (!check.latest) {
    return "未命中";
  }
  return `${check.latest.series_id} · ${check.latest.date}`;
}

function statusTone(status: MacroToolkitRunResponse["status"]) {
  if (status === "completed") return "success";
  if (status === "timeout") return "warning";
  return "error";
}

function toneTagColor(tone: MacroToolkitSignalCard["tone"]) {
  if (tone === "positive") return "green";
  if (tone === "negative") return "red";
  if (tone === "missing") return "default";
  return "blue";
}

function riskLevelColor(level: MacroToolkitAShareRiskPayload["risk_level"]) {
  if (level === "green") return "green";
  if (level === "yellow") return "gold";
  if (level === "orange") return "orange";
  if (level === "red") return "red";
  return "default";
}

function riskLevelTone(level: MacroToolkitAShareRiskPayload["risk_level"]): MacroToolkitSignalCard["tone"] {
  if (level === "green") return "positive";
  if (level === "unknown") return "missing";
  return level === "yellow" ? "neutral" : "negative";
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    current: "已对齐",
    lagging: "轻微滞后",
    stale: "陈旧",
    missing: "缺失",
    unknown: "待确认",
    ready: "数据齐备",
    partial: "部分就绪",
    not_required: "无需数据",
    complete: "已完成",
    degraded: "部分降级",
    unavailable: "不可用",
    deferred: "已延后",
    loading: "加载中",
    failed: "失败",
    aligned: "已对齐",
    fallback: "最近快照",
    library_ready: "函数已迁入",
    wired: "已接线",
    visible: "已展示",
    not_wired: "未接线",
    planned: "待接入",
    sample_only: "样例展示",
  };
  return labels[status] ?? status;
}

function statusColor(status: string) {
  if (["current", "ready", "library_ready", "complete", "wired", "visible"].includes(status)) {
    return "green";
  }
  if (["lagging", "partial", "planned", "degraded", "sample_only", "deferred", "loading"].includes(status)) {
    return "gold";
  }
  if (["stale", "missing", "not_wired", "unavailable", "failed"].includes(status)) return "red";
  return "default";
}

function compactText(text: string | null | undefined, maxLength = 34) {
  if (!text) return "";
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength - 1)}…`;
}

function macroStatusIconTone(tone: MacroToolkitSignalCard["tone"] | "positive" | "neutral") {
  if (tone === "positive") return "positive";
  if (tone === "negative") return "negative";
  if (tone === "missing") return "missing";
  return "neutral";
}

function MacroStatusIcon({
  tone = "neutral",
  children,
}: {
  tone?: MacroToolkitSignalCard["tone"] | "positive" | "neutral";
  children: ReactNode;
}) {
  return (
    <span className={`macro-toolkit-status-icon macro-toolkit-status-icon--${macroStatusIconTone(tone)}`}>
      {children}
    </span>
  );
}

function MacroToolkitContractBoundary({
  formalUseAllowed,
  resultKind,
  ruleVersion,
}: {
  formalUseAllowed?: boolean;
  resultKind?: string;
  ruleVersion?: string;
}) {
  return (
    <div
      className="macro-toolkit-contract-boundary"
      data-testid="macro-toolkit-contract-boundary"
      aria-label="宏观工具口径边界"
    >
      <span>
        <SafetyCertificateOutlined />
        分析/工具口径
      </span>
      <strong>{formalUseAllowed ? "正式可用" : "非正式口径"}</strong>
      <small>{resultKind ?? MACRO_TOOLKIT_ANALYSIS_KIND}</small>
      <small>{ruleVersion ?? MACRO_TOOLKIT_UI_RULE_VERSION}</small>
    </div>
  );
}

function formatValue(value: number | null, unit = "") {
  if (value === null) {
    return "缺失";
  }
  const digits = Math.abs(value) >= 100 ? 2 : 4;
  return `${value.toFixed(digits)}${unit}`;
}

function formatChange(change: number | null, changePct: number | null) {
  if (change === null && changePct === null) {
    return "无可比";
  }
  if (changePct !== null) {
    return `${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}%`;
  }
  return `${change! >= 0 ? "+" : ""}${change!.toFixed(4)}`;
}

function formatPercent(value: number | null | undefined) {
  if (value == null) {
    return "缺失";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function clampScore(score: number | null | undefined) {
  if (score == null) {
    return 0;
  }
  return Math.min(100, Math.max(0, score));
}

type ScoreStyle = CSSProperties & { "--score": string };

function scoreStyle(score: number | null | undefined): ScoreStyle {
  return { "--score": `${clampScore(score)}%` };
}

function formatQueryError(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }
  return "宏观工具接口暂不可用";
}

function isReadyStatus(status: string) {
  return ["current", "ready", "library_ready", "complete", "wired", "visible", "ok"].includes(status);
}

export default function MacroToolkitPage() {
  const client = useApiClient();
  const [selectedGroup, setSelectedGroup] = useState("all");
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<MacroToolkitRunResponse | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [refreshResult, setRefreshResult] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [isRefreshingCffex, setIsRefreshingCffex] = useState(false);
  const [stockRefreshResult, setStockRefreshResult] = useState<string | null>(null);
  const [stockRefreshError, setStockRefreshError] = useState<string | null>(null);
  const [isRefreshingChoiceStock, setIsRefreshingChoiceStock] = useState(false);
  const [isRunning, setIsRunning] = useState(false);

  const analysisQuery = useQuery({
    queryKey: ["macro-toolkit", "analysis"],
    queryFn: () => client.getMacroToolkitAnalysis(),
    staleTime: 60_000,
  });

  const scriptsQuery = useQuery({
    queryKey: ["macro-toolkit", "scripts"],
    queryFn: () => client.getMacroToolkitScripts(),
    staleTime: 60_000,
  });

  const strategyQuery = useQuery({
    queryKey: ["macro-toolkit", "strategy-summaries"],
    queryFn: () => client.getMacroToolkitStrategySummaries(),
    staleTime: 60_000,
  });

  const payload = scriptsQuery.data?.result;
  const analysis = analysisQuery.data?.result;
  const scripts = payload?.scripts ?? EMPTY_SCRIPTS;
  const capabilityResults = analysis?.capability_results ?? [];
  const strategyPayload = strategyQuery.data?.result;
  const strategySummaries = strategyPayload?.strategy_summaries ?? analysis?.strategy_summaries ?? [];
  const shadowPortfolioReport =
    strategyPayload?.shadow_portfolio_report ?? analysis?.shadow_portfolio_report ?? null;
  const fullRealStrategyCount = strategySummaries.filter((strategy) => hasCompleteRealStrategyChain(strategy)).length;
  const partialRealStrategyCount = strategySummaries.filter(
    (strategy) => hasRealStrategySource(strategy) && !hasCompleteRealStrategyChain(strategy),
  ).length;
  const degradedStrategyCount = strategySummaries.filter(
    (strategy) => hasRealStrategySource(strategy) && strategy.status !== "complete",
  ).length;
  const sampleStrategyCount = strategySummaries.filter((strategy) => strategy.status === "sample_only").length;
  const hasLoadedStrategySummaries = strategySummaries.length > 0;
  const strategySupplyState =
    strategyQuery.isFetching && !hasLoadedStrategySummaries
      ? "loading"
      : strategyQuery.isError && !hasLoadedStrategySummaries
        ? "failed"
        : "loaded";
  const hasRealStrategyData = strategySummaries.some((strategy) => hasRealStrategySource(strategy));
  const strategyDescription =
    strategySupplyState === "loading"
      ? "策略摘要正在生成，核心判断和市场踩踏风险已先返回。"
      : strategySupplyState === "failed"
        ? "策略摘要读取失败，当前不能判断策略供数闭环。"
        : hasRealStrategyData
          ? "展示已合入宏观模块的 A股策略能力；已接入股票行情或因子快照，不作为正式投资信号。"
          : "展示已合入宏观模块的 A股策略能力；当前为合成样例和模块可用性检查，不作为正式投资信号。";
  const groupOptions = useMemo(
    () => [
      { value: "all", label: "全部分组" },
      ...[...(payload?.groups ?? [])].sort().map((group) => ({
        value: group,
        label: groupLabel(group),
      })),
    ],
    [payload?.groups],
  );

  const filteredScripts = useMemo(() => {
    if (selectedGroup === "all") {
      return scripts;
    }
    return scripts.filter((script) => script.group === selectedGroup);
  }, [scripts, selectedGroup]);

  useEffect(() => {
    if (selectedName || filteredScripts.length === 0) {
      return;
    }
    setSelectedName(filteredScripts[0]!.name);
  }, [filteredScripts, selectedName]);

  const selectedScript = useMemo(
    () => scripts.find((script) => script.name === selectedName) ?? filteredScripts[0] ?? null,
    [filteredScripts, scripts, selectedName],
  );
  const outputDetail = payload?.output_files.length
    ? `${payload.output_files[0]!.name} · ${formatSize(payload.output_files[0]!.size_bytes)}`
    : payload?.output_dir ?? "data/macro_toolkit/output";
  const cffexStatus = payload?.cffex_member_rank ?? analysis?.cffex_member_rank ?? null;
  const choiceStockRefresh =
    strategyPayload?.choice_stock_refresh ?? payload?.choice_stock_refresh ?? analysis?.choice_stock_refresh ?? null;
  const omittedEntries = Object.entries(payload?.omitted_scripts ?? {});
  const sourceChecks = payload?.source_checks ?? analysis?.source_checks ?? [];
  const capabilityItems = payload?.capabilities ?? analysis?.capabilities ?? [];
  const analysisMeta = analysisQuery.data?.result_meta;
  const sourceHitCount = sourceChecks.filter((check) => check.row_count > 0).length;
  const availableScriptCount = scripts.filter((script) => script.available).length;
  const readyCapabilityCount = capabilityItems.filter((item) => isReadyStatus(item.data_status)).length;
  const wiredCapabilityCount = capabilityItems.filter((item) =>
    isReadyStatus(item.route_status) && isReadyStatus(item.frontend_status),
  ).length;
  const degradedResultCount = capabilityResults.filter((result) => result.status !== "complete").length;
  const missingIndicatorCount = analysis?.indicators.filter((indicator) => indicator.quality === "missing").length ?? 0;
  const primarySignal =
    analysis?.signal_cards
      .filter((card) => card.score != null)
      .sort((left, right) => (right.score ?? 0) - (left.score ?? 0))[0] ?? null;
  const isMacroRefreshing = analysisQuery.isFetching || scriptsQuery.isFetching || strategyQuery.isFetching;
  const queryErrorText = [analysisQuery.error, scriptsQuery.error, strategyQuery.error]
    .filter(Boolean)
    .map(formatQueryError)
    .join("；");
  const failedReadMessages = [analysisQuery.error, scriptsQuery.error, strategyQuery.error]
    .filter(Boolean)
    .map(formatQueryError);
  const runtimeSections = analysis?.runtime_status?.deferred_sections ?? [];

  const runSelectedScript = useCallback(async () => {
    if (!selectedScript) {
      return;
    }
    setIsRunning(true);
    setRunError(null);
    setRunResult(null);
    try {
      const result = await client.runMacroToolkitScript(selectedScript.name);
      setRunResult(result);
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch(), strategyQuery.refetch()]);
    } catch (error) {
      setRunError(error instanceof Error ? error.message : "运行失败");
    } finally {
      setIsRunning(false);
    }
  }, [analysisQuery, client, scriptsQuery, selectedScript, strategyQuery]);

  const refreshCffexMemberRank = useCallback(async () => {
    setIsRefreshingCffex(true);
    setRefreshError(null);
    setRefreshResult(null);
    try {
      const response = await client.refreshCffexMemberRank({
        tradeDate: analysis?.as_of_date ?? undefined,
      });
      const rank = response.result.cffex_member_rank;
      setRefreshResult(`刷新完成：${rank.row_count} 行，最新交易日 ${rank.latest_trade_date ?? "缺失"}`);
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch(), strategyQuery.refetch()]);
    } catch (error) {
      setRefreshError(error instanceof Error ? error.message : "刷新席位失败");
    } finally {
      setIsRefreshingCffex(false);
    }
  }, [analysis?.as_of_date, client, scriptsQuery, analysisQuery, strategyQuery]);

  const refreshChoiceStock = useCallback(async () => {
    setIsRefreshingChoiceStock(true);
    setStockRefreshError(null);
    setStockRefreshResult("正在刷新股票历史数据和完整因子");
    try {
      const refresh = await runPollingTask<MacroToolkitChoiceStockRefreshRun>({
        start: async () => {
          const response = await client.refreshChoiceStock({
            asOfDate: analysis?.as_of_date ?? undefined,
            refreshHistory: true,
            refreshFactors: true,
            factorMaxStockCount: null,
          });
          return response.result.refresh;
        },
        getStatus: async (runId) => {
          const response = await client.getChoiceStockRefreshStatus(runId);
          return response.result.refresh;
        },
        intervalMs: 5_000,
        maxAttempts: 240,
        onUpdate: (payload) => {
          setStockRefreshResult(
            payload.status === "completed"
              ? `刷新完成：历史 ${payload.history_row_count ?? "-"} 行，因子 ${payload.factor_row_count ?? "-"} 行`
              : `刷新状态：${payload.status}`,
          );
        },
      });
      if (refresh.status !== "completed") {
        throw new Error(refresh.error_message ?? `股票刷新未完成：${refresh.status}`);
      }
      setStockRefreshResult(
        `刷新完成：历史 ${refresh.history_row_count ?? "-"} 行，因子 ${refresh.factor_row_count ?? "-"} 行`,
      );
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch(), strategyQuery.refetch()]);
    } catch (error) {
      setStockRefreshError(error instanceof Error ? error.message : "刷新股票数据失败");
      setStockRefreshResult(null);
    } finally {
      setIsRefreshingChoiceStock(false);
    }
  }, [analysis?.as_of_date, analysisQuery, client, scriptsQuery, strategyQuery]);

  const indicatorColumns: ColumnsType<MacroToolkitIndicator> = [
    {
      title: "指标",
      dataIndex: "label",
      key: "label",
      render: (_, item) => (
        <div className="macro-toolkit-script-cell">
          <span className="macro-toolkit-script-name">{item.label}</span>
          <span className="macro-toolkit-script-file">{item.alias}</span>
        </div>
      ),
    },
    {
      title: "分组",
      dataIndex: "group",
      key: "group",
      width: 120,
      render: (group: string) => <Tag>{group}</Tag>,
    },
    {
      title: "最新值",
      dataIndex: "latest_value",
      key: "latest_value",
      width: 150,
      render: (_, item) => <IndicatorValueCell item={item} />,
    },
    {
      title: "变化",
      dataIndex: "change_pct",
      key: "change_pct",
      width: 110,
      render: (_, item) => <DeltaCell change={item.change} changePct={item.change_pct} />,
    },
    {
      title: "日期",
      dataIndex: "latest_date",
      key: "latest_date",
      width: 120,
      render: (date: string | null, item) => (
        <div className="macro-toolkit-date-cell">
          <span>{date ?? "缺失"}</span>
          <Tag color={item.quality === "ok" ? "green" : "red"}>
            {item.quality === "ok" ? "可用" : "缺失"}
          </Tag>
        </div>
      ),
    },
    {
      title: "来源",
      dataIndex: "source",
      key: "source",
      width: 120,
      render: (source: string | null, item) => (
        <div className="macro-toolkit-source-cell">
          <span>{source ?? "未命中"}</span>
          <small>{item.series_id ?? item.alias}</small>
        </div>
      ),
    },
  ];

  const scriptColumns: ColumnsType<MacroToolkitScriptRecord> = [
    {
      title: "脚本",
      dataIndex: "name",
      key: "name",
      render: (_, script) => (
        <div className="macro-toolkit-script-cell">
          <span className="macro-toolkit-script-name">{script.name}</span>
          <span className="macro-toolkit-script-file">{script.filename}</span>
        </div>
      ),
    },
    {
      title: "分组",
      dataIndex: "group",
      key: "group",
      render: (group: string) => <Tag>{groupLabel(group)}</Tag>,
      width: 120,
    },
    {
      title: "数据源",
      dataIndex: "default_data_sources",
      key: "default_data_sources",
      render: (sources: string[]) => (
        <div className="macro-toolkit-tag-row">
          {sources.map((source) => (
            <Tag color={source === "choice" ? "blue" : "green"} key={source}>
              {source}
            </Tag>
          ))}
        </div>
      ),
      width: 160,
    },
    {
      title: "依赖",
      dataIndex: "optional_dependencies",
      key: "optional_dependencies",
      render: (deps: string[]) =>
        deps.length > 0 ? deps.join(" / ") : "内置",
    },
    {
      title: "状态",
      dataIndex: "available",
      key: "available",
      render: (available: boolean) => (
        <Tag color={available ? "green" : "red"}>{available ? "可运行" : "缺失"}</Tag>
      ),
      width: 100,
    },
  ];

  const capabilityColumns: ColumnsType<MacroToolkitCapability> = [
    {
      title: "功能",
      dataIndex: "label",
      key: "label",
      render: (_, item) => (
        <div className="macro-toolkit-script-cell">
          <span className="macro-toolkit-script-name">
            {item.legacy_module} · {item.label}
          </span>
          <span className="macro-toolkit-script-file">{item.group}</span>
        </div>
      ),
    },
    {
      title: "代码",
      dataIndex: "implementation_status",
      key: "implementation_status",
      width: 120,
      render: (status: string) => <Tag color={statusColor(status)}>{statusLabel(status)}</Tag>,
    },
    {
      title: "页面/API",
      dataIndex: "route_status",
      key: "route_status",
      width: 140,
      render: (status: string, item) => (
        <div className="macro-toolkit-tag-row">
          <Tag color={statusColor(status)}>{statusLabel(status)}</Tag>
          <Tag color={statusColor(item.frontend_status)}>{statusLabel(item.frontend_status)}</Tag>
        </div>
      ),
    },
    {
      title: "数据",
      dataIndex: "data_status",
      key: "data_status",
      width: 140,
      render: (status: string, item) => <CapabilityDataCell status={status} item={item} />,
    },
    {
      title: "下一步",
      dataIndex: "next_step",
      key: "next_step",
    },
  ];

  const outputColumns: ColumnsType<MacroToolkitOutputFile> = [
    { title: "文件", dataIndex: "name", key: "name" },
    {
      title: "大小",
      dataIndex: "size_bytes",
      key: "size_bytes",
      width: 100,
      render: (size: number) => formatSize(size),
    },
    {
      title: "更新时间",
      dataIndex: "modified_at",
      key: "modified_at",
      width: 220,
    },
  ];

  const isAnalysisLoading = analysisQuery.isLoading && !analysis;

  if (!payload && !analysis && (scriptsQuery.isError || analysisQuery.isError)) {
    return (
      <PageStateSurface
        variant="error"
        testId="macro-toolkit-error-state"
        className="macro-toolkit-error-state"
        title="宏观工具暂不可用"
        description={queryErrorText || "后端宏观模块没有返回可展示数据。"}
        actions={
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              void analysisQuery.refetch();
              void scriptsQuery.refetch();
              void strategyQuery.refetch();
            }}
            loading={analysisQuery.isFetching || scriptsQuery.isFetching || strategyQuery.isFetching}
          >
            重试读取
          </Button>
        }
      >
        <MacroToolkitContractBoundary />
        <div className="macro-toolkit-error-sources" aria-label="宏观工具失败来源">
          <span>失败来源</span>
          {failedReadMessages.length ? (
            failedReadMessages.map((message) => <small key={message}>{message}</small>)
          ) : (
            <small>后端宏观模块没有返回可展示数据。</small>
          )}
        </div>
      </PageStateSurface>
    );
  }

  return (
    <div className="macro-toolkit-page">
      <section
        data-testid="macro-toolkit-tailwind-cockpit"
        className="overflow-hidden rounded-xl border border-blue-100 bg-white text-slate-900 shadow-lg shadow-blue-100/70"
      >
        <div className="border-b border-blue-100 bg-[linear-gradient(135deg,#ffffff_0%,#f8fbff_52%,#eaf3ff_100%)] p-4 lg:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 text-[12px] font-semibold text-slate-500">
                <ClockCircleOutlined className="text-blue-500" />
                <span className="font-mono">{analysis?.as_of_date ?? "DATE_MISSING"}</span>
              </div>
              <h1 className="mt-2 text-2xl font-black leading-tight text-blue-950 lg:text-4xl">宏观分析结果</h1>
            </div>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                void analysisQuery.refetch();
                void scriptsQuery.refetch();
                void strategyQuery.refetch();
              }}
              loading={isMacroRefreshing}
            >
              刷新结果
            </Button>
          </div>

          <div className="mt-4 grid gap-3">
            <MacroToolkitContractBoundary
              formalUseAllowed={analysisMeta?.formal_use_allowed}
              resultKind={analysisMeta?.result_kind}
              ruleVersion={analysisMeta?.rule_version}
            />
            <div className="min-w-0 rounded-lg border border-blue-100 bg-blue-50/70 p-4 shadow-sm shadow-blue-100/60">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-600">
                <MacroStatusIcon tone={analysis?.conclusion.tone ?? "missing"}>
                  {analysis?.conclusion.tone === "negative" || !analysis ? <WarningOutlined /> : <LineChartOutlined />}
                </MacroStatusIcon>
                投研观点
              </div>
              <strong className="mt-3 block truncate text-3xl font-black text-blue-950">
                {analysis?.conclusion.stance ?? "读取中"}
              </strong>
              <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-700" title={analysis?.conclusion.summary}>
                {analysis?.conclusion.summary ?? "正在从系统数据源生成宏观判断。"}
              </p>
            </div>
            <div className="grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-3">
              <TailwindMetricTile
                icon={<SafetyCertificateOutlined />}
                label="证据覆盖"
                value={formatPercent(analysis?.coverage.hit_rate)}
                detail={`${analysis?.coverage.hit_count ?? 0}/${analysis?.coverage.indicator_count ?? 0} 指标命中`}
              />
              <TailwindMetricTile
                icon={<ClockCircleOutlined />}
                label="分析日期"
                value={analysis?.as_of_date ?? "缺失"}
                detail={(analysis?.default_data_sources ?? []).join(" + ") || "choice + tushare"}
              />
              <TailwindMetricTile
                icon={<ThunderboltOutlined />}
                label="能力闭环"
                value={`${readyCapabilityCount}/${capabilityItems.length || 0}`}
                detail={`${wiredCapabilityCount} 项已接到页面/API`}
              />
            </div>
          </div>
        </div>

      </section>

      {analysisQuery.isError ? (
        <Alert type="error" showIcon message="宏观分析结果加载失败" />
      ) : null}

      {isAnalysisLoading ? (
        <>
          <div data-testid="macro-toolkit-initial-analysis-loading">
            <Alert
              type="info"
              showIcon
              message="核心分析加载中"
              description="页面口径边界已就绪；核心信号、市场踩踏风险和脚本注册表会在后端返回后自动补上。"
            />
          </div>
          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="signals"
              title="核心信号"
              description="等待后端宏观 analysis 结果返回。"
            />
            <div className="macro-toolkit-empty-output">核心分析加载中，暂不显示占位结论。</div>
          </section>
          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="risk"
              title="市场踩踏风险"
              description="等待 A 股宽度、跌停、成交与回落压力判断返回。"
            />
            <div className="macro-toolkit-empty-output">市场踩踏风险加载中，暂不推导风险等级。</div>
          </section>
        </>
      ) : null}

      {analysis ? (
        <>
          <DataStatusStrip className="macro-toolkit-status-strip">
            <span title={`读取口径：${analysisQuery.data?.result_meta.basis ?? "-"}`}>
              <DatabaseOutlined /> {analysisQuery.data?.result_meta.basis ?? "-"}
            </span>
            <span title={`质量：${analysisQuery.data?.result_meta.quality_flag ?? "-"}`}>
              <SafetyCertificateOutlined /> {analysisQuery.data?.result_meta.quality_flag ?? "-"}
            </span>
            <span title={`建议：${analysis.conclusion.recommended_action}`}>
              <ThunderboltOutlined /> {compactText(analysis.conclusion.recommended_action, 24)}
            </span>
          </DataStatusStrip>

          {runtimeSections.length ? (
            <div className="macro-toolkit-runtime-strip" aria-label="宏观工具运行状态">
              {runtimeSections.map((section) => (
                <span key={section.key}>
                  <ClockCircleOutlined />
                  {section.label} · <Tag color={statusColor(section.status)}>{statusLabel(section.status)}</Tag>
                </span>
              ))}
            </div>
          ) : null}

          <div className="macro-toolkit-readiness-strip" aria-label="宏观工具投研总览">
            <ReadinessTile
              icon={<LineChartOutlined />}
              label="主信号"
              value={primarySignal ? `${primarySignal.title} · ${primarySignal.stance}` : "缺失"}
              detail={primarySignal?.evidence.join(" / ") ?? "暂无可排序信号"}
              tone={primarySignal?.tone ?? "missing"}
            />
            <ReadinessTile
              icon={<ClockCircleOutlined />}
              label="数据新鲜度"
              value={analysis.as_of_date ?? "缺失"}
              detail={`${missingIndicatorCount} 个指标缺失；${sourceHitCount} 个源命中`}
              tone={missingIndicatorCount > 0 ? "neutral" : "positive"}
            />
            <ReadinessTile
              icon={<ThunderboltOutlined />}
              label="模型结果"
              value={`${capabilityResults.length} 个功能输出`}
              detail={`${degradedResultCount} 个降级或不可用结果`}
              tone={degradedResultCount > 0 ? "neutral" : "positive"}
            />
          </div>

          {analysis.warnings.length ? (
            <Alert
              type="warning"
              showIcon
              message="分析限制"
              description={analysis.warnings.join(" ")}
            />
          ) : null}

          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="signals"
              title="核心信号"
              description="由系统内 Choice/Tushare 序列直接计算，脚本产物作为补充证据。"
            />
            <div className="macro-toolkit-signal-grid">
              {analysis.signal_cards.map((card) => (
                <div
                  className={`macro-toolkit-signal-card macro-toolkit-signal-card--${card.tone}`}
                  key={card.key}
                  style={scoreStyle(card.score)}
                >
                  <div className="macro-toolkit-signal-head">
                    <span>{card.title}</span>
                    <Tag color={toneTagColor(card.tone)}>{card.stance}</Tag>
                  </div>
                  <strong>{card.score === null ? "缺失" : card.score}</strong>
                  <div className="macro-toolkit-score-track" aria-hidden="true">
                    <span />
                  </div>
                  <small>{card.evidence.join(" / ")}</small>
                </div>
              ))}
            </div>
          </section>

          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="risk"
              title="市场踩踏风险"
              description="接入宏观分析结果链路的 A股盘后宽度、跌停、成交与回落压力判断。"
            />
            <AShareRiskPanel risk={analysis.a_share_risk} />
          </section>

          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="indicators"
              title="指标矩阵"
              description="展示每个宏观指标的最新值、变化、日期和数据来源。"
            />
            <Table
              rowKey="alias"
              size="small"
              columns={indicatorColumns}
              dataSource={analysis.indicators}
              pagination={false}
              tableLayout="fixed"
              scroll={{ x: 920 }}
              rowClassName={(item) =>
                item.quality === "missing" ? "macro-toolkit-row--missing" : ""
              }
            />
          </section>

          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="results"
              title="功能结果"
              description="M7-M16 已按现有宏观纯函数和正式事实表输出结果，缺口只保留为数据降级提示。"
            />
            {capabilityResults.length ? (
              <div className="macro-toolkit-capability-result-grid">
                {capabilityResults.map((result) => (
                  <CapabilityResultCard result={result} key={result.key} />
                ))}
              </div>
            ) : analysis?.runtime_status?.analysis_scope === "core" ? (
              <Alert
                type="info"
                showIcon
                message="M7-M16 功能结果正在生成"
                description="核心判断和市场踩踏风险已先返回。"
              />
            ) : (
              <div className="macro-toolkit-empty-output">暂无 M7-M16 功能结果。</div>
            )}
          </section>

          <section className="macro-toolkit-section">
            <PageSectionLead
              eyebrow="strategies"
              title="策略展示"
              description={strategyDescription}
            />
            <div className="macro-toolkit-stock-refresh-panel">
              <div className="macro-toolkit-cffex-metrics">
                <MetricTile
                  label="股票历史"
                  value={choiceStockRefresh?.daily_observation?.stock_count ?? 0}
                  detail={choiceStockTableDetail(choiceStockRefresh?.daily_observation, "latest_trade_date")}
                />
                <MetricTile
                  label="完整因子"
                  value={choiceStockRefresh?.factor_snapshot?.stock_count ?? 0}
                  detail={choiceStockTableDetail(choiceStockRefresh?.factor_snapshot, "as_of_date")}
                />
                <MetricTile
                  label="刷新权限"
                  value={choiceStockRefresh?.permission?.mode === "identity_only" ? "已开放" : "待确认"}
                  detail={choiceStockRefresh?.permission?.resource ?? "choice_stock.refresh"}
                />
              </div>
              <div className="macro-toolkit-cffex-actions">
                <Button
                  icon={<ReloadOutlined />}
                  loading={isRefreshingChoiceStock}
                  onClick={() => void refreshChoiceStock()}
                >
                  刷新股票数据
                </Button>
                {stockRefreshResult ? <Alert type="success" showIcon message={stockRefreshResult} /> : null}
                {stockRefreshError ? <Alert type="error" showIcon message={stockRefreshError} /> : null}
              </div>
            </div>
            <div className="macro-toolkit-strategy-supply-strip" aria-label="策略供数闭环">
              <span className="macro-toolkit-strategy-supply-label">
                <DatabaseOutlined />
                策略供数闭环
              </span>
              {strategySupplyState === "loaded" ? (
                <>
                  <span>
                    <DatabaseOutlined />
                    完整链路 {fullRealStrategyCount}/{strategySummaries.length}
                  </span>
                  <span>
                    <SafetyCertificateOutlined />
                    部分链路 {partialRealStrategyCount}
                  </span>
                  <span>
                    <SafetyCertificateOutlined />
                    降级 {degradedStrategyCount}
                  </span>
                  <span>
                    <SafetyCertificateOutlined />
                    样例 {sampleStrategyCount}
                  </span>
                </>
              ) : (
                <span>
                  <ClockCircleOutlined />
                  策略供数 {statusLabel(strategySupplyState)}
                </span>
              )}
              <span>
                <ClockCircleOutlined />
                股票历史 {choiceStockTableSummary(choiceStockRefresh?.daily_observation, "latest_trade_date")}
              </span>
              <span>
                <ClockCircleOutlined />
                因子快照 {choiceStockTableSummary(choiceStockRefresh?.factor_snapshot, "as_of_date")}
              </span>
            </div>
            <ShadowPortfolioReportPanel report={shadowPortfolioReport} />
            {strategySummaries.length ? (
              <div className="macro-toolkit-strategy-grid">
                {strategySummaries.map((strategy) => (
                  <StrategySummaryCard strategy={strategy} key={strategy.key} />
                ))}
              </div>
            ) : strategyQuery.isFetching ? (
              <Alert
                type="info"
                showIcon
                message="策略展示正在生成"
                description="核心判断和市场踩踏风险已先返回。"
              />
            ) : strategyQuery.isError ? (
              <Alert
                type="warning"
                showIcon
                message="策略展示暂不可用"
                description={formatQueryError(strategyQuery.error)}
              />
            ) : (
              <div className="macro-toolkit-empty-output">暂无策略摘要。</div>
            )}
          </section>
        </>
      ) : null}

      <section className="macro-toolkit-section">
        <PageSectionLead
          eyebrow="closure"
          title="功能补齐方案"
          description="按 V1 宏观分析 M7-M16 对齐，区分代码迁入、API/页面接线和数据命中。"
        />
        {capabilityItems.length ? (
          <Table
            rowKey="key"
            size="small"
            columns={capabilityColumns}
            dataSource={capabilityItems}
            pagination={false}
            tableLayout="fixed"
            scroll={{ x: 920 }}
          />
        ) : scriptsQuery.isFetching ? (
          <Alert
            type="info"
            showIcon
            message="功能补齐方案正在读取"
            description="不会阻塞核心信号和市场踩踏风险。"
          />
        ) : (
          <div className="macro-toolkit-empty-output">暂无功能补齐方案。</div>
        )}
      </section>

      <section className="macro-toolkit-section macro-toolkit-operations-section">
        <div className="macro-toolkit-section-headline">
          <PageSectionLead
            eyebrow="toolkit"
            title="宏观工具"
            description="迁移脚本是否已经能在系统 Choice/Tushare 数据源上直接运行？"
            style={{ marginTop: 0 }}
          />
          <Button
            icon={<ReloadOutlined />}
            onClick={() => void scriptsQuery.refetch()}
            loading={scriptsQuery.isFetching}
          >
            刷新
          </Button>
        </div>
        {scriptsQuery.isFetching && !payload ? (
          <Alert
            type="info"
            showIcon
            message="脚本注册表正在读取"
            description="脚本状态会稍后补上，核心分析已可先查看。"
          />
        ) : null}
        <div className="macro-toolkit-operations-brief">
          <MetricTile
            label="脚本就绪"
            value={`${availableScriptCount}/${scripts.length}`}
            detail="已进入宏观模块注册表"
            tone={availableScriptCount === scripts.length ? "positive" : "neutral"}
          />
          <MetricTile
            label="默认数据源"
            value={(payload?.default_data_sources ?? []).join(" + ") || "无"}
            detail="与系统口径保持一致"
          />
          <MetricTile
            label="输出文件"
            value={payload?.output_files.length ?? 0}
            detail={outputDetail}
          />
          <MetricTile
            label="源别名命中"
            value={`${sourceHitCount}/${sourceChecks.length}`}
            detail="旧代码别名到当前数据面的映射"
          />
        </div>
      </section>

      {scriptsQuery.isError ? (
        <Alert type="error" showIcon message="宏观工具加载失败" />
      ) : null}

      {payload ? (
        <DataStatusStrip className="macro-toolkit-status-strip">
          <span>读取口径：{scriptsQuery.data?.result_meta.basis}</span>
          <span>表：{scriptsQuery.data?.result_meta.tables_used?.join(" / ")}</span>
          <span>质量：{scriptsQuery.data?.result_meta.quality_flag}</span>
        </DataStatusStrip>
      ) : null}

      {payload?.warnings.length ? (
        <Alert
          type="warning"
          showIcon
          message="仍有未落库的数据面"
          description={payload.warnings.join(" ")}
        />
      ) : null}

      <section className="macro-toolkit-section">
        <PageSectionLead
          eyebrow="cffex"
          title="CFFEX席位状态"
          description="crowding_cn 等脚本依赖的中金所席位排名读面。"
        />
        <div className="macro-toolkit-cffex-panel">
          <div className="macro-toolkit-cffex-metrics">
            <MetricTile
              label="席位行数"
              value={cffexStatus?.row_count ?? 0}
              detail={cffexStatus?.status ?? "未读取"}
            />
            <MetricTile
              label="最新交易日"
              value={cffexStatus?.latest_trade_date ?? "缺失"}
              detail={`对齐 ${cffexStatus?.reference_date ?? analysis?.as_of_date ?? "待定"}`}
            />
            <MetricTile
              label="新鲜度"
              value={statusLabel(cffexStatus?.freshness_status ?? "unknown")}
              detail={
                cffexStatus?.stale_days == null
                  ? "待确认"
                  : `落后 ${cffexStatus.stale_days} 天`
              }
            />
          </div>
          <div className="macro-toolkit-cffex-actions">
            <Button
              icon={<ReloadOutlined />}
              loading={isRefreshingCffex}
              onClick={() => void refreshCffexMemberRank()}
            >
              刷新席位
            </Button>
            {refreshResult ? <Alert type="success" showIcon message={refreshResult} /> : null}
            {refreshError ? <Alert type="error" showIcon message={refreshError} /> : null}
          </div>
        </div>
      </section>

      <section className="macro-toolkit-section">
        <PageSectionLead
          eyebrow="outputs"
          title="脚本产物"
          description="运行脚本后自动刷新这里，便于确认 CSV、图片或报告是否生成。"
        />
        {payload?.output_files.length ? (
          <Table
            rowKey="path"
            size="small"
            columns={outputColumns}
            dataSource={payload.output_files}
            pagination={false}
          />
        ) : (
          <div className="macro-toolkit-empty-output">尚未发现输出文件。</div>
        )}
      </section>

      <section className="macro-toolkit-section">
        <PageSectionLead
          eyebrow="source"
          title="系统数据源命中"
          description="这些旧代码别名已经映射到当前系统的 Choice/Tushare 数据面。"
        />
        <div className="macro-toolkit-source-grid">
          {sourceChecks.map((check) => (
            <div className="macro-toolkit-source-item" key={check.alias}>
              <span>{check.alias}</span>
              <strong>{check.row_count}</strong>
              <small>{formatSourceCheck(check)}</small>
            </div>
          ))}
        </div>
      </section>

      {omittedEntries.length ? (
        <section className="macro-toolkit-section">
          <PageSectionLead
            eyebrow="omitted"
            title="未纳入脚本"
            description="这些源文件保留为迁移证据，但暂不作为可执行宏观工作流。"
          />
          <div className="macro-toolkit-omitted-list">
            {omittedEntries.map(([filename, reason]) => (
              <div className="macro-toolkit-omitted-item" key={filename}>
                <span>{filename}</span>
                <small>{reason}</small>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="macro-toolkit-section">
        <PageSectionLead
          eyebrow="scripts"
          title="脚本注册表"
          description="脚本从原 macro_toolkit 聚合到后端宏观模块，前端通过注册表展示。"
        />
        <div className="macro-toolkit-toolbar">
          <Select
            value={selectedGroup}
            options={groupOptions}
            onChange={(value) => {
              setSelectedGroup(value);
              setSelectedName(null);
            }}
          />
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            disabled={!selectedScript}
            loading={isRunning}
            onClick={() => void runSelectedScript()}
          >
            运行选中脚本
          </Button>
        </div>
        <Table
          rowKey="name"
          size="small"
          columns={scriptColumns}
          dataSource={filteredScripts}
          pagination={{ pageSize: 8, showSizeChanger: false }}
          rowClassName={(script) =>
            script.name === selectedScript?.name ? "macro-toolkit-row--selected" : ""
          }
          onRow={(script) => ({
            onClick: () => setSelectedName(script.name),
          })}
        />
      </section>

      <section className="macro-toolkit-section">
        <PageSectionLead
          eyebrow="run"
          title="运行结果"
          description={selectedScript ? selectedScript.name : "暂无选中脚本"}
        />
        <div className="macro-toolkit-run-panel">
          <div className="macro-toolkit-run-title">
            <ToolOutlined />
            <span>{selectedScript?.filename ?? "未选择"}</span>
          </div>
          {runError ? <Alert type="error" showIcon message={runError} /> : null}
          {runResult ? (
            <Alert
              type={statusTone(runResult.status)}
              showIcon
              message={`状态：${runResult.status}`}
              description={`退出码：${runResult.exit_code ?? "无"} · 输出文件：${runResult.output_files.length}`}
            />
          ) : null}
          <pre className="macro-toolkit-console">
            {runResult?.stdout || runResult?.stderr || "尚未运行。"}
          </pre>
        </div>
      </section>
    </div>
  );
}

function CapabilityResultCard({ result }: { result: MacroToolkitCapabilityResult }) {
  const metric = result.primary_metric;
  const evidence = result.evidence.length ? result.evidence : result.warnings;
  const inputEvidence = normalizeInputEvidence(result);
  return (
    <div
      className={`macro-toolkit-capability-result macro-toolkit-capability-result--${result.tone}`}
      style={scoreStyle(result.score)}
    >
      <div className="macro-toolkit-capability-result-head">
        <span>
          {result.legacy_module} · {result.label}
        </span>
        <Tag color={statusColor(result.status)}>{statusLabel(result.status)}</Tag>
      </div>
      <strong>{metric ? formatMetricDisplay(metric) : result.score ?? statusLabel(result.status)}</strong>
      <div className="macro-toolkit-score-track" aria-hidden="true">
        <span />
      </div>
      <p>{result.headline}</p>
      <small>{evidence.slice(0, 3).join(" / ") || "暂无证据"}</small>
      {inputEvidence ? (
        <div className="macro-toolkit-input-evidence">
          {inputEvidence.missingInputs.length ? (
            <span>缺失输入：{inputEvidence.missingInputs.join(" / ")}</span>
          ) : null}
          {inputEvidence.sources.length ? <span>数据源：{inputEvidence.sources.join(" / ")}</span> : null}
          {inputEvidence.latestDates.length ? <span>最新日期：{inputEvidence.latestDates.join(" / ")}</span> : null}
          {inputEvidence.inputs.length ? (
            <small>
              {inputEvidence.inputs
                .slice(0, 3)
                .map((item) => `${item.label || item.field}: ${item.series_id ?? "缺失"} ${item.latest_date ?? ""}`.trim())
                .join(" / ")}
            </small>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function ReadinessTile({
  icon,
  label,
  value,
  detail,
  tone = "neutral",
}: {
  icon?: ReactNode;
  label: string;
  value: string;
  detail: string;
  tone?: MacroToolkitSignalCard["tone"];
}) {
  const Icon = tone === "negative" || tone === "missing" ? ExclamationCircleOutlined : CheckCircleOutlined;
  return (
    <div className={`macro-toolkit-readiness-tile macro-toolkit-readiness-tile--${tone}`}>
      <span>
        <MacroStatusIcon tone={tone}>{icon ?? <Icon />}</MacroStatusIcon>
        {label}
      </span>
      <strong>{value}</strong>
      <small title={detail}>{compactText(detail, 28)}</small>
    </div>
  );
}

function TailwindMetricTile({
  icon,
  label,
  value,
  detail,
}: {
  icon: ReactNode;
  label: string;
  value: string | number;
  detail: string;
}) {
  return (
    <div className="min-w-0 rounded-lg border border-blue-100 bg-white p-3 shadow-sm shadow-blue-100/60">
      <div className="flex min-w-0 items-center gap-2 text-xs font-bold text-slate-600">
        <span className="grid h-6 w-6 place-items-center rounded-md border border-blue-100 bg-blue-50 text-blue-600">
          {icon}
        </span>
        <span className="truncate">{label}</span>
      </div>
      <strong className="mt-2 block truncate font-mono text-xl text-blue-950">{value}</strong>
      <small className="block truncate text-xs text-slate-500" title={detail}>
        {detail}
      </small>
    </div>
  );
}

function IndicatorValueCell({ item }: { item: MacroToolkitIndicator }) {
  return (
    <div className="macro-toolkit-number-cell">
      <strong>{formatValue(item.latest_value, item.unit)}</strong>
      <small>{item.row_count.toLocaleString()} rows</small>
    </div>
  );
}

function DeltaCell({ change, changePct }: { change: number | null; changePct: number | null }) {
  const direction = changePct ?? change;
  const hasDirection = direction !== null;
  const isPositive = hasDirection && direction > 0;
  const isNegative = hasDirection && direction < 0;

  return (
    <div
      className={[
        "macro-toolkit-delta-cell",
        isPositive ? "macro-toolkit-delta-cell--up" : "",
        isNegative ? "macro-toolkit-delta-cell--down" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {isPositive ? <ArrowUpOutlined /> : null}
      {isNegative ? <ArrowDownOutlined /> : null}
      <span>{formatChange(change, changePct)}</span>
    </div>
  );
}

function CapabilityDataCell({
  status,
  item,
}: {
  status: string;
  item: MacroToolkitCapability;
}) {
  const ratio = item.data_required_count > 0 ? item.data_hit_count / item.data_required_count : 1;
  return (
    <div className="macro-toolkit-capability-data-cell" style={scoreStyle(ratio * 100)}>
      <div>
        <Tag color={statusColor(status)}>{statusLabel(status)}</Tag>
        <span>
          {item.data_hit_count}/{item.data_required_count}
        </span>
      </div>
      <div className="macro-toolkit-score-track" aria-hidden="true">
        <span />
      </div>
    </div>
  );
}

function normalizeInputEvidence(result: MacroToolkitCapabilityResult) {
  const raw = result.input_evidence ?? result.result.input_evidence;
  if (!raw) {
    return null;
  }
  const inputs = raw.inputs ?? [];
  const missingInputs = raw.missing_inputs ?? [];
  const sources = raw.sources ?? [];
  const latestDates = raw.latest_dates ?? [];
  if (!inputs.length && !missingInputs.length && !sources.length && !latestDates.length) {
    return null;
  }
  return { inputs, missingInputs, sources, latestDates };
}

function hasRealStrategySource(strategy: MacroToolkitStrategySummary) {
  return (
    strategy.result.price_source === "choice_stock_daily_observation" ||
    strategy.result.factor_source === "choice_stock_factor_snapshot"
  );
}

function hasCompleteRealStrategyChain(strategy: MacroToolkitStrategySummary) {
  if (strategy.status !== "complete" || strategyDataStatus(strategy) !== "complete") {
    return false;
  }
  const hasPriceSource = strategy.result.price_source === "choice_stock_daily_observation";
  const hasFactorSource = strategy.result.factor_source === "choice_stock_factor_snapshot";
  if (strategy.key === "multi_factor_selection") {
    return hasFactorSource;
  }
  if (strategy.key === "low_crowding_regime_multifactor") {
    return hasPriceSource && hasFactorSource;
  }
  return hasPriceSource;
}

function strategyDataStatus(strategy: MacroToolkitStrategySummary) {
  return typeof strategy.result.data_status === "string" && strategy.result.data_status.trim()
    ? strategy.result.data_status.trim()
    : strategy.status;
}

function choiceStockTableDetail(
  table: { row_count?: number; latest_trade_date?: string | null; as_of_date?: string | null; freshness_status?: string; fallback_mode?: string | null; fallback_date?: string | null } | null | undefined,
  dateField: "latest_trade_date" | "as_of_date",
) {
  return `行数 ${table?.row_count ?? 0} · ${choiceStockTableSummary(table, dateField)}`;
}

function choiceStockTableSummary(
  table: { latest_trade_date?: string | null; as_of_date?: string | null; freshness_status?: string; fallback_mode?: string | null; fallback_date?: string | null } | null | undefined,
  dateField: "latest_trade_date" | "as_of_date",
) {
  const dateText = table?.[dateField] ?? "缺失";
  const statusText = statusLabel(table?.freshness_status ?? "unknown");
  const fallbackText = choiceStockFallbackText(table);
  return [dateText, statusText, fallbackText].filter(Boolean).join(" · ");
}

function choiceStockFallbackText(
  table: { fallback_mode?: string | null; fallback_date?: string | null } | null | undefined,
) {
  if (table?.fallback_mode !== "latest_available" || !table.fallback_date) {
    return "";
  }
  return `最近可用 ${table.fallback_date}`;
}

function formatSignedRatio(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) {
    return "缺失";
  }
  const percent = value * 100;
  return `${percent >= 0 ? "+" : ""}${percent.toFixed(1)}%`;
}

function formatPlainRatio(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) {
    return "缺失";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function formatNumberValue(value: number | null | undefined, digits = 1) {
  if (value == null || !Number.isFinite(value)) {
    return "缺失";
  }
  return value.toFixed(digits);
}

function portfolioConstraintText(portfolio: MacroToolkitShadowPortfolio) {
  const constraints = portfolio.constraints;
  const parts = [
    constraints.pe_max == null ? "" : `PE≤${constraints.pe_max}`,
    constraints.pb_max == null ? "" : `PB≤${constraints.pb_max}`,
    constraints.turnover_cap == null ? "" : `换手≤${Math.round(constraints.turnover_cap * 100)}%`,
  ].filter(Boolean);
  return parts.length ? parts.join(" / ") : "沿用正式规则约束";
}

function portfolioWeightsText(portfolio: MacroToolkitShadowPortfolio) {
  const labels: Record<string, string> = {
    value: "价值",
    quality: "质量",
    momentum: "动量",
    low_vol: "低波",
    dividend: "红利",
  };
  return Object.entries(portfolio.weights)
    .map(([key, value]) => `${labels[key] ?? key}${Math.round(value * 100)}%`)
    .join(" / ");
}

function costResultText(portfolio: MacroToolkitShadowPortfolio, costBps: number) {
  const result = portfolio.cost_results.find((item) => item.cost_bps === costBps);
  if (!result) {
    return `${costBps}bp 缺失`;
  }
  return `${costBps}bp ${formatSignedRatio(result.total_return)} / 超额 ${formatSignedRatio(result.excess_return)}`;
}

function portfolioCostResult(portfolio: MacroToolkitShadowPortfolio, costBps: number) {
  return portfolio.cost_results.find((item) => item.cost_bps === costBps);
}

function shadowPortfolioPeriodRows(
  report: MacroToolkitShadowPortfolioReport,
  portfolio: MacroToolkitShadowPortfolio,
) {
  return report.period_returns.filter((row) => row.portfolio_key === portfolio.key);
}

function shadowPortfolioPeriodWinLossText(rows: MacroToolkitShadowPortfolioPeriodReturn[]) {
  if (!rows.length) {
    return "周期缺失";
  }
  const wins = rows.filter((row) => row.excess_return > 0).length;
  return `${wins}赢 / ${rows.length - wins}输`;
}

function shadowPortfolioPeriodRangeText(rows: MacroToolkitShadowPortfolioPeriodReturn[]) {
  if (!rows.length) {
    return "最佳缺失 / 最差缺失";
  }
  const best = rows.reduce((winner, row) => (row.excess_return > winner.excess_return ? row : winner), rows[0]!);
  const worst = rows.reduce((loser, row) => (row.excess_return < loser.excess_return ? row : loser), rows[0]!);
  return `最佳 ${formatSignedRatio(best.excess_return)} / 最差 ${formatSignedRatio(worst.excess_return)}`;
}

function shadowPortfolioCostGateText(
  reference: MacroToolkitShadowPortfolio,
  candidate: MacroToolkitShadowPortfolio,
) {
  const passingCosts = [20, 50].filter((costBps) => {
    const referenceCost = portfolioCostResult(reference, costBps);
    const candidateCost = portfolioCostResult(candidate, costBps);
    return (
      referenceCost != null &&
      candidateCost != null &&
      candidateCost.total_return > referenceCost.total_return &&
      candidateCost.excess_return > referenceCost.excess_return
    );
  });
  if (passingCosts.length === 2) {
    return "20bp/50bp 均胜出";
  }
  if (passingCosts.length) {
    return `${passingCosts.join("bp / ")}bp 胜出`;
  }
  return "成本后未胜出";
}

function holdingCodeList(holdings: MacroToolkitShadowPortfolioHolding[]) {
  return holdings.slice(0, 3).map((holding) => holding.stock_code).join(" / ") || "无";
}

function shadowPortfolioHoldingDiff(
  reference: MacroToolkitShadowPortfolio,
  candidate: MacroToolkitShadowPortfolio,
) {
  const referenceCodes = new Set(reference.latest_holdings.map((holding) => holding.stock_code));
  const candidateCodes = new Set(candidate.latest_holdings.map((holding) => holding.stock_code));
  const overlap = candidate.latest_holdings.filter((holding) => referenceCodes.has(holding.stock_code));
  const candidateOnly = candidate.latest_holdings.filter((holding) => !referenceCodes.has(holding.stock_code));
  const referenceOnly = reference.latest_holdings.filter((holding) => !candidateCodes.has(holding.stock_code));
  return {
    overlapText: `持仓重合 ${overlap.length}/${Math.max(candidate.latest_holdings.length, 1)}`,
    candidateOnlyText: `新增观察 ${holdingCodeList(candidateOnly)}`,
    referenceOnlyText: `正式独有 ${holdingCodeList(referenceOnly)}`,
  };
}

function periodChipText(row: MacroToolkitShadowPortfolioPeriodReturn) {
  return `${row.start_date.slice(5)}→${row.end_date.slice(5)} ${formatSignedRatio(row.excess_return)}`;
}

function shadowPortfolioWarningText(warning: string) {
  if (warning === "DUCKDB_BUSY") {
    return "本地股票历史库正在刷新或被落库任务占用，稍后刷新页面即可重试。";
  }
  if (warning.startsWith("DUCKDB_OPEN_FAILED")) {
    return "DuckDB 读连接打开失败，暂时不能生成影子组合回测。";
  }
  if (warning === "DUCKDB_NOT_FOUND") {
    return "本地股票历史库不存在，暂时不能生成影子组合回测。";
  }
  if (warning.startsWith("MISSING_TABLES")) {
    return "本地股票历史表或因子快照表缺失，暂时不能生成影子组合回测。";
  }
  if (warning === "FACTOR_HISTORY_TOO_SHORT" || warning === "SHORT_HISTORY") {
    return "因子快照历史偏短，当前结果只能作为只读观察。";
  }
  if (warning === "READ_ONLY_SHADOW_NOT_PRODUCTION") {
    return "只读影子评估，不能作为正式投研信号。";
  }
  return warning;
}

function shadowPortfolioUnavailableDescription(warnings: readonly string[]) {
  const visibleWarnings = Array.from(new Set(warnings.map(shadowPortfolioWarningText).filter(Boolean)));
  return visibleWarnings.join(" / ") || "本地股票历史或因子快照不足。";
}

function ShadowPortfolioReview({ report }: { report: MacroToolkitShadowPortfolioReport }) {
  const reference =
    report.portfolios.find((portfolio) => portfolio.role === "production_reference") ?? report.portfolios[0];
  const candidates = report.portfolios.filter((portfolio) => portfolio.role === "shadow_candidate");
  if (!reference || !candidates.length) {
    return null;
  }
  return (
    <div className="macro-toolkit-shadow-review" aria-label="影子组合稳健性审查">
      {candidates.map((candidate) => {
        const rows = shadowPortfolioPeriodRows(report, candidate);
        const holdingDiff = shadowPortfolioHoldingDiff(reference, candidate);
        return (
          <div className="macro-toolkit-shadow-review__item" key={`review-${candidate.key}`}>
            <div className="macro-toolkit-capability-result-head">
              <span>稳健性审查</span>
              <Tag color="blue">{candidate.label}</Tag>
            </div>
            <div className="macro-toolkit-shadow-review__facts">
              <span>
                <b>周期胜负</b>
                {shadowPortfolioPeriodWinLossText(rows)}
              </span>
              <span>
                <b>区间分布</b>
                {shadowPortfolioPeriodRangeText(rows)}
              </span>
              <span>
                <b>成本后结论</b>
                {shadowPortfolioCostGateText(reference, candidate)}
              </span>
              <span>
                <b>持仓差异</b>
                {holdingDiff.overlapText}
              </span>
            </div>
            {rows.length ? (
              <div className="macro-toolkit-shadow-review__periods">
                {rows.slice(-4).map((row) => (
                  <span key={`${candidate.key}-${row.start_date}-${row.end_date}`}>{periodChipText(row)}</span>
                ))}
              </div>
            ) : null}
            <div className="macro-toolkit-shadow-holdings macro-toolkit-shadow-holdings--diff">
              <span>{holdingDiff.candidateOnlyText}</span>
              <span>{holdingDiff.referenceOnlyText}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ShadowPortfolioReportPanel({ report }: { report: MacroToolkitShadowPortfolioReport | null }) {
  if (!report) {
    return null;
  }
  if (report.status !== "complete") {
    return (
      <div className="macro-toolkit-shadow-report macro-toolkit-shadow-report--warning" aria-label="影子组合报告">
        <Alert
          type="warning"
          showIcon
          message="影子组合报告暂不可用"
          description={shadowPortfolioUnavailableDescription(report.warnings)}
        />
        {report.warnings.length ? (
          <div className="macro-toolkit-tag-row">
            {report.warnings.map((warning) => (
              <Tag color="gold" key={warning}>
                {warning}
              </Tag>
            ))}
          </div>
        ) : null}
      </div>
    );
  }
  return (
    <div className="macro-toolkit-shadow-report" aria-label="影子组合报告">
      <div className="macro-toolkit-shadow-report__head">
        <div>
          <span>只读影子组合</span>
          <strong>{report.as_of_date ?? "日期缺失"}</strong>
          <small>
            {report.completed_periods} 个完成调仓周期 / {report.benchmark?.label ?? "基准缺失"}
          </small>
        </div>
        <div className="macro-toolkit-tag-row">
          <Tag color="blue">{report.rule_version}</Tag>
          {report.warnings.map((warning) => (
            <Tag color="gold" key={warning}>
              {warning}
            </Tag>
          ))}
        </div>
      </div>
      <div className="macro-toolkit-shadow-report__grid">
        {report.portfolios.map((portfolio) => (
          <div className="macro-toolkit-shadow-card" key={portfolio.key}>
            <div className="macro-toolkit-capability-result-head">
              <span>{portfolio.role === "shadow_candidate" ? "影子观察" : "正式参照"}</span>
              <Tag color={portfolio.role === "shadow_candidate" ? "blue" : "default"}>{portfolio.label}</Tag>
            </div>
            <div className="macro-toolkit-shadow-card__metrics">
              <MetricTile label="总收益" value={formatSignedRatio(portfolio.total_return)} detail="不含生产替换" />
              <MetricTile label="超额" value={formatSignedRatio(portfolio.excess_return)} detail="相对因子池等权" />
              <MetricTile label="最大回撤" value={formatSignedRatio(portfolio.max_drawdown)} detail={`胜率 ${formatPlainRatio(portfolio.win_rate)}`} />
              <MetricTile label="估值" value={`PE ${formatNumberValue(portfolio.average_pe)}`} detail={`PB ${formatNumberValue(portfolio.average_pb)}`} />
            </div>
            <div className="macro-toolkit-strategy-trace">
              <span>
                <b>权重</b>
                {portfolioWeightsText(portfolio)}
              </span>
              <span>
                <b>约束</b>
                {portfolioConstraintText(portfolio)}
              </span>
              <span>
                <b>换手</b>
                {formatPlainRatio(portfolio.average_turnover)}
              </span>
              <span>
                <b>20bp</b>
                {costResultText(portfolio, 20)}
              </span>
              <span>
                <b>50bp</b>
                {costResultText(portfolio, 50)}
              </span>
            </div>
            {portfolio.latest_holdings.length ? (
              <div className="macro-toolkit-shadow-holdings">
                {portfolio.latest_holdings.slice(0, 5).map((holding) => (
                  <span key={`${portfolio.key}-${holding.stock_code}`}>
                    {holding.rank}. {holding.stock_code} · {holding.industry}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>
      <ShadowPortfolioReview report={report} />
    </div>
  );
}

function StrategySummaryCard({ strategy }: { strategy: MacroToolkitStrategySummary }) {
  const metric = strategy.primary_metric;
  const dataStatus = strategyDataStatus(strategy);
  const priceSource =
    typeof strategy.result.price_source === "string" && strategy.result.price_source.trim()
      ? strategy.result.price_source
      : "价格来源缺失";
  const factorSource =
    typeof strategy.result.factor_source === "string" && strategy.result.factor_source.trim()
      ? strategy.result.factor_source
      : "因子来源缺失";
  const warnings = strategy.warnings;
  const sourceVersions = strategyTraceList(strategy.result.source_versions);
  const vendorVersions = strategyTraceList(strategy.result.vendor_versions);
  const factorSourceVersions = strategyTraceList(strategy.result.factor_source_versions);
  const factorVendorVersions = strategyTraceList(strategy.result.factor_vendor_versions);
  const factorRuleVersions = strategyTraceList(strategy.result.factor_rule_versions);
  const factorRunIds = strategyTraceList(strategy.result.factor_run_ids);
  const missingFactorInputs = strategyTraceList(strategy.result.missing_factor_inputs, Number.POSITIVE_INFINITY);
  const asOfDate = strategyScalarText(strategy.result.as_of_date);
  const factorAsOfDate = strategyScalarText(strategy.result.factor_as_of_date);
  const factorDateStatus = strategyScalarText(strategy.result.factor_date_status);

  return (
    <div className={`macro-toolkit-strategy-card macro-toolkit-strategy-card--${strategy.tone}`}>
      <div className="macro-toolkit-capability-result-head">
        <span>{strategy.group}</span>
        <Tag color={statusColor(strategy.status)}>{statusLabel(strategy.status)}</Tag>
      </div>
      <strong>{strategy.label}</strong>
      <div className="macro-toolkit-strategy-metric">
        <span>{metric?.label ?? "状态"}</span>
        <b>{metric ? `${metric.value}${metric.unit}` : statusLabel(strategy.status)}</b>
      </div>
      <small>{strategy.evidence.slice(0, 2).join(" / ") || "暂无证据"}</small>
      <div className="macro-toolkit-strategy-trace" aria-label={`${strategy.label}策略追踪`}>
        <span>
          <b>数据状态</b>
          {statusLabel(dataStatus)} <em>{dataStatus}</em>
        </span>
        <span>
          <b>价格</b>
          {priceSource}
        </span>
        <span>
          <b>因子</b>
          {factorSource}
        </span>
        {asOfDate ? (
          <span>
            <b>行情日</b>
            {asOfDate}
          </span>
        ) : null}
        {factorAsOfDate ? (
          <span>
            <b>因子日</b>
            {factorAsOfDate}
            {factorDateStatus ? ` · ${statusLabel(factorDateStatus)}` : ""}
          </span>
        ) : null}
        {sourceVersions ? (
          <span>
            <b>价格版本</b>
            {sourceVersions}
          </span>
        ) : null}
        {vendorVersions ? (
          <span>
            <b>行情厂商</b>
            {vendorVersions}
          </span>
        ) : null}
        {factorSourceVersions ? (
          <span>
            <b>因子版本</b>
            {factorSourceVersions}
          </span>
        ) : null}
        {factorVendorVersions ? (
          <span>
            <b>因子厂商</b>
            {factorVendorVersions}
          </span>
        ) : null}
        {factorRuleVersions ? (
          <span>
            <b>因子规则</b>
            {factorRuleVersions}
          </span>
        ) : null}
        {factorRunIds ? (
          <span>
            <b>因子运行</b>
            {factorRunIds}
          </span>
        ) : null}
        {missingFactorInputs ? (
          <span>
            <b>缺失输入</b>
            {missingFactorInputs}
          </span>
        ) : null}
        {warnings.length ? (
          <div className="macro-toolkit-strategy-warnings">
            {warnings.map((warning) => (
              <Tag color="gold" key={warning}>
                {warning}
              </Tag>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function strategyTraceList(value: unknown, maxItems = 3) {
  if (!Array.isArray(value)) {
    return "";
  }
  const items = value
    .map((item) => String(item ?? "").trim())
    .filter(Boolean);
  return (Number.isFinite(maxItems) ? items.slice(0, maxItems) : items).join(" / ");
}

function strategyScalarText(value: unknown) {
  if (typeof value !== "string" && typeof value !== "number") {
    return "";
  }
  return String(value).trim();
}

const A_SHARE_RISK_METRICS: Array<{
  key: string;
  label: string;
  format?: "percent" | "ratio";
}> = [
  { key: "up_count", label: "上涨家数" },
  { key: "up_ratio", label: "上涨比例", format: "percent" },
  { key: "drop_3_count", label: "跌超3%" },
  { key: "drop_5_count", label: "跌超5%" },
  { key: "limit_down_count", label: "跌停家数" },
  { key: "near_down_count", label: "近跌停" },
  { key: "turnover_ratio_ma20", label: "成交额/20日", format: "ratio" },
  { key: "index_drawdown_from_high", label: "回落幅度", format: "percent" },
];

function AShareRiskPanel({ risk }: { risk?: MacroToolkitAShareRiskPayload }) {
  if (!risk) {
    return (
      <div className="macro-toolkit-empty-output">
        市场踩踏风险数据未返回，当前不能形成风险等级判断。
      </div>
    );
  }
  const tone = riskLevelTone(risk.risk_level);
  const scoreText = risk.risk_score === null ? "缺失" : risk.risk_score;
  return (
    <div className={`macro-toolkit-a-share-risk macro-toolkit-a-share-risk--${tone}`}>
      <div className="macro-toolkit-a-share-risk__summary" style={scoreStyle(risk.risk_score)}>
        <div className="macro-toolkit-capability-result-head">
          <span>
            <MacroStatusIcon tone={tone}>
              {tone === "negative" ? <WarningOutlined /> : <ClockCircleOutlined />}
            </MacroStatusIcon>
            {risk.trade_date ?? "日期缺失"}
          </span>
          <div className="macro-toolkit-tag-row">
            <Tag color={statusColor(risk.status)}>{statusLabel(risk.status)}</Tag>
            <Tag color={riskLevelColor(risk.risk_level)}>{risk.risk_name}</Tag>
          </div>
        </div>
        <strong>{scoreText}</strong>
        <div className="macro-toolkit-score-track" aria-hidden="true">
          <span />
        </div>
        <p title={risk.summary}>{compactText(risk.summary || "风险摘要缺失。", 38)}</p>
        <small title={risk.position_rule}>{compactText(risk.position_rule || "仓位规则缺失，不能据此放大仓位。", 30)}</small>
      </div>

      <div className="macro-toolkit-a-share-risk__metrics">
        {A_SHARE_RISK_METRICS.map((metric) => (
          <div className="macro-toolkit-strategy-metric" key={metric.key}>
            <span>{metric.label}</span>
            <b>{formatRiskMetric(risk.metrics[metric.key], metric.format)}</b>
          </div>
        ))}
      </div>

      <div className="macro-toolkit-a-share-risk__lists">
        <RiskList title="触发规则" items={risk.triggered_rules} emptyText="未触发明确踩踏规则。" />
        <RiskList title="观察条件" items={risk.watch_next} emptyText="暂无下一步观察条件。" />
        <RiskList title="数据提示" items={risk.warnings} emptyText={risk.status === "complete" ? "数据能力完整。" : "降级原因缺失。"} />
      </div>
    </div>
  );
}

function RiskList({ title, items, emptyText }: { title: string; items: string[]; emptyText: string }) {
  const visibleItems = items.length ? items : [emptyText];
  return (
    <div className="macro-toolkit-a-share-risk__list">
      <span>{title}</span>
      {visibleItems.slice(0, 4).map((item) => (
        <small key={item} title={item}>
          {compactText(item, 26)}
        </small>
      ))}
    </div>
  );
}

function formatRiskMetric(value: number | null | undefined, format?: "percent" | "ratio") {
  if (value == null) {
    return "缺失";
  }
  if (format === "percent") {
    return `${(value * 100).toFixed(1)}%`;
  }
  if (format === "ratio") {
    return `${value.toFixed(2)}x`;
  }
  return Number.isInteger(value) ? value.toString() : value.toFixed(2);
}

function formatMetricDisplay(metric: NonNullable<MacroToolkitCapabilityResult["primary_metric"]>) {
  return `${metric.label} ${metric.value}${metric.unit}`;
}

function MetricTile({
  icon,
  label,
  value,
  detail,
  tone = "neutral",
}: {
  icon?: ReactNode;
  label: string;
  value: string | number;
  detail: string;
  tone?: "neutral" | "positive";
}) {
  return (
    <div className={`macro-toolkit-metric macro-toolkit-metric--${tone}`}>
      <span>
        <MacroStatusIcon tone={tone}>{icon ?? <InfoCircleOutlined />}</MacroStatusIcon>
        {label}
      </span>
      <strong>{value}</strong>
      <small title={detail}>{compactText(detail, 26)}</small>
    </div>
  );
}
