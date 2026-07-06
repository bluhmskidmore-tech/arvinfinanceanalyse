import type { ResultMeta } from "../../../api/contracts";
import type {
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
      <dl className="cross-asset-review-queue__list">
        <div>
          <dt>宏观质量</dt>
          <dd>
            <strong>{resultMetaQualityLabel(latestMeta?.quality_flag)}</strong>
            <span>{compactGeneratedAt(latestMeta?.generated_at)}</span>
          </dd>
        </div>
        <div>
          <dt>联动质量</dt>
          <dd>
            <strong>{resultMetaQualityLabel(linkageMeta?.quality_flag)}</strong>
            <span>{compactGeneratedAt(linkageMeta?.generated_at)}</span>
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
  supportive: "支撑",
  restrictive: "压制",
  neutral: "中性",
  conflicted: "分歧",
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

function assetDirectionLabel(direction: string) {
  const normalized = direction.toLowerCase();
  if (normalized.includes("supportive")) {
    return UI.supportive;
  }
  if (normalized.includes("restrictive")) {
    return UI.restrictive;
  }
  if (normalized.includes("neutral")) {
    return UI.neutral;
  }
  if (normalized.includes("conflicted")) {
    return UI.conflicted;
  }
  if (normalized.includes("pending") || normalized.includes("definition")) {
    return UI.pending;
  }
  return direction;
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

function resolveAssetBondJudgmentHeadline(stockTone: string, commodityTone: string, pendingLineCount: number) {
  if (stockTone === UI.restrictive && commodityTone === UI.neutral) {
    return "股票链条压制风险偏好，商品链条暂不强化通胀交易。";
  }
  if (stockTone === UI.restrictive && commodityTone === UI.supportive) {
    return "风险偏好承压但商品仍有通胀扰动，债券判断需看利率主线确认。";
  }
  if (stockTone === UI.supportive && commodityTone === UI.neutral) {
    return "风险偏好改善，商品端中性，债券压力暂不来自跨资产共振。";
  }
  if (pendingLineCount > 0) {
    return "已接入信号先约束风险偏好与通胀方向，待接入项只限定置信度。";
  }
  return "跨资产证据可进入债券传导判断，继续跟踪方向共振。";
}

function buildAssetBondJudgment(input: {
  stockRow: CrossAssetClassAnalysisRow | undefined;
  commodityRow: CrossAssetClassAnalysisRow | undefined;
  optionsRow: CrossAssetClassAnalysisRow | undefined;
  pendingLineCount: number;
}) {
  const stockTone = input.stockRow ? assetDirectionLabel(input.stockRow.direction) : UI.pending;
  const commodityTone = input.commodityRow ? assetDirectionLabel(input.commodityRow.direction) : UI.pending;
  const optionsTone = input.optionsRow?.status === "ready" ? assetDirectionLabel(input.optionsRow.direction) : UI.pending;
  const boundary =
    input.pendingLineCount > 0
      ? `当前仍有 ${input.pendingLineCount} 项待接入，缺口只降低结论置信度，不用相邻资产替代。`
      : "当前待接入缺口较少，可更直接追踪跨资产共振对债券的传导。";

  return {
    headline: resolveAssetBondJudgmentHeadline(stockTone, commodityTone, input.pendingLineCount),
    summary: `${input.stockRow?.label ?? UI.stock}${stockTone}${UI.joiner}${input.commodityRow?.label ?? UI.commodity}${commodityTone}${UI.joiner}${input.optionsRow?.label ?? UI.options}${optionsTone}。${boundary}`,
    items: [
      {
        key: "stock",
        label: input.stockRow?.label ?? UI.stock,
        tone: stockTone,
        direction: input.stockRow?.direction ?? "pending",
        detail: input.stockRow?.explanation ?? "股票链条暂无治理后输入，不进入债券主判断。",
      },
      {
        key: "commodities",
        label: input.commodityRow?.label ?? UI.commodity,
        tone: commodityTone,
        direction: input.commodityRow?.direction ?? "pending",
        detail: input.commodityRow?.explanation ?? "商品链条暂无治理后输入，不放大通胀或需求判断。",
      },
      {
        key: "options",
        label: input.optionsRow?.label ?? UI.options,
        tone: optionsTone,
        direction: input.optionsRow?.status === "ready" ? input.optionsRow.direction : "pending",
        detail:
          input.optionsRow?.status === "ready"
            ? input.optionsRow.explanation
            : "期权和波动率口径尚在待接入清单，只作为风险信号缺口提示。",
      },
    ],
  };
}

export function AssetClassAnalysisPanel({
  rows,
  equityEvidenceItems,
}: {
  rows: CrossAssetClassAnalysisRow[];
  equityEvidenceItems: CrossAssetEquityEvidenceItem[];
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
    stockRow ? `${UI.stock}${assetDirectionLabel(stockRow.direction)}` : "",
    commodityRow ? `${UI.commodity}${assetDirectionLabel(commodityRow.direction)}` : "",
    optionsRow ? `${UI.options}${optionsRow.status === "ready" ? assetDirectionLabel(optionsRow.direction) : UI.pending}` : "",
  ].filter(Boolean);
  const bondJudgment = buildAssetBondJudgment({ stockRow, commodityRow, optionsRow, pendingLineCount });

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
              <div className="cross-asset-class-analysis__cards">
                {primaryRows.map((row) => (
                  <article key={row.key} data-testid={`cross-asset-asset-analysis-${row.key}`} className="cross-asset-class-analysis__card">
                    <div className="cross-asset-class-analysis__card-header">
                      <div>
                        <div className="cross-asset-class-analysis__card-title">{row.label}</div>
                        <div className="cross-asset-class-analysis__card-subtitle">{analysisStatusLabel(row.status)}</div>
                      </div>
                      <span className={`cross-asset-class-analysis__direction cross-asset-class-analysis__direction--${directionClassName(row.direction)}`}>
                        {assetDirectionLabel(row.direction)}
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
                            <strong>{item.valueLabel}</strong>
                            <small>
                              {evidenceStatusLabel(item.status)} · {item.changeLabel} · {item.unitLabel} · {item.tradeDate ?? "—"} · {item.sourceLabel}
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
                          <span>{assetDirectionLabel(line.direction)}</span>
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
