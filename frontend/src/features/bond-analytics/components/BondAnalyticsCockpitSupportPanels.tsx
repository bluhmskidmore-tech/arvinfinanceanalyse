import { Button, Card } from "antd";
import { Link } from "react-router-dom";

import type {
  BondTopHoldingItem,
  ChoiceMacroLatestPoint,
  DV01RiskPayload,
} from "../../../api/contracts";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "../../../utils/choiceMacroFormat";
import {
  BOND_ANALYTICS_MACRO_BAR_SERIES,
  buildMacroPointForDeltaDisplay,
  coalesceMacroSeriesDelta,
} from "../lib/bondAnalyticsMacroSeries";
import { BOND_HOLDINGS_EMPTY_NOTE } from "../lib/bondHoldingsEvidenceCopy";
import { buildBondTradingDeskPath } from "../../bond-trading-desk/lib/bondTradingDeskPageModel";
import { EM_DASH } from "../../../utils/format";
import {
  buildReadoutFacts,
  formatDurationDisplay,
  formatMoneyDisplay,
  formatMoneyEvidenceDisplay,
  formatNumericEvidenceDisplay,
  formatNumericString,
  formatPctEvidenceDisplay,
  formatSignedPct,
  formatTextEvidenceDisplay,
  formatWanEvidenceDisplay,
} from "./bondAnalyticsCockpitFormat";
import {
  MobileReadoutField,
  SectionCardTitle,
} from "./BondAnalyticsCockpitPrimitives";
import { cardBodyStyle } from "./bondAnalyticsCockpitTokens";
import styles from "./BondAnalyticsInstitutionalCockpit.module.css";

const TOP_HOLDINGS_MOBILE_LABEL = "前十大持仓";
const TOP_HOLDINGS_HOME_NOTE = "前十大持仓暂未返回，首页先保留组合规模与浮盈快照。";

export type AccountingDv01SummaryRow = {
  label: string;
  value: string;
  payload: DV01RiskPayload | null;
};

function pickLargestDv01Row(rows: AccountingDv01SummaryRow[]) {
  let largest: AccountingDv01SummaryRow | null = null;
  let largestDv01 = Number.NEGATIVE_INFINITY;

  for (const row of rows) {
    const dv01 = bondNumericRaw(row.payload?.total_dv01);
    const rawDv01 = dv01 === null ? Number.NaN : Math.abs(dv01);
    if (Number.isFinite(rawDv01) && rawDv01 > largestDv01) {
      largest = row;
      largestDv01 = rawDv01;
    }
  }

  return largest;
}

function AccountingDv01MobileReadout({
  rows,
  isLoading,
  hasError,
}: {
  rows: AccountingDv01SummaryRow[];
  isLoading: boolean;
  hasError: boolean;
}) {
  const largestRow = pickLargestDv01Row(rows);
  const stateLabel = hasError ? "读面暂未返回" : isLoading ? "读取中" : "移动摘要";
  const largestDv01Display = largestRow
    ? formatWanEvidenceDisplay(largestRow.payload?.total_dv01)
    : hasError
      ? "读面暂未返回"
      : isLoading
        ? "读取中"
        : "暂无可用分类";

  return (
    <div
      data-testid="bond-analysis-accounting-dv01-mobile-readout"
      className={styles.mobileTableReadout}
    >
      <div className={styles.mobileReadoutHeader}>
        <span>会计分类 DV01</span>
        <strong>{stateLabel}</strong>
      </div>
      <div className={styles.mobileReadoutGrid}>
        <MobileReadoutField
          label="最高 DV01 分类"
          value={largestRow?.label ?? EM_DASH}
          detail={largestDv01Display}
        />
        <MobileReadoutField
          label="面值加权久期"
          value={formatDurationDisplay(largestRow?.payload?.face_weighted_modified_duration)}
        />
        <MobileReadoutField
          label="DV01"
          value={largestDv01Display}
        />
        <MobileReadoutField
          label="面值"
          value={formatMoneyDisplay(largestRow?.payload?.total_face_value)}
        />
        <MobileReadoutField
          label="持仓数"
          value={largestRow?.payload ? formatNumericString(largestRow.payload.position_count) : EM_DASH}
        />
      </div>
    </div>
  );
}

export function AccountingDv01SummaryPanel({
  rows,
  isLoading,
  hasError,
  onOpenModuleDetail,
}: {
  rows: AccountingDv01SummaryRow[];
  isLoading: boolean;
  hasError: boolean;
  onOpenModuleDetail?: (key: BondAnalyticsModuleKey) => void;
}) {
  return (
    <Card
      variant="borderless"
      size="small"
      title={<SectionCardTitle eyebrow="分类风险" title="会计分类 DV01" />}
      extra={
        <Button
          size="small"
          type="text"
          data-testid="bond-analysis-home-open-dv01-risk"
          onClick={() => onOpenModuleDetail?.("dv01-risk")}
        >
          打开 DV01 风险
        </Button>
      }
      data-testid="bond-analysis-accounting-dv01-summary"
      className={`${styles.dashboardCard} ${styles.accountingDv01Card}`}
      styles={{ body: { padding: 0 } }}
    >
      <AccountingDv01MobileReadout rows={rows} isLoading={isLoading} hasError={hasError} />
      <div
        data-testid="bond-analysis-accounting-dv01-raw-grid"
        className={styles.accountingDv01Grid}
      >
        <div className={styles.accountingDv01Header}>
          <span>分类</span>
          <span>面值加权久期</span>
          <span>DV01</span>
          <span>面值</span>
          <span>持仓数</span>
        </div>
        {rows.map((row) => (
          <div className={styles.accountingDv01Row} key={row.value}>
            <strong>{row.label}</strong>
            <span className={styles.accountingDv01Number}>{formatDurationDisplay(row.payload?.face_weighted_modified_duration)}</span>
            <span className={styles.accountingDv01Number}>{formatWanEvidenceDisplay(row.payload?.total_dv01)}</span>
            <span className={styles.accountingDv01Number}>{formatMoneyDisplay(row.payload?.total_face_value)}</span>
            <span className={styles.accountingDv01Number}>
              {row.payload ? formatNumericString(row.payload.position_count) : EM_DASH}
            </span>
          </div>
        ))}
      </div>
      {isLoading ? <div className={styles.accountingDv01Note}>分类 DV01 正在读取。</div> : null}
      {hasError ? <div className={styles.accountingDv01Note}>分类 DV01 读面暂未返回。</div> : null}
    </Card>
  );
}

export function HoldingsMobileReadout({
  holdings,
  unavailable,
  reportDate,
}: {
  holdings: BondTopHoldingItem[];
  unavailable: boolean;
  reportDate: string;
}) {
  const leadHolding = unavailable ? null : holdings[0] ?? null;
  const leadName = leadHolding
    ? leadHolding.instrument_name ?? leadHolding.instrument_code
    : unavailable
      ? "读面暂未返回"
      : "暂无持仓明细";
  const leadDetail = leadHolding ? (
    <Link
      to={buildBondTradingDeskPath(leadHolding.instrument_code, reportDate)}
      data-testid={`bond-trading-desk-link-${leadHolding.instrument_code}`}
    >
      {leadHolding.instrument_code}
    </Link>
  ) : undefined;
  const statusLabel = unavailable ? "读面暂未返回" : `${holdings.length} 只可见`;

  return (
    <div data-testid="bond-analysis-holdings-mobile-readout" className={styles.mobileTableReadout}>
      <div className={styles.mobileReadoutHeader}>
        <span>{TOP_HOLDINGS_MOBILE_LABEL}</span>
        <strong>{statusLabel}</strong>
      </div>
      <div className={styles.mobileReadoutGrid}>
        <MobileReadoutField label="最大持仓" value={leadName} detail={leadDetail} />
        <MobileReadoutField label="评级" value={formatTextEvidenceDisplay(leadHolding?.rating)} />
        <MobileReadoutField label="市值" value={formatMoneyEvidenceDisplay(leadHolding?.market_value)} />
        <MobileReadoutField label="收益率" value={formatPctEvidenceDisplay(leadHolding?.ytm)} />
        <MobileReadoutField label="久期" value={formatNumericEvidenceDisplay(leadHolding?.modified_duration)} />
        <MobileReadoutField label="权重" value={formatPctEvidenceDisplay(leadHolding?.weight)} />
      </div>
    </div>
  );
}

export function ReferenceMarketTicker({
  series,
  unavailable,
}: {
  series: ChoiceMacroLatestPoint[];
  unavailable: boolean;
}) {
  const byId = new Map(series.map((point) => [point.series_id, point]));
  const hasAnyLevel = BOND_ANALYTICS_MACRO_BAR_SERIES.some((item) => byId.has(item.series_id));

  return (
    <div data-testid="bond-analysis-market-ticker" className={styles.referenceMarketTicker}>
      {BOND_ANALYTICS_MACRO_BAR_SERIES.map((item) => {
        const point = byId.get(item.series_id);
        const delta = coalesceMacroSeriesDelta(point);
        const displayPoint = point ? buildMacroPointForDeltaDisplay(point, delta) : null;
        const tone =
          displayPoint?.latest_change == null
            ? "flat"
            : displayPoint.latest_change > 0
              ? "up"
              : displayPoint.latest_change < 0
                ? "down"
                : "flat";

        return (
          <div key={item.series_id} className={styles.referenceTickerCell}>
            <span>{item.shortLabel}</span>
            <strong>{point ? formatChoiceMacroValue(point, { spaceBeforeUnit: false }) : EM_DASH}</strong>
            <small data-tone={tone}>
              {displayPoint
                ? formatChoiceMacroDelta(displayPoint, {
                    emptyDisplay: unavailable || !hasAnyLevel ? "待读取" : EM_DASH,
                    spaceBeforeUnit: false,
                  })
                : unavailable || !hasAnyLevel
                  ? "待读取"
                  : EM_DASH}
            </small>
          </div>
        );
      })}
    </div>
  );
}

export function ReferenceJudgmentMatrix({
  duration,
  creditWeight,
  spreadMedianBp,
  dv01Display,
  hasDv01Readout,
  hasCurveReadout,
  marketValueMomPct,
}: {
  duration: number;
  creditWeight: number;
  spreadMedianBp: number;
  dv01Display: string;
  hasDv01Readout: boolean;
  hasCurveReadout: boolean;
  marketValueMomPct: number | null;
}) {
  const creditMissing = [
    Number.isFinite(spreadMedianBp) ? null : "信用利差",
    Number.isFinite(creditWeight) ? null : "信用占比",
  ].filter(Boolean);
  const rows = [
    {
      label: "利率证据",
      value: Number.isFinite(duration) ? "已返回" : "待返回",
      detail: Number.isFinite(duration) ? `返回字段：组合久期 ${duration.toFixed(2)} 年` : `返回字段：${EM_DASH}`,
      missing: Number.isFinite(duration) ? `缺失项：${EM_DASH}` : "缺失项：久期",
      isReturned: Number.isFinite(duration),
    },
    {
      label: "曲线证据",
      value: hasCurveReadout ? "正式曲线可读" : "正式曲线待返回",
      detail: hasCurveReadout ? "返回字段：期限点收益率与日变动" : "返回字段：期限桶仅作暴露观察",
      missing: hasCurveReadout ? "缺失项：正式 KRD" : "缺失项：正式曲线 / 正式 KRD",
      isReturned: hasCurveReadout,
    },
    {
      label: "信用证据",
      value: Number.isFinite(spreadMedianBp) || Number.isFinite(creditWeight) ? "已返回" : "待返回",
      detail: `返回字段：${buildReadoutFacts({ duration: Number.NaN, creditWeight, spreadMedianBp }).join(" · ") || EM_DASH}`,
      missing: `缺失项：${creditMissing.length > 0 ? creditMissing.join(" / ") : EM_DASH}`,
      isReturned: Number.isFinite(spreadMedianBp) || Number.isFinite(creditWeight),
    },
    {
      label: "资金证据",
      value: hasDv01Readout ? "DV01已返回" : "DV01待返回",
      detail: `返回字段：组合 DV01 ${dv01Display}`,
      missing: hasDv01Readout ? `缺失项：${EM_DASH}` : "缺失项：DV01",
      isReturned: hasDv01Readout,
    },
  ];

  return (
    <div data-testid="bond-analysis-judgment-matrix" className={styles.referenceJudgmentPanel}>
      <div className={styles.referenceEvidenceNotice}>
        <span>证据边界</span>
        <strong>只展示后端返回事实，不生成交易判断或风险阈值。</strong>
      </div>
      <div className={styles.referenceJudgmentMatrix}>
        {rows.map((row) => (
          <div
            key={row.label}
            className={styles.referenceJudgmentCard}
            data-readout-status={row.isReturned ? "returned" : "pending"}
          >
            <span>{row.label}</span>
            <strong>{row.value}</strong>
            <small>{row.detail}</small>
            <em>{row.missing}</em>
          </div>
        ))}
      </div>
      <div className={styles.strategyTagGrid}>
        <div>
          <span>组合久期</span>
          <strong>{Number.isFinite(duration) ? `${duration.toFixed(2)} 年` : EM_DASH}</strong>
        </div>
        <div>
          <span>市值环比</span>
          <strong>{formatSignedPct(marketValueMomPct)}</strong>
        </div>
        <div>
          <span>曲线状态</span>
          <strong>{hasCurveReadout ? "已返回" : "待返回"}</strong>
        </div>
        <div>
          <span>风险锚点</span>
          <strong>DV01事实</strong>
        </div>
        <div>
          <span>前端边界</span>
          <strong>只展示返回事实</strong>
        </div>
      </div>
    </div>
  );
}

export function ReferenceReturnAttributionPanel({
  actionPnlDisplay,
  actionPnlTone,
  actionCount,
  marketValueMomPct,
  dv01Mom,
  unrealizedPnlDisplay,
  unrealizedPnlMomPct,
  onOpenModuleDetail,
}: {
  actionPnlDisplay: string;
  actionPnlTone: "default" | "positive" | "negative";
  actionCount: number | null;
  marketValueMomPct: number | null;
  dv01Mom: number;
  unrealizedPnlDisplay: string;
  unrealizedPnlMomPct: number | null;
  onOpenModuleDetail?: (key: BondAnalyticsModuleKey) => void;
}) {
  return (
    <Card
      variant="borderless"
      size="small"
      title={<SectionCardTitle eyebrow="归因 / DV01" title="收益归因 / DV01 变动证据" />}
      data-testid="bond-analysis-return-attribution-panel"
      className={`${styles.referencePanelCard} ${styles.referenceAttributionCard}`}
      styles={{ body: cardBodyStyle }}
    >
      <div className={styles.referenceAttributionPanel}>
        <div className={styles.attributionLead}>
          <span>动作归因</span>
          <strong data-tone={actionPnlTone}>{actionPnlDisplay}</strong>
          <small>{actionCount !== null ? `${actionCount} 笔动作` : "动作归因待返回"}</small>
        </div>
        <div className={styles.footerChangeSplit}>
          <span>市值 {formatSignedPct(marketValueMomPct)}</span>
          <span>DV01 {Number.isFinite(dv01Mom) ? `${dv01Mom >= 0 ? "+" : ""}${(dv01Mom / 10000).toFixed(2)} 万` : EM_DASH}</span>
        </div>
        <div className={styles.attributionEvidenceGrid}>
          <div>
            <span>归因状态</span>
            <strong>{actionCount !== null ? "已返回" : "待返回"}</strong>
          </div>
          <div>
            <span>动作数</span>
            <strong>{actionCount !== null ? `${actionCount} 笔` : EM_DASH}</strong>
          </div>
          <div>
            <span>DV01变动</span>
            <strong>{Number.isFinite(dv01Mom) ? `${dv01Mom >= 0 ? "+" : ""}${(dv01Mom / 10000).toFixed(2)} 万` : EM_DASH}</strong>
          </div>
          <div>
            <span>市值环比</span>
            <strong>{formatSignedPct(marketValueMomPct)}</strong>
          </div>
        </div>
        <div className={styles.attributionLedger}>
          <div>
            <span>本期估值收益</span>
            <strong>{unrealizedPnlDisplay}</strong>
          </div>
          <div>
            <span>较上期</span>
            <strong>{formatSignedPct(unrealizedPnlMomPct)}</strong>
          </div>
        </div>
        <div className={styles.attributionBoundaryNote}>
          收益、动作与 DV01 仅按返回读面列示；未返回字段保持缺口，不在前端补算归因。
        </div>
        <Button size="small" type="text" data-testid="bond-analysis-home-open-action-attribution" onClick={() => onOpenModuleDetail?.("action-attribution")}>
          打开动作归因
        </Button>
      </div>
    </Card>
  );
}

export function HoldingRows({
  holdings,
  unavailable,
  reportDate,
}: {
  holdings: BondTopHoldingItem[];
  unavailable: boolean;
  reportDate: string;
}) {
  if (unavailable) {
    return <div className={styles.tableEmpty}>{TOP_HOLDINGS_HOME_NOTE}</div>;
  }

  if (holdings.length === 0) {
    return <div className={styles.tableEmpty}>{BOND_HOLDINGS_EMPTY_NOTE}</div>;
  }

  return (
    <div className={styles.holdingsTableRows}>
      {holdings.map((item) => (
        <div key={item.instrument_code} className={styles.holdingsTableRow}>
          <div className={styles.holdingNameCell}>
            <strong>{item.instrument_name ?? item.instrument_code}</strong>
            <Link
              to={buildBondTradingDeskPath(item.instrument_code, reportDate)}
              data-testid={`bond-trading-desk-link-${item.instrument_code}`}
            >
              {item.instrument_code}
            </Link>
          </div>
          <span>{item.asset_class}</span>
          <span>{formatTextEvidenceDisplay(item.rating)}</span>
          <span className={styles.holdingNumericCell}>{formatMoneyEvidenceDisplay(item.market_value)}</span>
          <span className={styles.holdingNumericCell}>{formatPctEvidenceDisplay(item.ytm)}</span>
          <span className={styles.holdingNumericCell}>{formatNumericEvidenceDisplay(item.modified_duration)}</span>
          <span className={styles.holdingNumericCell}>{formatPctEvidenceDisplay(item.weight)}</span>
        </div>
      ))}
    </div>
  );
}
