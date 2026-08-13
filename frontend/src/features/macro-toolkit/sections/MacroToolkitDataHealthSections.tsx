import { DatabaseOutlined, LineChartOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Tag } from "antd";

import type {
  MacroToolkitDataHealth,
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
  formatDataHealthRepairAction,
  formatDataHealthRepairLabel,
  formatMissingIndicatorDetail,
  formatObservationDeferredSectionLabel,
  formatObservationRepairSummary,
  repairItemFocusKey,
  repairPriorityColor,
  repairPriorityLabel,
  repairTicketOwner,
  repairTicketReceipt,
  repairTicketReceiptStatus,
  repairTicketSla,
  repairTicketSubmissionImpact,
  repairTypeLabel,
  summarizeRepairAction,
} from "../lib/macroToolkitDataHealthSupport";
import { MacroStatusIcon } from "../lib/MacroToolkitStatusPrimitives";
import { compactText } from "../lib/macroToolkitPanelShared";
import type { MacroToolkitActionReceipt, MacroToolkitRepairItem } from "../lib/macroToolkitPageModel";

const RECEIPT_CHECK_WARNING_PATTERN = /^刷新回执未通过完整性校验[：:]\s*(.+?)(?:，方向性结论已关闭.*)?$/;
const CFFEX_OPTIONAL_MISSING_PATTERN = /^CFFEX optional step is missing/i;
const CFFEX_OPTIONAL_REPORTED_PATTERN = /^CFFEX optional step reported\s+(\S+?);/i;

/** 回执校验/CFFEX 可选步骤类告警收成中文摘要；键名清单进 details，原文进 title。 */
function DataHealthWarningNote({ warning }: { warning: string }) {
  const receiptMatch = warning.match(RECEIPT_CHECK_WARNING_PATTERN);
  if (receiptMatch?.[1]) {
    const checks = receiptMatch[1]
      .split("、")
      .map((item) => item.trim())
      .filter(Boolean);
    if (checks.length) {
      return (
        <details className="macro-toolkit-data-health__warning-note" title={warning}>
          <summary>
            刷新回执未通过完整性校验，共 {checks.length} 项检查未过，方向性结论已关闭（查看未过检查项）
          </summary>
          <ul>
            {checks.map((check) => (
              <li key={check}>{check}</li>
            ))}
          </ul>
        </details>
      );
    }
  }
  if (CFFEX_OPTIONAL_MISSING_PATTERN.test(warning)) {
    return (
      <span className="macro-toolkit-data-health__warning-soft" title={warning}>
        CFFEX 可选步骤未包含在回执中，必需步骤校验不受影响
      </span>
    );
  }
  const cffexReported = warning.match(CFFEX_OPTIONAL_REPORTED_PATTERN);
  if (cffexReported) {
    return (
      <span className="macro-toolkit-data-health__warning-soft" title={warning}>
        CFFEX 可选步骤状态待复核（{cffexReported[1]}），必需步骤校验不受影响
      </span>
    );
  }
  return <Tag color="red">{warning}</Tag>;
}

/** 能力缺口修复建议：英文缺口代码清单收进 details，卡面留一句中文摘要；原文同时进 title。 */
function MacroToolkitRepairActionNote({ action }: { action: string }) {
  const summary = summarizeRepairAction(action);
  if (!summary) {
    return <small title={action}>{compactText(action, 78)}</small>;
  }
  return (
    <details className="macro-toolkit-data-health__repair-note-details">
      <summary title={action}>{summary}</summary>
      <small>{action}</small>
    </details>
  );
}

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
  const focusedRepairItem = focusedRepairKey
    ? (repairItems.find((item) => repairItemFocusKey(item) === focusedRepairKey) ?? null)
    : null;
  const observationRepairSummary = plainLanguage ? formatObservationRepairSummary(repairItems) : null;
  const deferredText = dataHealth.deferred_sections.length
    ? `延后加载：${dataHealth.deferred_sections.map(formatObservationDeferredSectionLabel).join(" / ")}`
    : "完整结果已加载";
  const blockedActionNotes = plainLanguage
    ? []
    : Array.from(
        new Set(
          repairItems
            .filter(
              (item) =>
                item.action &&
                !(
                  item.action.enabled &&
                  (item.action.kind === "load_full_analysis" || canRefreshMacroSourceBackfill(item))
                ),
            )
            .map((item) => `${item.action?.label ?? "待处理"}：${item.action?.reason ?? "需要人工确认"}`),
        ),
      );
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
          {dataHealth.analysis_scope === "core" ? "首屏口径" : "完整口径"}
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
          {missingIndicators.length ? (
            <span className="macro-toolkit-data-health__notes-label">
              以下 {missingIndicators.length} 项缺失：
            </span>
          ) : null}
          {missingIndicators.map((item) => (
            <Tag color="gold" key={item.alias ?? item.key ?? item.label}>
              {item.alias ?? item.key ?? item.label}
            </Tag>
          ))}
          {missingAliases.length ? (
            <span className="macro-toolkit-data-health__notes-label">
              以下 {missingAliases.length} 项来源未命中：
            </span>
          ) : null}
          {missingAliases.map((alias) => (
            <Tag color="red" key={alias}>
              {alias}
            </Tag>
          ))}
          {dataHealth.warnings.map((warning) => (
            <DataHealthWarningNote warning={warning} key={warning} />
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
          {blockedActionNotes.length ? (
            <small
              className="macro-toolkit-data-health__repair-note"
              title={blockedActionNotes.join("；")}
            >
              {blockedActionNotes.join("；")}
            </small>
          ) : null}
          {focusedRepairItem ? (
            <MacroToolkitRepairTicket
              item={focusedRepairItem}
              receipt={dataHealthReceipt}
              receiptConfirmed={dataHealthReceiptConfirmed}
            />
          ) : null}
          <div className="macro-toolkit-data-health__repair-list">
            {repairItems.map((item) => {
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
                    <Tag color={repairPriorityColor(item.priority)}>
                      {repairPriorityLabel(item.priority)} · {repairTypeLabel(item.type)}
                    </Tag>
                    {formatDataHealthRepairLabel(item, plainLanguage)}
                  </span>
                  <MacroToolkitRepairActionNote action={formatDataHealthRepairAction(item, plainLanguage)} />
                </div>
                <div className="macro-toolkit-data-health__repair-meta">
                  {item.alias ? <small>{item.alias}</small> : null}
                  {item.source_table ? <small>{item.source_table}</small> : null}
                  {item.latest_date || item.stale_days ? (
                    <small>
                      {[
                        item.latest_date ? `最新值日期 ${item.latest_date}` : "",
                        item.stale_days ? `落后 ${item.stale_days} 天` : "",
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </small>
                  ) : null}
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
                      <small title={item.action.reason ?? "需要人工确认"}>
                        {item.action.label ?? "待处理"}
                      </small>
                    )}
                  </div>
                ) : null}
                </div>
              );
            })}
          </div>
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
