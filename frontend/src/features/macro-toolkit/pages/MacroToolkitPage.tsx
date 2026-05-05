import { useCallback, useEffect, useMemo, useState } from "react";
import { PlayCircleOutlined, ReloadOutlined, ToolOutlined } from "@ant-design/icons";
import { Alert, Button, Select, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type {
  MacroToolkitCapability,
  MacroToolkitIndicator,
  MacroToolkitOutputFile,
  MacroToolkitRunResponse,
  MacroToolkitScriptRecord,
  MacroToolkitSignalCard,
  MacroToolkitSourceCheck,
} from "../../../api/macroToolkitClient";
import {
  DataStatusStrip,
  PageDecisionHero,
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
    library_ready: "函数已迁入",
    not_wired: "未接线",
    planned: "待接入",
  };
  return labels[status] ?? status;
}

function statusColor(status: string) {
  if (["current", "ready", "library_ready"].includes(status)) return "green";
  if (["lagging", "partial", "planned"].includes(status)) return "gold";
  if (["stale", "missing", "not_wired"].includes(status)) return "red";
  return "default";
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

export default function MacroToolkitPage() {
  const client = useApiClient();
  const [selectedGroup, setSelectedGroup] = useState("all");
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<MacroToolkitRunResponse | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [refreshResult, setRefreshResult] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [isRefreshingCffex, setIsRefreshingCffex] = useState(false);
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

  const payload = scriptsQuery.data?.result;
  const analysis = analysisQuery.data?.result;
  const scripts = payload?.scripts ?? EMPTY_SCRIPTS;
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
  const omittedEntries = Object.entries(payload?.omitted_scripts ?? {});

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
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch()]);
    } catch (error) {
      setRunError(error instanceof Error ? error.message : "运行失败");
    } finally {
      setIsRunning(false);
    }
  }, [analysisQuery, client, scriptsQuery, selectedScript]);

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
      await Promise.all([scriptsQuery.refetch(), analysisQuery.refetch()]);
    } catch (error) {
      setRefreshError(error instanceof Error ? error.message : "刷新席位失败");
    } finally {
      setIsRefreshingCffex(false);
    }
  }, [analysis?.as_of_date, client, scriptsQuery, analysisQuery]);

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
      render: (_, item) => formatValue(item.latest_value, item.unit),
    },
    {
      title: "变化",
      dataIndex: "change_pct",
      key: "change_pct",
      width: 110,
      render: (_, item) => formatChange(item.change, item.change_pct),
    },
    {
      title: "日期",
      dataIndex: "latest_date",
      key: "latest_date",
      width: 120,
      render: (date: string | null) => date ?? "缺失",
    },
    {
      title: "来源",
      dataIndex: "source",
      key: "source",
      width: 120,
      render: (source: string | null) => source ?? "未命中",
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
      render: (status: string, item) => (
        <span>
          <Tag color={statusColor(status)}>{statusLabel(status)}</Tag>
          {item.data_hit_count}/{item.data_required_count}
        </span>
      ),
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

  if (scriptsQuery.isLoading || analysisQuery.isLoading) {
    return (
      <PageStateSurface
        variant="loading"
        title="正在读取宏观工具"
        description="正在从后端宏观模块读取脚本注册表。"
      />
    );
  }

  return (
    <div className="macro-toolkit-page">
      <PageDecisionHero
        title="宏观分析结果"
        eyebrow="宏观模块"
        businessQuestion="当前 Choice/Tushare 数据给出的宏观环境判断是什么？"
        actions={
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              void analysisQuery.refetch();
              void scriptsQuery.refetch();
            }}
            loading={analysisQuery.isFetching || scriptsQuery.isFetching}
          >
            刷新结果
          </Button>
        }
        conclusion={
          <div className="macro-toolkit-analysis-hero">
            <div className="macro-toolkit-stance-card">
              <span>当前结论</span>
              <strong>{analysis?.conclusion.stance ?? "读取中"}</strong>
              <small>{analysis?.conclusion.summary ?? "正在从系统数据源生成宏观判断。"}</small>
            </div>
            <MetricTile
              label="数据命中"
              value={`${analysis?.coverage.hit_count ?? 0}/${analysis?.coverage.indicator_count ?? 0}`}
              detail={`命中率 ${(((analysis?.coverage.hit_rate ?? 0) * 100)).toFixed(1)}%`}
            />
            <MetricTile
              label="分析日期"
              value={analysis?.as_of_date ?? "缺失"}
              detail={(analysis?.default_data_sources ?? []).join(" + ") || "choice + tushare"}
            />
          </div>
        }
      />

      {analysisQuery.isError ? (
        <Alert type="error" showIcon message="宏观分析结果加载失败" />
      ) : null}

      {analysis ? (
        <>
          <DataStatusStrip className="macro-toolkit-status-strip">
            <span>读取口径：{analysisQuery.data?.result_meta.basis}</span>
            <span>质量：{analysisQuery.data?.result_meta.quality_flag}</span>
            <span>建议：{analysis.conclusion.recommended_action}</span>
          </DataStatusStrip>

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
                >
                  <div className="macro-toolkit-signal-head">
                    <span>{card.title}</span>
                    <Tag color={toneTagColor(card.tone)}>{card.stance}</Tag>
                  </div>
                  <strong>{card.score === null ? "缺失" : card.score}</strong>
                  <small>{card.evidence.join(" / ")}</small>
                </div>
              ))}
            </div>
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
            />
          </section>
        </>
      ) : null}

      <section className="macro-toolkit-section">
        <PageSectionLead
          eyebrow="closure"
          title="功能补齐方案"
          description="按 V1 宏观分析 M7-M16 对齐，区分代码迁入、API/页面接线和数据命中。"
        />
        <Table
          rowKey="key"
          size="small"
          columns={capabilityColumns}
          dataSource={payload?.capabilities ?? analysis?.capabilities ?? []}
          pagination={false}
        />
      </section>

      <PageDecisionHero
        title="宏观工具"
        eyebrow="宏观模块"
        businessQuestion="迁移脚本是否已经能在系统 Choice/Tushare 数据源上直接运行？"
        actions={
          <Button
            icon={<ReloadOutlined />}
            onClick={() => void scriptsQuery.refetch()}
            loading={scriptsQuery.isFetching}
          >
            刷新
          </Button>
        }
        conclusion={
          <div className="macro-toolkit-hero-grid">
            <MetricTile label="脚本" value={scripts.length} detail="已进入宏观模块注册表" />
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
          </div>
        }
      />

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
          {(payload?.source_checks ?? []).map((check) => (
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

function MetricTile({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail: string;
}) {
  return (
    <div className="macro-toolkit-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}
