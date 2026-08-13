import type { ResultMeta } from "../../../api/contracts";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import type { LabeledValue } from "../../../pageModel";
import type {
  MacroObservationEvidenceMetaView,
  MacroObservationReportBundleView,
} from "../model/macroObservationPageModel";
import "./MacroObservationHealthEvidence.css";

/**
 * 06 证据与口径（只读）三段式：
 * 1. 运行时状态行（runtimeSummary 三句之一 + 延后分区徽标列）；
 * 2. FormalResultMetaPanel 完整溯源 + 口径速读补充行——面板已完整展示
 *    basis / trace_id 全文 / generated_at / tables 明细，速读区只补面板
 *    没有的人话行：正式使用（仅观察）与质量标记的防误读说明；
 * 3. 报告产物列表（下载 a 链接是本分区唯一操作出口）。
 */

/** 面板未覆盖的口径速读行：正式使用说明 + 质量标记防误读 note。 */
const CALIBER_SUPPLEMENT_KEY_SUFFIXES = ["-formal-use", "-quality"] as const;

function caliberSupplementRows(rows: LabeledValue[] | null): LabeledValue[] {
  return (rows ?? []).filter((row) =>
    CALIBER_SUPPLEMENT_KEY_SUFFIXES.some((suffix) => row.key.endsWith(suffix)),
  );
}

export default function MacroObservationEvidenceSection({
  metaView,
  analysisMeta,
  strategyMeta,
  reportBundle,
  runtimeSummary,
  deferredSectionLabels,
}: {
  metaView: MacroObservationEvidenceMetaView;
  analysisMeta: ResultMeta | undefined;
  strategyMeta: ResultMeta | undefined;
  reportBundle: MacroObservationReportBundleView;
  runtimeSummary: string;
  deferredSectionLabels: string[];
}) {
  const caliberGroups = [
    { key: "analysis", title: "分析信封", rows: caliberSupplementRows(metaView.analysis) },
    { key: "strategy", title: "策略信封", rows: caliberSupplementRows(metaView.strategy) },
  ].filter((group) => group.rows.length);
  const failedCount = reportBundle.validationFailedCount;

  return (
    <div className="macro-observation-evidence" data-testid="macro-observation-evidence">
      <p
        className="macro-observation-evidence__runtime"
        aria-label="运行时状态"
        data-testid="macro-observation-evidence-runtime"
      >
        <strong>证据状态</strong>
        <span>{runtimeSummary}</span>
        {deferredSectionLabels.map((label) => (
          <span key={label} className="macro-observation-evidence__deferred-pill">
            {label}
          </span>
        ))}
      </p>

      {caliberGroups.length ? (
        <div
          className="macro-observation-evidence__caliber"
          data-testid="macro-observation-evidence-caliber"
        >
          {caliberGroups.map((group) => (
            <p
              key={group.key}
              className="macro-observation-evidence__caliber-group"
              aria-label={`${group.title}口径速读`}
            >
              <span className="macro-observation-evidence__caliber-title">{group.title}</span>
              {group.rows.map((row) => (
                <span key={row.key} className="macro-observation-evidence__caliber-row">
                  <span className="macro-observation-evidence__caliber-label">{row.label}</span>
                  <strong className="macro-observation-evidence__caliber-value">{row.value}</strong>
                  {row.note ? (
                    <small className="macro-observation-evidence__caliber-note">{row.note}</small>
                  ) : null}
                </span>
              ))}
            </p>
          ))}
        </div>
      ) : null}

      <FormalResultMetaPanel
        testId="macro-observation-meta-panel"
        sections={[
          { key: "analysis", title: "宏观分析信封", meta: analysisMeta },
          { key: "strategy", title: "策略摘要信封", meta: strategyMeta },
        ]}
      />

      <div
        className="macro-observation-evidence__bundle"
        aria-label="观察报告包"
        data-testid="macro-observation-report-bundle"
      >
        <div className="macro-observation-evidence__bundle-head">
          <span className="macro-observation-evidence__bundle-title">观察报告包</span>
          <span
            className="macro-observation-evidence__bundle-status"
            data-status={reportBundle.status}
          >
            {reportBundle.statusText}
          </span>
          <small className="macro-observation-evidence__bundle-validation">
            校验 {reportBundle.validationText}
          </small>
        </div>

        {reportBundle.downloadable && reportBundle.artifacts.length ? (
          <ul className="macro-observation-evidence__artifacts">
            {reportBundle.artifacts.map((artifact) => (
              <li key={artifact.id} className="macro-observation-evidence__artifact">
                <a
                  className="macro-observation-evidence__artifact-name"
                  href={artifact.downloadHref}
                  download={artifact.filename}
                  title={artifact.filename}
                >
                  {artifact.filename}
                </a>
                <small
                  className="macro-observation-evidence__artifact-label"
                  title={`${artifact.label} · ${artifact.kind}`}
                >
                  {artifact.label} · {artifact.kind}
                </small>
                <span className="macro-observation-evidence__artifact-size">
                  {artifact.sizeText}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          // mock 下 status=missing 是常态，用 muted 文案而非报错样式。
          <p className="macro-observation-evidence__bundle-reason">
            {reportBundle.reason ?? "发布清单返回后才会开放下载。"}
          </p>
        )}

        {failedCount > 0 ? (
          <p
            className="macro-observation-evidence__bundle-failed"
            data-testid="macro-observation-bundle-validation-warning"
          >
            {failedCount} 项校验未通过，使用报告前需先复核校验明细。
          </p>
        ) : null}
        {reportBundle.warningCount ? (
          <p className="macro-observation-evidence__bundle-warnings">
            警示 {reportBundle.warningCount} 条
          </p>
        ) : null}
      </div>
    </div>
  );
}
