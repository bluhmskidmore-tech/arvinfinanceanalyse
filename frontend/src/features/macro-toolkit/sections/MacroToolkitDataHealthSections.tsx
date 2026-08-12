import { DatabaseOutlined, LineChartOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Tag } from "antd";

import type {
  MacroToolkitCapabilityResult,
  MacroToolkitDataHealth,
  MacroToolkitHasonStrategy,
  MacroToolkitSignalCard,
} from "../../../api/macroToolkitClient";
import {
  canRefreshMacroSourceBackfill,
  normalizeMacroSourceBackfillAlias,
} from "../lib/macroToolkitCrisisSupport";
import {
  capabilityHealthDetail,
  capabilityIssueCount,
  coverageValue,
  formatCompactObservationList,
  formatDataHealthRepairAction,
  formatDataHealthRepairLabel,
  formatMissingIndicatorDetail,
  formatObservationDeferredSectionLabel,
  formatObservationRepairSummary,
  formatObservationRepairTraceItem,
  repairItemFocusKey,
  repairPriorityColor,
  repairPriorityLabel,
  repairTicketOwner,
  repairTicketReceipt,
  repairTicketReceiptStatus,
  repairTicketSla,
  repairTicketSubmissionImpact,
  repairTypeLabel,
} from "../lib/macroToolkitDataHealthSupport";
import {
  MacroStatusIcon,
  compactText,
  observationStatusLabel,
  statusColor,
} from "../lib/macroToolkitPanelShared";
import type { MacroToolkitActionReceipt, MacroToolkitRepairItem } from "../lib/macroToolkitPageModel";

export function MacroToolkitDataHealthSummary({ dataHealth }: { dataHealth: MacroToolkitDataHealth }) {
  const repairItems = dataHealth.repair_items ?? [];
  const missingIndicators = dataHealth.indicator_coverage.missing;
  const missingAliases = dataHealth.source_coverage.missing_aliases;
  const repairSummary = repairItems.length ? formatObservationRepairSummary(repairItems) : "当前无待处理数据项。";
  return (
    <section className="macro-toolkit-data-health-summary" aria-label="数据健康摘要">
      <div className="macro-toolkit-data-health-summary__head">
        <span>
          <MacroStatusIcon tone={repairItems.length || missingIndicators.length || missingAliases.length ? "missing" : "neutral"}>
            <DatabaseOutlined />
          </MacroStatusIcon>
          数据健康摘要
        </span>
        <Tag color={dataHealth.analysis_scope === "core" ? "gold" : "green"}>
          {dataHealth.analysis_scope === "core" ? "首屏口径" : "完整口径"}
        </Tag>
      </div>
      <div className="macro-toolkit-data-health-summary__grid">
        <div>
          <span>指标覆盖</span>
          <strong>
            {dataHealth.indicator_coverage.hit_count}/{dataHealth.indicator_coverage.total_count}
          </strong>
          <small>{formatMissingIndicatorDetail(missingIndicators)}</small>
        </div>
        <div>
          <span>来源覆盖</span>
          <strong>{coverageValue(dataHealth.source_coverage)}</strong>
          <small>{dataHealth.source_coverage.deferred ? "来源检查延后确认" : missingAliases.length ? "有来源待补齐" : "来源全部命中"}</small>
        </div>
        <div>
          <span>观察复核提示</span>
          <strong>{repairItems.length ? `${repairItems.length} 项` : "无"}</strong>
          <small>{repairSummary}</small>
        </div>
      </div>
    </section>
  );
}

export function ObservationEvidenceTraceSummary({
  dataHealth,
  capabilityResults,
  degradedResultCount,
  hasonStrategy,
  isCoreAnalysis,
}: {
  dataHealth?: MacroToolkitDataHealth;
  capabilityResults: MacroToolkitCapabilityResult[];
  degradedResultCount: number;
  hasonStrategy?: MacroToolkitHasonStrategy;
  isCoreAnalysis: boolean;
}) {
  const repairItems = dataHealth?.repair_items ?? [];
  const missingIndicatorLabels =
    dataHealth?.indicator_coverage.missing.map((item) => item.label ?? item.alias ?? item.key).filter(Boolean) ?? [];
  const missingIndicatorDetail = dataHealth
    ? missingIndicatorLabels.length
      ? `缺口 ${formatCompactObservationList(missingIndicatorLabels)}。`
      : "指标全部命中。"
    : "完整分析后确认数据健康。";
  const sourceCoverageDetail = dataHealth
    ? dataHealth.source_coverage.deferred
      ? "完整分析补充项待确认。"
      : dataHealth.source_coverage.missing_aliases.length
        ? `来源待补齐 ${formatCompactObservationList(dataHealth.source_coverage.missing_aliases)}。`
        : "来源全部命中。"
    : "来源完整分析后确认。";
  const repairDetail = repairItems.length
    ? `${repairItems.length} 项复核提示：${formatCompactObservationList(repairItems.map(formatObservationRepairTraceItem))}；${formatObservationRepairSummary(repairItems)}`
    : "当前无复核提示。";
  const indicatorCoverage = dataHealth
    ? `${dataHealth.indicator_coverage.hit_count}/${dataHealth.indicator_coverage.total_count}`
    : "待确认";
  const capabilityValue = capabilityResults.length
    ? `${capabilityResults.length} 项证据`
    : "延后确认";
  const capabilityDetail = degradedResultCount
    ? `${degradedResultCount} 项证据需复核；不是正式投资信号。`
    : capabilityResults.length
      ? "能力证据仅解释覆盖情况，不是正式投资信号。"
      : "不按 0 处理。";
  const hasonValue = hasonStrategy ? observationStatusLabel(hasonStrategy.status) : "待确认";
  const hasonDetail = hasonStrategy
    ? `${hasonStrategy.readiness.ready_modules}/${hasonStrategy.readiness.total_modules} 覆盖，${hasonStrategy.readiness.missing_modules} 个模块待复核。`
    : "观察框架完整分析后确认。";
  return (
    <section className="macro-toolkit-observation-trace-summary" aria-label="证据追踪摘要">
      <div className="macro-toolkit-observation-trace-summary__head">
        <div>
          <span>证据追踪摘要</span>
          <strong>{isCoreAnalysis ? "首屏证据已压缩展示" : "完整证据已压缩展示"}</strong>
        </div>
        <Tag color={isCoreAnalysis ? "gold" : "green"}>{isCoreAnalysis ? "延后确认" : "完整分析"}</Tag>
      </div>
      <div className="macro-toolkit-observation-trace-summary__grid">
        <div>
          <span>数据健康</span>
          <strong>指标覆盖 {indicatorCoverage}</strong>
          <small>{missingIndicatorDetail}</small>
          <small>{sourceCoverageDetail}</small>
          <small>{repairDetail}</small>
        </div>
        <div>
          <span>能力证据</span>
          <strong>{capabilityValue}</strong>
          <small>{capabilityDetail}</small>
        </div>
        <div>
          <span>观察框架</span>
          <strong>{hasonValue}</strong>
          <small>{hasonDetail}</small>
        </div>
      </div>
    </section>
  );
}

export function MacroToolkitDataHealthPanel({
  dataHealth,
  showActions = false,
  plainLanguage = false,
  onRepairAction,
  repairActionLoading = false,
  refreshingSourceAlias = null,
  focusedRepairKey = null,
  dataHealthReceipt = null,
  dataHealthReceiptConfirmed = false,
}: {
  dataHealth: MacroToolkitDataHealth;
  showActions?: boolean;
  plainLanguage?: boolean;
  onRepairAction?: (item: MacroToolkitRepairItem) => void;
  repairActionLoading?: boolean;
  refreshingSourceAlias?: string | null;
  focusedRepairKey?: string | null;
  dataHealthReceipt?: MacroToolkitActionReceipt | null;
  dataHealthReceiptConfirmed?: boolean;
}) {
  const missingAliases = dataHealth.source_coverage.missing_aliases;
  const missingIndicators = dataHealth.indicator_coverage.missing;
  const repairItems = dataHealth.repair_items ?? [];
  const visibleRepairItems = repairItems.slice(0, 6);
  const hiddenRepairItemCount = repairItems.length - visibleRepairItems.length;
  const focusedRepairItem = focusedRepairKey
    ? (repairItems.find((item) => repairItemFocusKey(item) === focusedRepairKey) ?? null)
    : null;
  const observationRepairSummary = plainLanguage ? formatObservationRepairSummary(repairItems) : null;
  const deferredText = dataHealth.deferred_sections.length
    ? `延后加载：${dataHealth.deferred_sections.map(formatObservationDeferredSectionLabel).join(" / ")}`
    : "完整结果已加载";
  return (
    <section className="macro-toolkit-data-health" aria-label="数据健康总览">
      <div className="macro-toolkit-data-health__head">
        <span>
          <MacroStatusIcon tone={dataHealth.warnings.length ? "missing" : "neutral"}>
            <DatabaseOutlined />
          </MacroStatusIcon>
          数据健康总览
        </span>
        <Tag color={dataHealth.analysis_scope === "core" ? "gold" : "green"}>
          {dataHealth.analysis_scope === "core" ? "core 首屏" : "full 完整"}
        </Tag>
      </div>
      <div className="macro-toolkit-data-health__grid">
        <HealthMetricTile
          label="指标覆盖"
          value={`${dataHealth.indicator_coverage.hit_count}/${dataHealth.indicator_coverage.total_count}`}
          detail={formatMissingIndicatorDetail(missingIndicators)}
          tone={dataHealth.indicator_coverage.missing_count > 0 ? "neutral" : "positive"}
        />
        <HealthMetricTile
          label="来源覆盖"
          value={coverageValue(dataHealth.source_coverage)}
          detail={
            dataHealth.source_coverage.deferred
              ? "来源检查延后加载"
              : missingAliases.length
                ? `缺失 ${missingAliases.join(" / ")}`
                : "来源全部命中"
          }
          tone={dataHealth.source_coverage.deferred ? "neutral" : missingAliases.length ? "missing" : "positive"}
        />
        <HealthMetricTile
          label="最新来源日期"
          value={dataHealth.source_coverage.latest_date ?? "延后加载"}
          detail={deferredText}
          tone={dataHealth.source_coverage.latest_date ? "positive" : "neutral"}
        />
        <HealthMetricTile
          label="能力降级"
          value={capabilityIssueCount(dataHealth)}
          detail={capabilityHealthDetail(dataHealth)}
          tone={capabilityIssueCount(dataHealth) > 0 ? "neutral" : "positive"}
        />
      </div>
      {(missingIndicators.length || missingAliases.length || dataHealth.warnings.length) ? (
        <div className="macro-toolkit-data-health__notes">
          {missingIndicators.map((item) => (
            <Tag color="gold" key={item.alias ?? item.key ?? item.label}>
              {item.alias ?? item.key ?? item.label} 缺失
            </Tag>
          ))}
          {missingAliases.map((alias) => (
            <Tag color="red" key={alias}>
              {alias} 来源未命中
            </Tag>
          ))}
          {dataHealth.warnings.map((warning) => (
            <Tag color="red" key={warning}>
              {warning}
            </Tag>
          ))}
        </div>
      ) : null}
      {repairItems.length ? (
        <div className="macro-toolkit-data-health__repairs" aria-label="待处理数据项">
          <div className="macro-toolkit-data-health__repairs-head">
            <span>待处理数据项</span>
            <Tag color={repairItems.some((item) => item.priority === "high") ? "red" : "gold"}>
              {repairItems.length} 项
            </Tag>
          </div>
          {observationRepairSummary ? (
            <div className="macro-toolkit-data-health__repair-summary">
              <span>观察复核提示</span>
              <strong>{observationRepairSummary}</strong>
            </div>
          ) : null}
          {focusedRepairItem ? (
            <MacroToolkitRepairTicket
              item={focusedRepairItem}
              receipt={dataHealthReceipt}
              receiptConfirmed={dataHealthReceiptConfirmed}
            />
          ) : null}
          <div className="macro-toolkit-data-health__repair-list">
            {visibleRepairItems.map((item) => {
              const itemFocusKey = repairItemFocusKey(item);
              const isFocusedRepair = focusedRepairKey === itemFocusKey;
              return (
                <div
                  className={`macro-toolkit-data-health__repair macro-toolkit-data-health__repair--${item.priority ?? "medium"}${
                    isFocusedRepair ? " macro-toolkit-data-health__repair--focused" : ""
                  }`}
                  key={item.key ?? `${item.type}-${item.label}-${item.suggested_action}`}
                  aria-label={`${isFocusedRepair ? "当前处理数据项" : "待处理数据项"}-${itemFocusKey}`}
                  aria-current={isFocusedRepair ? "true" : undefined}
                >
                <div className="macro-toolkit-data-health__repair-main">
                  <span>
                    <Tag color={repairPriorityColor(item.priority)}>{repairPriorityLabel(item.priority)}</Tag>
                    <Tag color={statusColor(item.type ?? "")}>{repairTypeLabel(item.type)}</Tag>
                    {formatDataHealthRepairLabel(item, plainLanguage)}
                  </span>
                  <small title={formatDataHealthRepairAction(item, plainLanguage)}>
                    {compactText(formatDataHealthRepairAction(item, plainLanguage), 78)}
                  </small>
                  {!plainLanguage && item.action?.reason ? (
                    <small title={item.action.reason}>
                      {item.action.label ? `${item.action.label}：` : ""}
                      {compactText(item.action.reason, 56)}
                    </small>
                  ) : null}
                </div>
                <div className="macro-toolkit-data-health__repair-meta">
                  {item.alias ? <Tag color="default">{item.alias}</Tag> : null}
                  {item.latest_date ? <Tag color="blue">最新 {item.latest_date}</Tag> : null}
                  {item.stale_days ? <Tag color="gold">落后 {item.stale_days} 天</Tag> : null}
                  {item.source_table ? <Tag color="default">{item.source_table}</Tag> : null}
                </div>
                {!plainLanguage && item.action ? (
                  <div className="macro-toolkit-data-health__repair-action">
                    {showActions && item.action.enabled && item.action.kind === "load_full_analysis" ? (
                      <Button
                        size="small"
                        icon={<LineChartOutlined />}
                        loading={repairActionLoading}
                        aria-label={item.action.label ?? "查看完整分析"}
                        onClick={() => onRepairAction?.(item)}
                      >
                        {item.action.label ?? "查看完整分析"}
                      </Button>
                    ) : showActions && item.action.enabled && canRefreshMacroSourceBackfill(item) ? (
                      <Button
                        size="small"
                        icon={<ReloadOutlined />}
                        loading={refreshingSourceAlias === normalizeMacroSourceBackfillAlias(item.alias)}
                        aria-label={item.action.label ?? "需要补齐来源数据"}
                        onClick={() => onRepairAction?.(item)}
                      >
                        {item.action.label ?? "需要补齐来源数据"}
                      </Button>
                    ) : (
                      <small title={item.action.reason ?? ""}>
                        {item.action.label ?? "待处理"} · {item.action.reason ?? "需要人工确认"}
                      </small>
                    )}
                  </div>
                ) : null}
                </div>
              );
            })}
          </div>
          {hiddenRepairItemCount > 0 ? (
            <small className="macro-toolkit-data-health__repair-overflow">
              还有 {hiddenRepairItemCount} 项未显示；请查看完整分析或后端明细确认。
            </small>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export function MacroToolkitRepairTicket({
  item,
  receipt = null,
  receiptConfirmed = false,
}: {
  item: MacroToolkitRepairItem;
  receipt?: MacroToolkitActionReceipt | null;
  receiptConfirmed?: boolean;
}) {
  const itemFocusKey = repairItemFocusKey(item);
  const ticketAction = (item.action?.label ?? formatDataHealthRepairAction(item, false));
  const nextStep = ticketAction || "复核数据缺口";
  const receiptStatus = repairTicketReceiptStatus(receipt, receiptConfirmed);
  return (
    <div className="macro-toolkit-data-health__repair-ticket" aria-label={`当前处理单-${itemFocusKey}`}>
      <div className="macro-toolkit-data-health__repair-ticket-head">
        <span>当前处理单</span>
        <strong>{formatDataHealthRepairLabel(item, false)}</strong>
      </div>
      <div className="macro-toolkit-data-health__repair-ticket-grid">
        <div>
          <span>责任人</span>
          <strong>{repairTicketOwner(item)}</strong>
        </div>
        <div>
          <span>SLA</span>
          <strong>{repairTicketSla(item)}</strong>
        </div>
        <div>
          <span>预期回执</span>
          <strong>{repairTicketReceipt(item)}</strong>
        </div>
        <div>
          <span>提交影响</span>
          <strong>{repairTicketSubmissionImpact(item)}</strong>
        </div>
        <div>
          <span>回执状态</span>
          <strong>{receiptStatus}</strong>
        </div>
        <div>
          <span>回执证据</span>
          <strong>{receipt?.evidenceEntry ?? "等待执行"}</strong>
        </div>
      </div>
      {receipt && receiptConfirmed ? (
        <a className="macro-toolkit-data-health__repair-ticket-evidence" href={receipt.evidenceHref}>
          查看签核证据
        </a>
      ) : null}
      <small title={formatDataHealthRepairAction(item, false)}>{compactText(nextStep, 88)}</small>
    </div>
  );
}

export function HealthMetricTile({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string | number;
  detail: string;
  tone: MacroToolkitSignalCard["tone"];
}) {
  return (
    <div className={`macro-toolkit-data-health__tile macro-toolkit-data-health__tile--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small title={detail}>{compactText(detail, 32)}</small>
    </div>
  );
}
