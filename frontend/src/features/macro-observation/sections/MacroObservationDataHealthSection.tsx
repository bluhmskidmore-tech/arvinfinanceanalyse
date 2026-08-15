import { Link } from "react-router-dom";

import {
  repairPriorityLabel,
  repairTypeLabel,
} from "../../macro-toolkit/lib/macroToolkitDataHealthSupport";
import type {
  MacroObservationDataHealthView,
  MacroObservationRepairRow,
} from "../model/macroObservationPageModel";
import "./MacroObservationHealthEvidence.css";

/**
 * 05 数据健康与修复项（只读）：单框三格覆盖读数带 + 修复项密度简表
 * （优先级徽标 / deferred 诚实态低饱和行）+「另 N 项」尾注与工具页链接。
 * 修复动作本身留在宏观工具页，本分区零操作按钮。
 */

/**
 * 模型层视图只透出展示文案（typeText / priorityText），不带原始枚举；
 * 徽标 tone 反查共享 lib 的锁定标签，避免复制字面量（标签变更时同源漂移）。
 */
const DEFERRED_TYPE_TEXT = repairTypeLabel("deferred");

const PRIORITY_TONE_BY_TEXT: Record<string, "high" | "medium" | "low"> = {
  [repairPriorityLabel("high")]: "high",
  [repairPriorityLabel("medium")]: "medium",
  [repairPriorityLabel("low")]: "low",
};

function isDeferredRepairRow(row: MacroObservationRepairRow): boolean {
  return row.typeText === DEFERRED_TYPE_TEXT;
}

export default function MacroObservationDataHealthSection({
  health,
}: {
  health: MacroObservationDataHealthView | null;
}) {
  if (!health) {
    return (
      <p
        className="macro-observation-datahealth__empty"
        data-testid="macro-observation-datahealth-empty"
      >
        数据健康读数尚未返回；核心分析落地后这里会补上覆盖读数与修复项。
      </p>
    );
  }

  return (
    <div className="macro-observation-datahealth" data-testid="macro-observation-datahealth">
      <div
        className="macro-observation-datahealth__coverage"
        role="group"
        aria-label="数据健康读数"
        data-testid="macro-observation-datahealth-coverage"
      >
        {health.coverage.map((item) => (
          <div key={item.key} className="macro-observation-datahealth__coverage-cell">
            <span className="macro-observation-datahealth__coverage-label">{item.label}</span>
            <strong className="macro-observation-datahealth__coverage-value">{item.value}</strong>
            {item.note ? (
              <small className="macro-observation-datahealth__coverage-note" title={item.note}>
                {item.note}
              </small>
            ) : null}
            {item.date ? (
              <small className="macro-observation-datahealth__coverage-note" title={item.date}>
                {item.date}
              </small>
            ) : null}
          </div>
        ))}
      </div>

      {health.repairItems.length ? (
        <div
          className="macro-observation-datahealth__table-region"
          role="region"
          tabIndex={0}
          aria-label="待处理数据项（只读）"
        >
        <table
          className="macro-observation-view__table macro-observation-datahealth__table"
        >
          <thead>
            <tr>
              <th className="macro-observation-datahealth__col-priority">优先级</th>
              <th className="macro-observation-datahealth__col-label">事项</th>
              <th className="macro-observation-datahealth__col-type">类型</th>
              <th>建议动作</th>
              <th className="macro-observation-datahealth__col-date">最新日期</th>
              <th className="macro-observation-datahealth__col-stale">滞后</th>
            </tr>
          </thead>
          <tbody>
            {health.repairItems.map((item) => {
              const deferred = isDeferredRepairRow(item);
              return (
                <tr key={item.key} data-deferred={deferred ? "true" : undefined}>
                  <td>
                    <span
                      className="macro-observation-datahealth__priority-badge"
                      data-priority={PRIORITY_TONE_BY_TEXT[item.priorityText] ?? "medium"}
                    >
                      {item.priorityText}
                    </span>
                  </td>
                  <td className="macro-observation-datahealth__label-cell" title={item.label}>
                    <span className="macro-observation-datahealth__label-text">{item.label}</span>
                    {deferred ? (
                      <span className="macro-observation-datahealth__deferred-badge">延后确认</span>
                    ) : null}
                  </td>
                  <td className="macro-observation-datahealth__type-cell">{item.typeText}</td>
                  {/* 展示层为中文短语；后端原句（含原始错误码）收行 title 溯源。 */}
                  <td
                    className="macro-observation-datahealth__action-cell"
                    title={item.actionTitle ?? item.actionText}
                  >
                    {item.actionText}
                  </td>
                  <td className="macro-observation-datahealth__date-cell">{item.latestDateText}</td>
                  <td className="macro-observation-datahealth__date-cell">{item.staleDaysText}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        </div>
      ) : (
        <p className="macro-observation-datahealth__note">当前没有待处理数据项。</p>
      )}

      <p className="macro-observation-datahealth__footer">
        {health.repairMoreNote ? (
          <span data-testid="macro-observation-repair-more">{health.repairMoreNote}</span>
        ) : null}
        <Link to="/macro-toolkit">完整修复清单见宏观工具页</Link>
      </p>

      {health.deferredSectionLabels.length ? (
        <p className="macro-observation-datahealth__note" aria-label="延后确认项">
          <strong>延后确认</strong>
          {health.deferredSectionLabels.map((label) => (
            <span key={label} className="macro-observation-datahealth__deferred-pill">
              {label}
            </span>
          ))}
        </p>
      ) : null}
      {health.warnings.length ? (
        <ul className="macro-observation-datahealth__warning" data-testid="macro-observation-datahealth-warnings">
          {health.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
