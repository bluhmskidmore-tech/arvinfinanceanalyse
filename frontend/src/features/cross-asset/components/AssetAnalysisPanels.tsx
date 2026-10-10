import type { ResultMeta } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import {
  crossAssetAssetDirectionLabel,
  type CrossAssetBondTransmissionJudgment,
  CrossAssetClassAnalysisLine,
  CrossAssetClassAnalysisRow,
  CrossAssetEquityEvidenceItem,
  CrossAssetStatusFlag,
} from "../lib/crossAssetDriversPageModel";

function resultMetaQualityLabel(value: string | null | undefined): string {
  if (value === "ok") return "正常";
  if (value === "warning") return "预警";
  if (value === "error") return "错误";
  if (value === "stale") return "陈旧";
  return value ?? "待定";
}

function compactGeneratedAt(value: string | null | undefined): string {
  if (!value) return "待定";
  const clock = value.match(/T(\d{2}:\d{2})/);
  return clock?.[1] ?? value;
}

function compactStatusFlagDetail(flag: CrossAssetStatusFlag): string {
  if (flag.id === "analytical-only") return "分析链路";
  if (flag.id === "fallback") return "置信下调";
  if (flag.id === "dual-source") return "Choice+公共";
  if (flag.id === "stale") return "确认日期";
  if (flag.id === "source-blocked") return "来源受限";
  if (flag.id === "choice-source-missing") return "Choice 缺口";
  if (flag.id === "loading-failure") return "加载失败";
  if (flag.id === "access-denied") return "权限受限";
  if (flag.id === "linkage-quality-warning") return "联动预警";
  if (flag.id === "no-data") return "暂无数据";
  return flag.detail;
}

export function CrossAssetReviewQueue({
  statusFlags,
  latestMeta,
  linkageMeta,
  isLoading,
}: {
  statusFlags: CrossAssetStatusFlag[];
  latestMeta?: ResultMeta;
  linkageMeta?: ResultMeta;
  isLoading?: boolean;
}) {
  const warningLabel = statusFlags.length > 0 ? `${statusFlags.length} 项提示` : "暂无阻断";
  const firstWarning = statusFlags[0];
  const fallbackFlag = statusFlags.find((flag) => flag.id === "fallback");

  return (
    <aside className="cross-asset-review-queue" data-testid="cross-asset-review-queue" aria-label="待复核队列">
      <div className="cross-asset-review-queue__head">
        <span>复核队列</span>
        <h2>待复核队列</h2>
      </div>
      {/* 宏观/联动质量正文只在来源审计与数据状态明细各出现一次（§6 去重），此处降为指引。 */}
      <dl className="cross-asset-review-queue__list">
        <div>
          <dt>数据质量</dt>
          <dd>
            <strong>见数据状态</strong>
            <span
              title={`宏观质量 ${resultMetaQualityLabel(latestMeta?.quality_flag)} · 联动质量 ${resultMetaQualityLabel(linkageMeta?.quality_flag)}`}
            >
              {compactGeneratedAt(latestMeta?.generated_at)}
            </span>
          </dd>
        </div>
        <div>
          <dt>降级与提示</dt>
          <dd>
            <strong>{warningLabel}</strong>
            <span>{fallbackFlag ? compactStatusFlagDetail(fallbackFlag) : firstWarning ? compactStatusFlagDetail(firstWarning) : "状态正常"}</span>
          </dd>
        </div>
        <div>
          <dt>执行边界</dt>
          <dd>
            <strong>仅分析口径</strong>
            <span>{isLoading ? "等待数据返回" : "不替代交易指令"}</span>
          </dd>
        </div>
      </dl>
    </aside>
  );
}

const UI = {
  verdictKicker: "跨资产结论",
  verdictDescription:
    "双数据来源口径：Choice 接入码与 Tushare/公共补充源并列展示；已接入证据进入主判断，缺口收敛到待接入清单。",
  readyJudgment: "已形成判断",
  bondTransmissionJudgment: "债券传导判断",
  pendingList: "待接入清单",
  pendingNote:
    "期权、波动率和部分商品链条仍按待确认处理；缺口优先补 Choice 接入码，也可接 Tushare/公共补充治理源，不用相邻资产替代。",
  stock: "股票",
  commodity: "商品",
  options: "期权",
  pending: "待接入",
  dataReady: "数据可用",
  inputPending: "输入待接入",
  joiner: "，",
  items: "项",
} as const;

function analysisStatusLabel(status: CrossAssetClassAnalysisRow["status"]) {
  return status === "ready" ? UI.dataReady : UI.inputPending;
}

function lineStatusLabel(stateLabel: CrossAssetClassAnalysisLine["stateLabel"]) {
  const labels: Record<CrossAssetClassAnalysisLine["stateLabel"], string> = {
    ready: "已就绪",
    stale: "可能陈旧",
    source_blocked: "来源受限",
    missing_dependency: "缺少依赖",
    pending_definition: "定义待确认",
  };
  return labels[stateLabel];
}

function evidenceStatusLabel(status: CrossAssetEquityEvidenceItem["status"]) {
  const labels: Record<CrossAssetEquityEvidenceItem["status"], string> = {
    ready: "已就绪",
    stale: "可能陈旧",
    fallback: "降级",
    source_blocked: "来源受限",
    missing_dependency: "缺少依赖",
  };
  return labels[status];
}

function directionClassName(direction: string) {
  const normalized = direction.toLowerCase();
  if (normalized.includes("supportive")) {
    return "supportive";
  }
  if (normalized.includes("restrictive")) {
    return "restrictive";
  }
  if (normalized.includes("conflicted")) {
    return "conflicted";
  }
  if (normalized.includes("pending") || normalized.includes("definition")) {
    return "pending";
  }
  return "neutral";
}

export function AssetClassAnalysisPanel({
  rows,
  equityEvidenceItems,
  bondJudgment,
}: {
  rows: CrossAssetClassAnalysisRow[];
  equityEvidenceItems: CrossAssetEquityEvidenceItem[];
  bondJudgment: CrossAssetBondTransmissionJudgment;
}) {
  const stockRow = rows.find((row) => row.key === "stock");
  const commodityRow = rows.find((row) => row.key === "commodities");
  const optionsRow = rows.find((row) => row.key === "options");
  const readyRows = rows.filter((row) => row.status === "ready");
  const primaryRows = readyRows;
  const pendingGroups = rows
    .map((row) => ({
      row,
      lines: row.lines.filter((line) => line.status !== "ready"),
    }))
    .filter((group) => group.lines.length > 0);
  const pendingLineCount = pendingGroups.reduce((count, group) => count + group.lines.length, 0);
  const verdictParts = [
    stockRow ? `${UI.stock}${crossAssetAssetDirectionLabel(stockRow.direction)}` : "",
    commodityRow ? `${UI.commodity}${crossAssetAssetDirectionLabel(commodityRow.direction)}` : "",
    optionsRow ? `${UI.options}${optionsRow.status === "ready" ? crossAssetAssetDirectionLabel(optionsRow.direction) : UI.pending}` : "",
  ].filter(Boolean);

  return (
    <section data-testid="cross-asset-asset-class-analysis" className="cross-asset-class-analysis">
      <div className="cross-asset-class-analysis__header">
        <div className="cross-asset-class-analysis__eyebrow">{UI.verdictKicker}</div>
        <h2 className="cross-asset-class-analysis__title">{verdictParts.join(UI.joiner)}</h2>
        <p className="cross-asset-class-analysis__description">{UI.verdictDescription}</p>
      </div>
      <div className="cross-asset-class-analysis__body">
        <div className="cross-asset-class-analysis__primary">
          <div className="cross-asset-class-analysis__judgment" data-testid="cross-asset-asset-class-judgment">
            <div className="cross-asset-class-analysis__judgment-kicker">{UI.bondTransmissionJudgment}</div>
            <h3 className="cross-asset-class-analysis__judgment-title">{bondJudgment.headline}</h3>
            <p className="cross-asset-class-analysis__judgment-summary">{bondJudgment.summary}</p>
            <div className="cross-asset-class-analysis__judgment-items">
              {bondJudgment.items.map((item) => (
                <div key={item.key} className="cross-asset-class-analysis__judgment-item">
                  <div className="cross-asset-class-analysis__judgment-item-head">
                    <span>{item.label}</span>
                    <strong className={`cross-asset-class-analysis__judgment-tone cross-asset-class-analysis__direction--${directionClassName(item.direction)}`}>
                      {item.tone}
                    </strong>
                  </div>
                  <p>{item.detail}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <details open className="cross-asset-class-analysis__details" data-testid="cross-asset-asset-class-details">
          <summary>
            <span>资产明细与待接入清单</span>
            <strong>{readyRows.length}/{rows.length} 已判断 · {pendingLineCount} 项待接入</strong>
          </summary>
          <div className="cross-asset-class-analysis__details-body">
            <div className="cross-asset-class-analysis__primary-details">
              <div className="cross-asset-class-analysis__column-head">
                <span>{UI.readyJudgment}</span>
                <span>{readyRows.length}/{rows.length}</span>
              </div>
              {primaryRows.length === 0 ? (
                <p className="cross-asset-class-analysis__cards-empty">暂无已形成判断，待接入项见右列。</p>
              ) : null}
              <div className="cross-asset-class-analysis__cards">
                {primaryRows.map((row) => (
                  <article key={row.key} data-testid={`cross-asset-asset-analysis-${row.key}`} className="cross-asset-class-analysis__card">
                    <div className="cross-asset-class-analysis__card-header">
                      <div>
                        <div className="cross-asset-class-analysis__card-title">{row.label}</div>
                        <div className="cross-asset-class-analysis__card-subtitle">{analysisStatusLabel(row.status)}</div>
                      </div>
                      <span className={`cross-asset-class-analysis__direction cross-asset-class-analysis__direction--${directionClassName(row.direction)}`}>
                        {crossAssetAssetDirectionLabel(row.direction)}
                      </span>
                    </div>
                    <p className="cross-asset-class-analysis__summary">{row.explanation}</p>
                    <div className="cross-asset-class-analysis__lines">
                      {row.lines.map((line) => (
                        <div
                          key={line.key}
                          data-testid={`cross-asset-asset-analysis-${row.key}-${line.key}`}
                          className={`cross-asset-class-analysis__line${line.status === "ready" ? "" : " cross-asset-class-analysis__line--pending"}`}
                        >
                          <div className="cross-asset-class-analysis__line-header">
                            <span className="cross-asset-class-analysis__line-title">{line.label}</span>
                            <span className="cross-asset-class-analysis__line-status">{lineStatusLabel(line.stateLabel)}</span>
                          </div>
                          <div className="cross-asset-class-analysis__line-source" title={line.sourceLabel}>
                            <strong>{line.dataLabel}</strong>
                          </div>
                          <p className="cross-asset-class-analysis__line-explanation">{line.explanation}</p>
                        </div>
                      ))}
                    </div>
                    {row.key === "stock" ? (
                      <div className="cross-asset-class-analysis__evidence" data-testid="cross-asset-equity-evidence">
                        {equityEvidenceItems.map((item) => (
                          <div
                            key={item.key}
                            className={`cross-asset-class-analysis__evidence-item${item.status === "ready" ? "" : ` cross-asset-class-analysis__evidence-item--${item.status}`}`}
                            data-testid={`cross-asset-equity-evidence-${item.key}`}
                            title={item.sourceLabel}
                          >
                            <span>{item.label}</span>
                            <strong>
                              {item.valueLabel}
                              {item.unitLabel !== EM_DASH && !item.valueLabel.endsWith(item.unitLabel)
                                ? ` ${item.unitLabel}`
                                : ""}
                            </strong>
                            {/* §7 `·` 配额：状态/变化一行，日期/来源一行。 */}
                            <small>
                              {evidenceStatusLabel(item.status)} · {item.changeLabel}
                            </small>
                            <small>
                              {item.tradeDate ?? EM_DASH} · {item.sourceLabel}
                            </small>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            </div>

            <aside className="cross-asset-class-analysis__pending">
              <div className="cross-asset-class-analysis__column-head">
                <span>{UI.pendingList}</span>
                <span>{pendingLineCount} {UI.items}</span>
              </div>
              {pendingGroups.map(({ row, lines }) => {
                const hasPrimaryCard = primaryRows.some((primaryRow) => primaryRow.key === row.key);
                const testIdSuffix = hasPrimaryCard ? "-pending" : "";
                return (
                  <article key={row.key} data-testid={`cross-asset-asset-analysis-${row.key}${testIdSuffix}`} className="cross-asset-class-analysis__pending-card">
                    <div className="cross-asset-class-analysis__card-header">
                      <div>
                        <div className="cross-asset-class-analysis__card-title">{row.label}</div>
                        <div className="cross-asset-class-analysis__card-subtitle">{analysisStatusLabel(row.status)}</div>
                      </div>
                      <span className="cross-asset-class-analysis__direction cross-asset-class-analysis__direction--pending">
                        {UI.pending}
                      </span>
                    </div>
                    <p className="cross-asset-class-analysis__summary">{row.explanation}</p>
                    <div className="cross-asset-class-analysis__pending-lines">
                      {lines.map((line) => (
                        <div
                          key={line.key}
                          data-testid={`cross-asset-asset-analysis-${row.key}-${line.key}${testIdSuffix}`}
                          className="cross-asset-class-analysis__pending-line"
                          title={line.sourceLabel}
                        >
                          <span>{line.label}</span>
                          <span>{crossAssetAssetDirectionLabel(line.direction)}</span>
                          <small>
                            {lineStatusLabel(line.stateLabel)} · {line.dataLabel}
                          </small>
                        </div>
                      ))}
                    </div>
                  </article>
                );
              })}
              <p className="cross-asset-class-analysis__pending-note">{UI.pendingNote}</p>
            </aside>
          </div>
        </details>
      </div>
    </section>
  );
}
