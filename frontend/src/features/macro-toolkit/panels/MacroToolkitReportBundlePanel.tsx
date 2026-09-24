import type { MacroToolkitReportBundle } from "../../../api/macroToolkitClient";

import "./MacroToolkitReportBundlePanel.css";

type MacroToolkitReportBundlePanelProps = {
  bundle?: MacroToolkitReportBundle;
};

function formatAssetSize(sizeBytes: number): string {
  if (sizeBytes >= 1_000_000) {
    return `${(sizeBytes / 1_000_000).toFixed(1)} MB`;
  }
  if (sizeBytes >= 1_000) {
    return `${Math.round(sizeBytes / 1_000)} KB`;
  }
  return `${sizeBytes} B`;
}

export function MacroToolkitReportBundlePanel({ bundle }: MacroToolkitReportBundlePanelProps) {
  const status = bundle?.status ?? "missing";
  const ready =
    status === "ready" &&
    bundle?.observation_only === true &&
    bundle.formal_use_allowed === false;
  const validation = bundle?.validation;
  const validationTotal = validation ? validation.passed + validation.failed : 0;
  const unavailableMessage = status === "invalid" ? "资产校验失败，下载已关闭" : "报告资产尚未发布";

  return (
    <section
      className={`macro-toolkit-report-bundle macro-toolkit-report-bundle--${status}`}
      aria-label="宏观策略报告资产"
      data-testid="macro-toolkit-report-bundle"
    >
      <header className="macro-toolkit-report-bundle__head">
        <div>
          <span>研究材料包</span>
          <strong>{bundle?.title ?? "2026 中国宏观与利率策略"}</strong>
          <small>经清单与哈希校验的只读研究材料；下载前将重新校验清单与哈希。</small>
        </div>
        <div className="macro-toolkit-report-bundle__badges" aria-label="报告资产口径">
          <span>研究级只读</span>
          <span>非正式口径</span>
        </div>
      </header>

      {ready ? (
        <>
          <div className="macro-toolkit-report-bundle__metrics" aria-label="报告资产日期与校验状态">
            <div>
              <span>材料日</span>
              <strong>{bundle.as_of_date ?? "缺失"}</strong>
            </div>
            <div>
              <span>曲线日</span>
              <strong>{bundle.curve_date ?? "缺失"}</strong>
            </div>
            <div>
              <span>账户日</span>
              <strong>{bundle.account_report_date ?? "缺失"}</strong>
            </div>
            <div>
              <span>一致性校验</span>
              <strong>
                {validation?.passed ?? 0}/{validationTotal}
              </strong>
            </div>
          </div>
          <div className="macro-toolkit-report-bundle__scope">
            <strong>校验范围</strong>
            <span>{validation?.scope ?? "校验范围未提供"}</span>
          </div>
          {bundle.warnings.length ? (
            <div className="macro-toolkit-report-bundle__warnings" role="note">
              {bundle.warnings.map((warning) => (
                <span key={warning}>{warning}</span>
              ))}
            </div>
          ) : null}
          <div className="macro-toolkit-report-bundle__artifacts" aria-label="报告资产下载列表">
            {bundle.artifacts.map((artifact) => (
              <a
                key={artifact.id}
                href={`/ui/macro/toolkit/report-bundle/${encodeURIComponent(artifact.id)}`}
                download={artifact.filename}
                aria-label={`下载${artifact.label}`}
              >
                <span>{artifact.label}</span>
                <strong>{artifact.filename}</strong>
                <small>{formatAssetSize(artifact.size_bytes)}</small>
              </a>
            ))}
          </div>
        </>
      ) : (
        <div className="macro-toolkit-report-bundle__unavailable" role="status">
          <strong>{unavailableMessage}</strong>
          <span>{bundle?.warnings[0] ?? "发布清单返回后才会开放下载。"}</span>
        </div>
      )}
    </section>
  );
}
