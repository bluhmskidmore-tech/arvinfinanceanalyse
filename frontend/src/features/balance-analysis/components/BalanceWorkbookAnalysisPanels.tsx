import type {
  BalanceAnalysisWorkbookOperationalSection,
  BalanceAnalysisWorkbookTable,
} from "../../../api/contracts";
import { PageStateSurface } from "../../../components/page/PagePrimitives";
import { EM_DASH } from "../../../utils/format";
import type { useBalanceAnalysisData } from "../hooks/useBalanceAnalysisData";
import {
  distributionChartBarWidthPercent,
  formatBalanceWorkbookCellDisplay,
  formatBalanceWorkbookMetricTwoDecimals,
  formatBalanceWorkbookWanAmountDisplay,
  gapChartBarWidthPercent,
  maxAbsFiniteChartScale,
  maxFiniteChartScale,
  parseBalanceChartMagnitude,
} from "../pages/balanceAnalysisPageModel";

// 评级块色板走 Nocturne 链（DOM 内联消费用 var；--nct-accent-* 亮阶在
// balance-analysis scope 的外壳块恒有定义），六档保持绿/紫/琥珀/亮紫/红/浅紫
// 的评级区分度。
const ratingBlockPalette = [
  "var(--dh-api-green)",
  "var(--dh-api-blue)",
  "var(--dh-api-amber)",
  "var(--nct-accent-400)",
  "var(--dh-api-red)",
  "var(--nct-accent-300)",
] as const;

export function renderWorkbookContractMismatch(
  table: Pick<BalanceAnalysisWorkbookTable, "key"> | Pick<BalanceAnalysisWorkbookOperationalSection, "key">,
  message: string,
) {
  return (
    <div
      data-testid={`balance-analysis-workbook-table-${table.key}`}
      className="balance-analysis-workbook-alert balance-analysis-workbook-alert--warning"
    >
      {message}
    </div>
  );
}

export function renderWorkbookEmptyState(message: string) {
  return (
    <div className="balance-analysis-workbook-alert balance-analysis-workbook-alert--empty">
      {message}
    </div>
  );
}

export function hasWorkbookFields(rows: Array<Record<string, unknown>>, requiredKeys: string[]) {
  if (rows.length === 0) {
    return true;
  }
  return rows.every((row) => requiredKeys.every((key) => row[key] !== undefined && row[key] !== null));
}

function renderDistributionPanel(
  table: BalanceAnalysisWorkbookTable,
  {
    labelKey,
    valueKey,
    color,
  }: {
    labelKey: string;
    valueKey: string;
    color: string;
  },
) {
  const rows = table.rows.slice(0, 6);
  if (!hasWorkbookFields(rows, [labelKey, valueKey])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：缺少主分布图所需字段。");
  }
  const maxAmong = maxFiniteChartScale(rows.map((row) => row[valueKey]));
  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} className="balance-analysis-mini-list">
      {rows.map((row, index) => {
        const mag = parseBalanceChartMagnitude(row[valueKey]);
        const widthPct = distributionChartBarWidthPercent(mag, maxAmong);
        const width = widthPct == null ? "0%" : `${widthPct}%`;
        return (
          <div key={`${table.key}-${index}`} className="balance-analysis-mini-row">
            <div className="balance-analysis-mini-topline">
              <span className="balance-analysis-mini-label">
                {formatBalanceWorkbookCellDisplay(row[labelKey])}
              </span>
              <span className="balance-analysis-mini-value">
                {formatBalanceWorkbookWanAmountDisplay(row[valueKey])}
              </span>
            </div>
            <div className="balance-analysis-mini-bar-track">
              <div
                data-testid={`balance-analysis-distribution-bar-${table.key}-${index}`}
                style={{
                  width,
                  background: color,
                }}
                className="balance-analysis-mini-bar-fill"
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function renderRatingPanel(table: BalanceAnalysisWorkbookTable) {
  const rows = table.rows.slice(0, 6);
  if (!hasWorkbookFields(rows, ["rating", "balance_amount"])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：评级分布字段不完整。");
  }
  const maxValue = maxFiniteChartScale(rows.map((row) => row.balance_amount));
  let hasFiniteTotal = false;
  let totalWan = 0;
  for (const row of table.rows) {
    const mag = parseBalanceChartMagnitude(row.balance_amount);
    if (mag.kind === "finite") {
      hasFiniteTotal = true;
      totalWan += mag.value;
    }
  }
  return (
    <div
      data-testid={`balance-analysis-workbook-table-${table.key}`}
      className="balance-analysis-rating-panel"
    >
      <div className="balance-analysis-rating-panel__grid">
        {rows.map((row, index) => {
          const mag = parseBalanceChartMagnitude(row.balance_amount);
          const ratio = mag.kind === "finite" ? Math.max(0.35, mag.value / maxValue) : 0.35;
          return (
            <article
              key={`${table.key}-${index}`}
              className="balance-analysis-rating-card"
              style={{
                background: ratingBlockPalette[index % ratingBlockPalette.length],
                opacity: 0.55 + ratio * 0.45,
              }}
            >
              <div className="balance-analysis-rating-card__label">{formatBalanceWorkbookCellDisplay(row.rating)}</div>
              <div className="balance-analysis-rating-card__value">
                {formatBalanceWorkbookWanAmountDisplay(row.balance_amount)}
              </div>
            </article>
          );
        })}
      </div>
      <div className="balance-analysis-rating-reconciliation">
        <span className="balance-analysis-rating-reconciliation__total">
          评级合计 {hasFiniteTotal ? formatBalanceWorkbookWanAmountDisplay(totalWan) : "未取到"}
        </span>
        <span className="balance-analysis-rating-reconciliation__note">
          Workbook 原币面值口径，合计对齐债券资产卡片；不等同于页面 CNY 市值或 CNX 总账控制数。
        </span>
      </div>
    </div>
  );
}

function renderMaturityGapPanel(table: BalanceAnalysisWorkbookTable) {
  const rows = table.rows.slice(0, 6);
  if (!hasWorkbookFields(rows, ["bucket", "gap_amount"])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：期限缺口字段不完整。");
  }
  const maxAbs = maxAbsFiniteChartScale(rows.map((row) => row.gap_amount));
  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} className="balance-analysis-mini-list balance-analysis-mini-list--tight">
      {rows.map((row, index) => {
        const mag = parseBalanceChartMagnitude(row.gap_amount);
        const widthPct = gapChartBarWidthPercent(mag, maxAbs);
        const width = widthPct == null ? "0%" : `${widthPct}%`;
        const positive = mag.kind === "finite" ? mag.value >= 0 : true;
        return (
          <article
            key={`${table.key}-${index}`}
            className="balance-analysis-gap-card"
            data-direction={positive ? "positive" : "negative"}
          >
            <div className="balance-analysis-mini-topline">
              <div className="balance-analysis-mini-label balance-analysis-mini-label--strong">
                {formatBalanceWorkbookCellDisplay(row.bucket)}
              </div>
              <div
                className={`balance-analysis-mini-value balance-analysis-mini-value--${positive ? "info" : "warning"}`}
              >
                {formatBalanceWorkbookWanAmountDisplay(row.gap_amount)}
              </div>
            </div>
            <div className="balance-analysis-mini-bar-track">
              <div
                data-testid={`balance-analysis-maturity-gap-bar-${table.key}-${index}`}
                style={{
                  width,
                  background: positive ? "var(--ib-accent)" : "var(--ib-warn)",
                }}
                className="balance-analysis-mini-bar-fill"
              />
            </div>
            {!positive ? (
              <div className="balance-analysis-gap-note">
                负缺口，应优先结合右侧治理信号处理。
              </div>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}

function renderIssuancePanel(table: BalanceAnalysisWorkbookTable) {
  const rows = table.rows.slice(0, 4);
  if (!hasWorkbookFields(rows, ["bond_type", "balance_amount"])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：发行类分析字段不完整。");
  }
  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} className="balance-analysis-mini-list">
      {rows.map((row, index) => (
        <article
          key={`${table.key}-${index}`}
          className="balance-analysis-ledger-card"
        >
          <div className="balance-analysis-mini-topline">
            <div className="balance-analysis-mini-label balance-analysis-mini-label--strong">{formatBalanceWorkbookCellDisplay(row.bond_type)}</div>
            <div className="balance-analysis-mini-value balance-analysis-mini-value--info">
              {formatBalanceWorkbookWanAmountDisplay(row.balance_amount)}
            </div>
          </div>
          <div className="balance-analysis-ledger-meta-row">
            <span>笔数 {formatBalanceWorkbookCellDisplay(row.count)}</span>
            <span>利率 {formatBalanceWorkbookMetricTwoDecimals(row.weighted_rate_pct)}</span>
            <span>期限 {formatBalanceWorkbookMetricTwoDecimals(row.weighted_term_years)}</span>
          </div>
        </article>
      ))}
    </div>
  );
}

export function renderWorkbookPrimaryPanel(table: BalanceAnalysisWorkbookTable) {
  if (table.key === "bond_business_types") {
    return renderDistributionPanel(table, {
      labelKey: "bond_type",
      valueKey: "balance_amount",
      color: "var(--ib-accent)",
    });
  }
  if (table.key === "rating_analysis") {
    return renderRatingPanel(table);
  }
  if (table.key === "maturity_gap") {
    return renderMaturityGapPanel(table);
  }
  if (table.key === "issuance_business_types") {
    return renderIssuancePanel(table);
  }
  return null;
}

function renderIndustryPanel(table: BalanceAnalysisWorkbookTable) {
  return renderDistributionPanel(table, {
    labelKey: "industry_name",
    valueKey: "balance_amount",
    color: "var(--ib-accent)",
  });
}

function renderRateDistributionPanel(table: BalanceAnalysisWorkbookTable) {
  const rows = table.rows.slice(0, 5);
  if (!hasWorkbookFields(rows, [
    "bucket",
    "bond_amount",
    "interbank_asset_amount",
    "interbank_liability_amount",
  ])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：利率分布字段不完整。");
  }

  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} className="balance-analysis-mini-list">
      {rows.map((row, index) => (
        <article
          key={`${table.key}-${index}`}
          className="balance-analysis-ledger-card"
        >
          <div className="balance-analysis-mini-label balance-analysis-mini-label--strong">{formatBalanceWorkbookCellDisplay(row.bucket)}</div>
          <div className="balance-analysis-rate-grid">
            <div>
              <div className="balance-analysis-rate-grid__label">债券</div>
              <div className="balance-analysis-mini-value balance-analysis-mini-value--info">
                {formatBalanceWorkbookWanAmountDisplay(row.bond_amount)}
              </div>
            </div>
            <div>
              <div className="balance-analysis-rate-grid__label">同业资产</div>
              <div className="balance-analysis-mini-value balance-analysis-mini-value--success">
                {formatBalanceWorkbookWanAmountDisplay(row.interbank_asset_amount)}
              </div>
            </div>
            <div>
              <div className="balance-analysis-rate-grid__label">同业负债</div>
              <div className="balance-analysis-mini-value balance-analysis-mini-value--warning-soft">
                {formatBalanceWorkbookWanAmountDisplay(row.interbank_liability_amount)}
              </div>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}

function renderCounterpartyPanel(table: BalanceAnalysisWorkbookTable) {
  const rows = table.rows.slice(0, 4);
  if (!hasWorkbookFields(rows, [
    "counterparty_type",
    "asset_amount",
    "liability_amount",
    "net_position_amount",
  ])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：对手方类型字段不完整。");
  }

  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} className="balance-analysis-mini-list">
      {rows.map((row, index) => (
        <article
          key={`${table.key}-${index}`}
          className="balance-analysis-ledger-card"
        >
          <div className="balance-analysis-mini-label balance-analysis-mini-label--strong">{formatBalanceWorkbookCellDisplay(row.counterparty_type)}</div>
          <div className="balance-analysis-ledger-meta-row">
            <span className="balance-analysis-mini-value--info">
              资产 {formatBalanceWorkbookWanAmountDisplay(row.asset_amount)}
            </span>
            <span className="balance-analysis-mini-value--warning-soft">
              负债 {formatBalanceWorkbookWanAmountDisplay(row.liability_amount)}
            </span>
            <span className="balance-analysis-mini-value--net">
              净头寸 {formatBalanceWorkbookWanAmountDisplay(row.net_position_amount)}
            </span>
          </div>
        </article>
      ))}
    </div>
  );
}

export function renderWorkbookSecondaryPanel(table: BalanceAnalysisWorkbookTable) {
  if (table.key === "industry_distribution") {
    return renderIndustryPanel(table);
  }
  if (table.key === "rate_distribution") {
    return renderRateDistributionPanel(table);
  }
  if (table.key === "counterparty_types") {
    return renderCounterpartyPanel(table);
  }
  return null;
}

export function renderDistributionEvidence(
  evidence: ReturnType<typeof useBalanceAnalysisData>["distributionEvidence"]["bond_business_types"],
  tableKey: string,
) {
  return (
    <div data-testid={`balance-analysis-distribution-evidence-${tableKey}`}>
      <p className="balance-analysis-workbook-panel__note" title={`来源版本：${evidence.meta?.source_version ?? EM_DASH}`}>
        来源：{evidence.source} · 实际报告日：{evidence.reportDate}
      </p>
      {evidence.stateSurfaces.map((state) => (
        <PageStateSurface key={state.key} variant={state.variant} title={state.title} description={state.description} />
      ))}
    </div>
  );
}
