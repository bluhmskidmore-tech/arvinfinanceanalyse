import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  InfoCircleOutlined,
  LineChartOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  ToolOutlined,
} from "@ant-design/icons";
import { Alert, Button, Checkbox, Select, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { Dispatch, SetStateAction } from "react";

import type { ResultMeta } from "../../../api/contracts";
import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitCffexMemberRankStatus,
  MacroToolkitChoiceStockRefreshPermission,
  MacroToolkitCommodityFuturesRefreshRun,
  MacroToolkitOutputFile,
  MacroToolkitPayload,
  MacroToolkitRunResponse,
  MacroToolkitScriptChainRun,
  MacroToolkitScriptRecord,
  MacroToolkitSourceCheck,
} from "../../../api/macroToolkitClient";
import { DataStatusStrip, PageSectionLead } from "../../../components/page/PagePrimitives";
import {
  formatCommodityShortfallChangeList,
  formatCommodityShortfallEstimateList,
} from "../lib/macroToolkitCrisisSupport";
import type {
  CommodityShortfallChange,
  CommodityShortfallEstimate,
} from "../lib/macroToolkitCrisisSupport";
import {
  chainRunAlertType,
  formatBusinessEvidenceLabel,
  formatQualityFlagLabel,
  formatSize,
  formatSourceCheck,
  groupLabel,
  statusTone,
} from "../lib/macroToolkitDisplayFormat";
import { MetricTile, statusLabel } from "../lib/macroToolkitPanelShared";
import {
  MACRO_COMMODITY_PRODUCT_OPTIONS,
} from "../lib/macroToolkitPageModel";
import type {
  CommodityRefreshOptions,
  MacroToolkitActionReceipt,
  MacroToolkitGovernanceFocusKey,
  RefreshFeedbackTone,
} from "../lib/macroToolkitPageModel";
import {
  choiceStockPermissionDetail,
  choiceStockPermissionValue,
  commodityCoverageDetail,
  commodityCoverageValue,
  commodityFuturesPermissionDetail,
  commodityFuturesPermissionNotice,
  commodityFuturesPermissionNoticeTitle,
  commodityLatestDateValue,
  commodityNanhuaStatusDetail,
  commodityNanhuaStatusTone,
  commodityNanhuaStatusValue,
  commoditySourceDetail,
  commoditySourceValue,
  commodityStatusTone,
  commodityTableStatusDetail,
} from "../lib/macroToolkitStrategyDisplaySupport";
import type { CommodityHealthStatus } from "../lib/macroToolkitStrategyDisplaySupport";
import { CommodityRefreshResultPanel } from "../panels/MacroToolkitCrisisPanels";
import { ActionReceiptPanel, ActionReceiptQueue } from "./MacroToolkitGovernanceSections";

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

export function MacroToolkitOperationsConsolePanel({
  selectedScript,
  scripts,
  availableScriptCount,
  actionReceipt,
  actionReceipts,
  selectedEvidenceHref,
  setSelectedEvidenceHref,
  defaultBusinessEvidenceSources,
  cffexStatus,
  commodityStatus,
  payload,
  outputDetail,
  selectedExecutionHref,
  isOperationActionBusy,
  isRunning,
  runSelectedScript,
  isRunningChain,
  runScriptChain,
  isRefreshingChoiceStock,
  refreshChoiceStock,
  isRefreshingCffex,
  refreshCffexMemberRank,
  isRefreshingCommodity,
  commodityRefreshDisabled,
  refreshCommodityFutures,
  commodityRefreshActionLabel,
  scriptsQuery,
  stockRefreshResult,
  stockRefreshError,
  refreshResult,
  refreshFeedbackTone,
  refreshError,
  commodityRefreshResult,
  commodityRefreshError,
  chainRunResult,
  chainRunError,
  runResult,
  runError,
}: {
  selectedScript: MacroToolkitScriptRecord | null;
  scripts: MacroToolkitScriptRecord[];
  availableScriptCount: number;
  actionReceipt: MacroToolkitActionReceipt;
  actionReceipts: MacroToolkitActionReceipt[];
  selectedEvidenceHref: string | null;
  setSelectedEvidenceHref: (href: string) => void;
  defaultBusinessEvidenceSources: string;
  cffexStatus: MacroToolkitCffexMemberRankStatus | null;
  commodityStatus: CommodityHealthStatus | null;
  payload: MacroToolkitPayload | undefined;
  outputDetail: string;
  selectedExecutionHref: string | null;
  isOperationActionBusy: boolean;
  isRunning: boolean;
  runSelectedScript: () => Promise<void>;
  isRunningChain: boolean;
  runScriptChain: (dryRun: boolean, modelId?: string) => Promise<void>;
  isRefreshingChoiceStock: boolean;
  refreshChoiceStock: () => Promise<void>;
  isRefreshingCffex: boolean;
  refreshCffexMemberRank: () => Promise<void>;
  isRefreshingCommodity: boolean;
  commodityRefreshDisabled: boolean;
  refreshCommodityFutures: (options?: CommodityRefreshOptions) => Promise<void>;
  commodityRefreshActionLabel: string;
  scriptsQuery: { isError: boolean };
  stockRefreshResult: string | null;
  stockRefreshError: string | null;
  refreshResult: string | null;
  refreshFeedbackTone: RefreshFeedbackTone;
  refreshError: string | null;
  commodityRefreshResult: string | null;
  commodityRefreshError: string | null;
  chainRunResult: MacroToolkitScriptChainRun | null;
  chainRunError: string | null;
  runResult: MacroToolkitRunResponse | null;
  runError: string | null;
}) {
  return (
    <div
      id="macro-toolkit-operations-console"
      className="macro-toolkit-operations-console"
      data-testid="macro-toolkit-operations-console"
    >
      <div className="macro-toolkit-operations-console__head">
        <div>
          <span>操作台</span>
          <strong>{selectedScript?.name ?? "脚本注册表读取中"}</strong>
          <small>执行脚本、刷新数据源、确认产物状态。</small>
        </div>
        <Tag color={scripts.length > 0 && availableScriptCount === scripts.length ? "green" : "gold"}>
          脚本 {availableScriptCount}/{scripts.length}
        </Tag>
      </div>
      <ActionReceiptPanel receipt={actionReceipt} />
      <ActionReceiptQueue
        receipts={actionReceipts}
        selectedEvidenceHref={selectedEvidenceHref}
        onSelectEvidence={setSelectedEvidenceHref}
      />
      <div className="macro-toolkit-operations-console__metrics">
        <MetricTile
          icon={<DatabaseOutlined />}
          label="业务证据"
          value={defaultBusinessEvidenceSources}
          detail="分析、刷新和脚本共享同一证据口径"
          detailMaxLength={38}
        />
        <MetricTile
          icon={<ClockCircleOutlined />}
          label="席位日期"
          value={cffexStatus?.latest_trade_date ?? "缺失"}
          detail={`中金所席位 ${cffexStatus?.row_count ?? 0} 行`}
        />
        <MetricTile
          icon={<LineChartOutlined />}
          label="商品期货"
          value={commodityNanhuaStatusValue(commodityStatus)}
          detail={commodityNanhuaStatusDetail(commodityStatus)}
          tone={commodityNanhuaStatusTone(commodityStatus)}
        />
        <MetricTile
          icon={<ToolOutlined />}
          label="输出文件"
          value={payload?.output_files.length ?? 0}
          detail={outputDetail}
        />
      </div>
      <div
        id="macro-toolkit-operations-actions"
        className={`macro-toolkit-operations-console__actions ${
          selectedExecutionHref === "#macro-toolkit-operations-actions"
            ? "macro-toolkit-operations-console__actions--active"
            : ""
        }`}
        data-testid="macro-toolkit-operations-actions"
      >
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          disabled={!selectedScript || (isOperationActionBusy && !isRunning)}
          loading={isRunning}
          onClick={() => void runSelectedScript()}
        >
          运行选中脚本
        </Button>
        <Button
          icon={<InfoCircleOutlined />}
          loading={isRunningChain}
          disabled={isOperationActionBusy && !isRunningChain}
          onClick={() => void runScriptChain(true)}
        >
          预检模型链
        </Button>
        <Button
          icon={<PlayCircleOutlined />}
          loading={isRunningChain}
          disabled={isOperationActionBusy && !isRunningChain}
          onClick={() => void runScriptChain(false)}
        >
          运行模型链
        </Button>
        <Button
          icon={<ReloadOutlined />}
          loading={isRefreshingChoiceStock}
          disabled={isOperationActionBusy && !isRefreshingChoiceStock}
          onClick={() => void refreshChoiceStock()}
          aria-label="刷新股票策略明细"
        >
          刷新股票策略明细
        </Button>
        <Button
          icon={<ReloadOutlined />}
          loading={isRefreshingCffex}
          disabled={isOperationActionBusy && !isRefreshingCffex}
          onClick={() => void refreshCffexMemberRank()}
        >
          刷新席位明细
        </Button>
        <Button
          icon={<InfoCircleOutlined />}
          loading={isRefreshingCommodity}
          disabled={commodityRefreshDisabled || (isOperationActionBusy && !isRefreshingCommodity)}
          onClick={() => void refreshCommodityFutures({ dryRun: true })}
        >
          预估明细刷新
        </Button>
        <Button
          icon={<ReloadOutlined />}
          loading={isRefreshingCommodity}
          disabled={commodityRefreshDisabled || (isOperationActionBusy && !isRefreshingCommodity)}
          aria-label={commodityRefreshActionLabel}
          onClick={() => void refreshCommodityFutures({ dryRun: false })}
        >
          {commodityRefreshActionLabel}
        </Button>
      </div>
      {scriptsQuery.isError ? <Alert type="error" showIcon message="脚本注册表加载失败" /> : null}
      {stockRefreshResult ? <Alert type="success" showIcon message={stockRefreshResult} /> : null}
      {stockRefreshError ? <Alert type="error" showIcon message={stockRefreshError} /> : null}
      {refreshResult ? <Alert type={refreshFeedbackTone} showIcon message={refreshResult} /> : null}
      {refreshError ? <Alert type="error" showIcon message={refreshError} /> : null}
      {commodityRefreshResult ? <Alert type="success" showIcon message={commodityRefreshResult} /> : null}
      {commodityRefreshError ? <Alert type="error" showIcon message={commodityRefreshError} /> : null}
      {chainRunResult ? (
        <Alert
          type={chainRunAlertType(chainRunResult.status)}
          showIcon
          message={`模型链：${chainRunResult.status}`}
          description={`步骤 ${chainRunResult.receipts.length}/${chainRunResult.manifest.length} · 产物支撑 ${chainRunResult.readiness_after.artifact_backed_count}/${chainRunResult.readiness_after.total_count} · 仅观察`}
        />
      ) : null}
      {chainRunError ? <Alert type="error" showIcon message={chainRunError} /> : null}
      {runResult ? (
        <Alert
          type={statusTone(runResult.status)}
          showIcon
          message={`脚本运行：${runResult.status}`}
          description={`输出文件 ${runResult.output_files.length} · 退出码 ${runResult.exit_code ?? "无"}`}
        />
      ) : null}
      {runError ? <Alert type="error" showIcon message={runError} /> : null}
    </div>
  );
}

export function MacroToolkitExecutionReceiptWorkspace({
  analysis,
  payload,
  scriptsQuery,
  scripts,
  availableScriptCount,
  executionBusinessEvidence,
  outputReceiptDetail,
  sourceHitCount,
  sourceChecks,
  selectedEvidenceHref,
  selectedGovernanceFocus,
  cffexStatus,
  isRefreshingCffex,
  refreshCffexMemberRank,
  isOperationActionBusy,
  refreshResult,
  refreshFeedbackTone,
  refreshError,
  selectedCommodityProducts,
  setSelectedCommodityProducts,
  setCommoditySuggestedSelection,
  setCommodityRefreshResult,
  setCommodityRefreshError,
  setCommodityRefreshRun,
  setCommodityEvidenceReloadMessage,
  setCommodityShortfallChanges,
  setCommodityShortfallEstimates,
  commodityPermission,
  shouldShowCommodityPermissionNotice,
  commodityStatus,
  commoditySuggestedSelection,
  isRefreshingCommodity,
  commodityRefreshDisabled,
  refreshCommodityFutures,
  commodityRefreshActionLabel,
  commodityRefreshResult,
  commodityEvidenceReloadMessage,
  commodityShortfallChanges,
  commodityShortfallEstimates,
  commodityRefreshError,
  commodityRefreshRun,
  actionReceipts,
  receiptTechnicalDetailsExpanded,
  setReceiptTechnicalDetailsExpanded,
  omittedEntries,
  selectedGroup,
  groupOptions,
  setSelectedGroup,
  setSelectedName,
  selectedScript,
  runSelectedScript,
  isRunning,
  runScriptChain,
  isRunningChain,
  filteredScripts,
  runError,
  runResult,
  chainRunResult,
}: {
  analysis: MacroToolkitAnalysisPayload | undefined;
  payload: MacroToolkitPayload | undefined;
  scriptsQuery: {
    isFetching: boolean;
    isError: boolean;
    data: { result_meta: ResultMeta } | undefined;
    refetch: () => Promise<unknown>;
  };
  scripts: MacroToolkitScriptRecord[];
  availableScriptCount: number;
  executionBusinessEvidence: string;
  outputReceiptDetail: string;
  sourceHitCount: number;
  sourceChecks: MacroToolkitSourceCheck[];
  selectedEvidenceHref: string | null;
  selectedGovernanceFocus: MacroToolkitGovernanceFocusKey;
  cffexStatus: MacroToolkitCffexMemberRankStatus | null;
  isRefreshingCffex: boolean;
  refreshCffexMemberRank: () => Promise<void>;
  isOperationActionBusy: boolean;
  refreshResult: string | null;
  refreshFeedbackTone: RefreshFeedbackTone;
  refreshError: string | null;
  selectedCommodityProducts: string[];
  setSelectedCommodityProducts: (products: string[]) => void;
  setCommoditySuggestedSelection: (products: string[]) => void;
  setCommodityRefreshResult: (value: string | null) => void;
  setCommodityRefreshError: (value: string | null) => void;
  setCommodityRefreshRun: (run: MacroToolkitCommodityFuturesRefreshRun | null) => void;
  setCommodityEvidenceReloadMessage: (value: string | null) => void;
  setCommodityShortfallChanges: (changes: CommodityShortfallChange[]) => void;
  setCommodityShortfallEstimates: (estimates: CommodityShortfallEstimate[]) => void;
  commodityPermission: MacroToolkitChoiceStockRefreshPermission | null;
  shouldShowCommodityPermissionNotice: boolean;
  commodityStatus: CommodityHealthStatus | null;
  commoditySuggestedSelection: string[];
  isRefreshingCommodity: boolean;
  commodityRefreshDisabled: boolean;
  refreshCommodityFutures: (options?: CommodityRefreshOptions) => Promise<void>;
  commodityRefreshActionLabel: string;
  commodityRefreshResult: string | null;
  commodityEvidenceReloadMessage: string | null;
  commodityShortfallChanges: CommodityShortfallChange[];
  commodityShortfallEstimates: CommodityShortfallEstimate[];
  commodityRefreshError: string | null;
  commodityRefreshRun: MacroToolkitCommodityFuturesRefreshRun | null;
  actionReceipts: MacroToolkitActionReceipt[];
  receiptTechnicalDetailsExpanded: boolean;
  setReceiptTechnicalDetailsExpanded: Dispatch<SetStateAction<boolean>>;
  omittedEntries: [string, string][];
  selectedGroup: string;
  groupOptions: { value: string; label: string }[];
  setSelectedGroup: (group: string) => void;
  setSelectedName: (name: string | null) => void;
  selectedScript: MacroToolkitScriptRecord | null;
  runSelectedScript: () => Promise<void>;
  isRunning: boolean;
  runScriptChain: (dryRun: boolean, modelId?: string) => Promise<void>;
  isRunningChain: boolean;
  filteredScripts: MacroToolkitScriptRecord[];
  runError: string | null;
  runResult: MacroToolkitRunResponse | null;
  chainRunResult: MacroToolkitScriptChainRun | null;
}) {
  const receiptWorkpaperItems = [
    {
      key: "archive",
      label: "产物归档",
      value: `${payload?.output_files.length ?? 0} 个产物`,
      detail: "明细在下方展开",
    },
    {
      key: "source",
      label: "来源命中",
      value: `${sourceHitCount}/${sourceChecks.length}`,
      detail: sourceChecks.length ? "来源证据已留痕" : "来源证据待返回",
    },
    {
      key: "execution",
      label: "执行能力",
      value: `${availableScriptCount}/${scripts.length}`,
      detail: scripts.length ? "可执行能力已归档" : "执行能力待返回",
    },
    {
      key: "receipt",
      label: "留痕状态",
      value: `${actionReceipts.length} 条`,
      detail: actionReceipts.length ? "回执队列可复核" : "等待操作回执",
    },
  ];
  return (
        <section className="macro-toolkit-execution-receipt-workspace" aria-label="执行证据与产物回执区">
          <div className="macro-toolkit-execution-receipt-workspace__head">
            <div>
              <span>执行与产物</span>
              <strong>执行证据</strong>
              <small>把可执行脚本、席位和商品刷新先归入证据，再用产物与数据源命中形成回执。</small>
            </div>
          </div>

          <div className="macro-toolkit-execution-receipt-workspace__execution" aria-label="执行证据详情">
            <span className="macro-toolkit-execution-receipt-workspace__section-label">执行证据</span>
          <section
            id="macro-toolkit-tool-execution-detail"
            data-testid="macro-toolkit-tool-execution-detail"
            className={`macro-toolkit-section macro-toolkit-operations-section ${
              selectedGovernanceFocus === "execution" ||
              selectedEvidenceHref === "#macro-toolkit-tool-execution-detail"
                ? "macro-toolkit-section--audit-focus"
                : ""
            }`}
          >
            <div className="macro-toolkit-section-headline">
              <PageSectionLead
                eyebrow="执行"
                title="执行闭环总览"
                description="把脚本状态、数据证据和产物回执合并成投委会可复核的执行闭环。"
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
                detail="可执行能力已归入执行证据"
                tone={availableScriptCount === scripts.length ? "positive" : "neutral"}
              />
              <MetricTile
                label="业务证据"
                value={executionBusinessEvidence}
                detail="底层源名留在审计明细"
                detailMaxLength={38}
              />
              <MetricTile label="产物回执" value={payload?.output_files.length ?? 0} detail={outputReceiptDetail} />
              <MetricTile
                label="来源映射"
                value={`${sourceHitCount}/${sourceChecks.length}`}
                detail="旧别名已映射到当前业务证据"
              />
            </div>
          </section>

          {scriptsQuery.isError ? <Alert type="error" showIcon message="宏观工具加载失败" /> : null}

          {payload ? (
            <DataStatusStrip className="macro-toolkit-status-strip">
              <span>证据口径：{formatBusinessEvidenceLabel(scriptsQuery.data?.result_meta.basis)}</span>
              <span>业务证据：{executionBusinessEvidence}</span>
              <span>质量状态：{formatQualityFlagLabel(scriptsQuery.data?.result_meta.quality_flag)}</span>
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

          <section
            id="macro-toolkit-cffex-detail"
            data-testid="macro-toolkit-cffex-detail"
            className={`macro-toolkit-section ${
              selectedEvidenceHref === "#macro-toolkit-cffex-detail" ? "macro-toolkit-section--audit-focus" : ""
            }`}
          >
            <PageSectionLead
              eyebrow="席位"
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
                    cffexStatus?.stale_days == null ? "待确认" : `落后 ${cffexStatus.stale_days} 天`
                  }
                />
              </div>
              <div className="macro-toolkit-cffex-actions">
                <Button
                  icon={<ReloadOutlined />}
                  loading={isRefreshingCffex}
                  disabled={isOperationActionBusy && !isRefreshingCffex}
                  onClick={() => void refreshCffexMemberRank()}
                >
                  刷新席位明细
                </Button>
                {refreshResult ? <Alert type={refreshFeedbackTone} showIcon message={refreshResult} /> : null}
                {refreshError ? <Alert type="error" showIcon message={refreshError} /> : null}
              </div>
            </div>
          </section>

          <section
            id="macro-toolkit-commodity-detail"
            data-testid="macro-toolkit-commodity-detail"
            className={`macro-toolkit-section ${
              selectedEvidenceHref === "#macro-toolkit-commodity-detail" ? "macro-toolkit-section--audit-focus" : ""
            }`}
          >
            <PageSectionLead
              eyebrow="商品"
              title="商品期货状态"
              description="刷新南华指数和宏观旁证商品期货；Crisis Score 公式仍只读取南华输入。"
            />
            <div className="macro-toolkit-cffex-panel" aria-label="商品期货刷新">
              <div className="macro-toolkit-cffex-metrics">
                <MetricTile
                  icon={<DatabaseOutlined />}
                  label="已选品种"
                  value={`${selectedCommodityProducts.length}/${MACRO_COMMODITY_PRODUCT_OPTIONS.length}`}
                  detail={
                    selectedCommodityProducts.length === MACRO_COMMODITY_PRODUCT_OPTIONS.length
                      ? "默认全选，可缩小范围"
                      : selectedCommodityProducts.join(" / ") || "未选择"
                  }
                />
                <MetricTile
                  icon={<SafetyCertificateOutlined />}
                  label="商品权限"
                  value={choiceStockPermissionValue(commodityPermission)}
                  detail={commodityFuturesPermissionDetail(commodityPermission)}
                  detailTitle={choiceStockPermissionDetail(commodityPermission, "macro_toolkit.commodity_futures")}
                  tone={shouldShowCommodityPermissionNotice ? "missing" : "neutral"}
                />
                <MetricTile
                  icon={<LineChartOutlined />}
                  label="南华输入"
                  value={commodityNanhuaStatusValue(commodityStatus)}
                  detail={commodityNanhuaStatusDetail(commodityStatus)}
                  tone={commodityNanhuaStatusTone(commodityStatus)}
                />
                <MetricTile
                  icon={<ClockCircleOutlined />}
                  label="最新日期"
                  value={commodityLatestDateValue(commodityStatus)}
                  detail={commodityTableStatusDetail(commodityStatus)}
                  tone={commodityStatusTone(commodityStatus)}
                />
                <MetricTile
                  icon={<DatabaseOutlined />}
                  label="覆盖品种"
                  value={commodityCoverageValue(commodityStatus)}
                  detail={commodityCoverageDetail(commodityStatus)}
                  tone={commodityStatusTone(commodityStatus)}
                />
                <MetricTile
                  icon={<SafetyCertificateOutlined />}
                  label="数据来源"
                  value={commoditySourceValue(commodityStatus)}
                  detail={commoditySourceDetail(commodityStatus)}
                  tone={commodityStatusTone(commodityStatus)}
                />
                <MetricTile
                  icon={<SafetyCertificateOutlined />}
                  label="证据归属"
                  value="商品期货证据"
                  detail="刷新后重新读取完整分析证据"
                />
              </div>
              <div className="macro-toolkit-commodity-selector">
                <span className="macro-toolkit-commodity-selector-label">刷新品种</span>
                <Checkbox.Group
                  className="macro-toolkit-commodity-products"
                  value={selectedCommodityProducts}
                  onChange={(values) => {
                    setSelectedCommodityProducts(values.map(String));
                    setCommoditySuggestedSelection([]);
                    setCommodityRefreshResult(null);
                    setCommodityRefreshError(null);
                    setCommodityRefreshRun(null);
                    setCommodityEvidenceReloadMessage(null);
                    setCommodityShortfallChanges([]);
                    setCommodityShortfallEstimates([]);
                  }}
                >
                  {MACRO_COMMODITY_PRODUCT_OPTIONS.map((option) => (
                    <Checkbox key={option.value} value={option.value}>
                      <span className="macro-toolkit-commodity-product-text">
                        <span>{option.label}</span>
                        <small>
                          {option.value} · {option.description}
                        </small>
                      </span>
                    </Checkbox>
                  ))}
                </Checkbox.Group>
              </div>
              {commoditySuggestedSelection.length ? (
                <Alert
                  type="info"
                  showIcon
                  message={`已按 Crisis Score 建议选择：${commoditySuggestedSelection.join(" / ")}`}
                  description="下一步先预估商品期货，再根据预计行数决定是否刷新。"
                />
              ) : null}
              {shouldShowCommodityPermissionNotice ? (
                <Alert
                  type="warning"
                  showIcon
                  message={commodityFuturesPermissionNoticeTitle(commodityPermission)}
                  description={commodityFuturesPermissionNotice(commodityPermission)}
                />
              ) : null}
              <div className="macro-toolkit-cffex-actions">
                <Button
                  icon={<InfoCircleOutlined />}
                  loading={isRefreshingCommodity}
                  disabled={commodityRefreshDisabled || (isOperationActionBusy && !isRefreshingCommodity)}
                  onClick={() => void refreshCommodityFutures({ dryRun: true })}
                >
                  预估明细刷新
                </Button>
                <Button
                  icon={<ReloadOutlined />}
                  loading={isRefreshingCommodity}
                  disabled={commodityRefreshDisabled || (isOperationActionBusy && !isRefreshingCommodity)}
                  aria-label={commodityRefreshActionLabel}
                  onClick={() => void refreshCommodityFutures({ dryRun: false })}
                >
                  {commodityRefreshActionLabel}
                </Button>
                {commodityRefreshResult ? <Alert type="success" showIcon message={commodityRefreshResult} /> : null}
                {commodityEvidenceReloadMessage ? (
                  <Alert
                    type={commodityEvidenceReloadMessage.includes("失败") ? "error" : "success"}
                    showIcon
                    message={commodityEvidenceReloadMessage}
                  />
                ) : null}
                {commodityShortfallChanges.length ? (
                  <Alert
                    type="success"
                    showIcon
                    message="Crisis Score 样本缺口变化"
                    description={formatCommodityShortfallChangeList(commodityShortfallChanges)}
                  />
                ) : null}
                {commodityShortfallEstimates.length ? (
                  <Alert
                    type={commodityShortfallEstimates.every((item) => item.canFill) ? "success" : "warning"}
                    showIcon
                    message="Crisis Score 样本预估"
                    description={formatCommodityShortfallEstimateList(commodityShortfallEstimates)}
                  />
                ) : null}
                {commodityRefreshError ? <Alert type="error" showIcon message={commodityRefreshError} /> : null}
              </div>
              {commodityRefreshRun ? <CommodityRefreshResultPanel refresh={commodityRefreshRun} /> : null}
            </div>
          </section>

          </div>

          <aside className="macro-toolkit-execution-receipt-workspace__receipt" aria-label="产物回执详情">
            <span className="macro-toolkit-execution-receipt-workspace__section-label">产物回执</span>
            <section className="macro-toolkit-receipt-workpaper" aria-label="产物审计底稿">
              <div className="macro-toolkit-receipt-workpaper__head">
                <span>产物审计底稿</span>
                <strong>回执先审，明细后查</strong>
                <small>脚本、文件和日志保留在下方明细；投委会先看归档、来源、执行和留痕。</small>
              </div>
              <div className="macro-toolkit-receipt-workpaper__grid">
                {receiptWorkpaperItems.map((item) => (
                  <div className="macro-toolkit-receipt-workpaper__item" key={item.key}>
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                    <small>{item.detail}</small>
                  </div>
                ))}
              </div>
            </section>
            <section
              className={`macro-toolkit-receipt-technical-details ${
                receiptTechnicalDetailsExpanded
                  ? "macro-toolkit-receipt-technical-details--expanded"
                  : "macro-toolkit-receipt-technical-details--collapsed"
              }`}
              aria-label="底稿技术明细"
            >
              <div className="macro-toolkit-receipt-technical-details__head">
                <div>
                  <span>底稿技术明细</span>
                  <strong>脚本、来源、注册表和日志</strong>
                  <small>{receiptTechnicalDetailsExpanded ? "已展开" : "默认收起"} · 审计追溯保留在这里</small>
                </div>
                <Button
                  size="small"
                  icon={receiptTechnicalDetailsExpanded ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                  aria-label={receiptTechnicalDetailsExpanded ? "收起明细" : "展开明细"}
                  aria-expanded={receiptTechnicalDetailsExpanded}
                  aria-controls="macro-toolkit-receipt-technical-details-body"
                  onClick={() => setReceiptTechnicalDetailsExpanded((expanded) => !expanded)}
                >
                  {receiptTechnicalDetailsExpanded ? "收起明细" : "展开明细"}
                </Button>
              </div>
              {receiptTechnicalDetailsExpanded ? (
                <div
                  id="macro-toolkit-receipt-technical-details-body"
                  className="macro-toolkit-receipt-technical-details__body"
                >
                <section
                  id="macro-toolkit-script-artifact-detail"
                  data-testid="macro-toolkit-script-artifact-detail"
                  className={`macro-toolkit-section ${
                    selectedGovernanceFocus === "artifacts" ||
                    selectedEvidenceHref === "#macro-toolkit-script-artifact-detail"
                      ? "macro-toolkit-section--audit-focus"
                      : ""
                  }`}
                >
                  <PageSectionLead
                    eyebrow="产物"
                    title="脚本产物"
                    description="运行脚本后自动刷新这里，便于确认 CSV、图片或报告是否生成。"
                  />
                  {payload?.output_files.length ? (
                    <Table
                      className="macro-toolkit-table--receipt"
                      rowKey="path"
                      size="small"
                      columns={outputColumns}
                      dataSource={payload.output_files}
                      pagination={false}
                      scroll={{ x: 640 }}
                    />
                  ) : (
                    <div className="macro-toolkit-empty-output">尚未发现输出文件。</div>
                  )}
                </section>

                <section className="macro-toolkit-section">
                  <PageSectionLead
                    eyebrow="来源"
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
                      eyebrow="未纳入"
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
                    eyebrow="脚本"
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
                      disabled={!selectedScript || (isOperationActionBusy && !isRunning)}
                      loading={isRunning}
                      onClick={() => void runSelectedScript()}
                    >
                      运行选中脚本
                    </Button>
                    <Button
                      icon={<InfoCircleOutlined />}
                      disabled={isOperationActionBusy && !isRunningChain}
                      loading={isRunningChain}
                      onClick={() => void runScriptChain(true)}
                    >
                      预检模型链
                    </Button>
                  </div>
                  <Table
                    className="macro-toolkit-table--receipt"
                    rowKey="name"
                    size="small"
                    columns={scriptColumns}
                    dataSource={filteredScripts}
                    pagination={{ pageSize: 8, showSizeChanger: false }}
                    scroll={{ x: 640 }}
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
                    eyebrow="运行"
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
                    {chainRunResult ? (
                      <Alert
                        type={chainRunAlertType(chainRunResult.status)}
                        showIcon
                        message={`模型链：${chainRunResult.status}`}
                        description={`步骤：${chainRunResult.receipts.length}/${chainRunResult.manifest.length} · 缺口：${chainRunResult.readiness_after.degraded_count}`}
                      />
                    ) : null}
                    <pre className="macro-toolkit-console">
                      {runResult?.stdout || runResult?.stderr || "尚未运行。"}
                    </pre>
                  </div>
                </section>
                </div>
              ) : null}
            </section>
          </aside>
        </section>
  );
}
