import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import type {
  CreditSpreadMigrationResponse,
  KRDCurveRiskResponse,
} from "../bond-analytics/types";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { PlaceholderCard } from "../workbench/components/PlaceholderCard";

/** 默认报告日；也可通过 URL `?report_date=YYYY-MM-DD` 覆盖。 */
const DEFAULT_REPORT_DATE = "2025-12-31";

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 16,
} as const;

const controlBarStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: 12,
  alignItems: "center",
  marginBottom: 20,
} as const;

const tableShellStyle = {
  overflowX: "auto",
  borderRadius: 16,
  border: "1px solid #e4ebf5",
  background: "#ffffff",
  marginTop: 18,
} as const;

const tableStyle = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 13,
} as const;

const thStyle = {
  textAlign: "left" as const,
  padding: "10px 12px",
  borderBottom: "1px solid #e4ebf5",
  color: "#5c6b82",
  fontSize: 13,
};

const tdStyle = {
  padding: "12px",
  borderBottom: "1px solid #eef2f7",
  color: "#162033",
};

const blockTitleStyle = {
  margin: "24px 0 0",
  fontSize: 16,
  fontWeight: 600,
  color: "#162033",
} as const;

async function fetchKrdCurveRisk(reportDate: string): Promise<KRDCurveRiskResponse> {
  const params = new URLSearchParams({ report_date: reportDate });
  const res = await fetch(`/api/bond-analytics/krd-curve-risk?${params}`);
  if (!res.ok) {
    throw new Error(`KRD 曲线风险：HTTP ${res.status}`);
  }
  const json: { result: KRDCurveRiskResponse } = await res.json();
  return json.result;
}

async function fetchCreditSpreadMigration(
  reportDate: string,
): Promise<CreditSpreadMigrationResponse> {
  const params = new URLSearchParams({ report_date: reportDate });
  const res = await fetch(`/api/bond-analytics/credit-spread-migration?${params}`);
  if (!res.ok) {
    throw new Error(`信用利差迁移：HTTP ${res.status}`);
  }
  const json: { result: CreditSpreadMigrationResponse } = await res.json();
  return json.result;
}

function cellText(value: string | number | null | undefined) {
  if (value === null || value === undefined) {
    return "—";
  }
  return String(value);
}

export default function RiskOverviewPage() {
  const [searchParams] = useSearchParams();
  const reportDate = useMemo(() => {
    const fromUrl = searchParams.get("report_date")?.trim();
    return fromUrl || DEFAULT_REPORT_DATE;
  }, [searchParams]);

  const krdQuery = useQuery({
    queryKey: ["risk-overview", "krd-curve-risk", reportDate],
    queryFn: () => fetchKrdCurveRisk(reportDate),
    retry: false,
  });

  const creditQuery = useQuery({
    queryKey: ["risk-overview", "credit-spread-migration", reportDate],
    queryFn: () => fetchCreditSpreadMigration(reportDate),
    retry: false,
  });

  const krd = krdQuery.data;
  const credit = creditQuery.data;

  return (
    <section>
      <div style={{ marginBottom: 24 }}>
        <h1
          style={{
            margin: 0,
            fontSize: 32,
            fontWeight: 600,
            letterSpacing: "-0.03em",
          }}
        >
          风险总览
        </h1>
        <p
          style={{
            marginTop: 10,
            marginBottom: 0,
            maxWidth: 860,
            color: "#5c6b82",
            fontSize: 15,
            lineHeight: 1.75,
          }}
        >
          消费 Bond Analytics 物化结果：利率曲线 / KRD、情景与信用利差。不在浏览器端做金融重算。
        </p>
      </div>

      <div style={controlBarStyle}>
        <div
          style={{
            padding: "10px 12px",
            borderRadius: 12,
            border: "1px solid #d7dfea",
            background: "#ffffff",
            color: "#162033",
            fontSize: 14,
          }}
        >
          报告日：<strong>{reportDate}</strong>
          <span style={{ marginLeft: 8, color: "#8090a8", fontSize: 13 }}>
            （可用 <code style={{ fontSize: 12 }}>?report_date=YYYY-MM-DD</code> 指定）
          </span>
        </div>
      </div>

      <div style={{ marginTop: 8 }}>
        <AsyncSection
          title="利率曲线与 KRD 风险"
          isLoading={krdQuery.isLoading}
          isError={krdQuery.isError}
          isEmpty={false}
          onRetry={() => void krdQuery.refetch()}
        >
          <div data-testid="risk-overview-kpi-grid" style={summaryGridStyle}>
            <PlaceholderCard
              title="组合久期"
              value={cellText(krd?.portfolio_duration)}
              detail="portfolio_duration，后端口径。"
            />
            <PlaceholderCard
              title="修正久期"
              value={cellText(krd?.portfolio_modified_duration)}
              detail="portfolio_modified_duration。"
            />
            <PlaceholderCard
              title="DV01"
              value={cellText(krd?.portfolio_dv01)}
              detail="portfolio_dv01。"
            />
            <PlaceholderCard
              title="凸性"
              value={cellText(krd?.portfolio_convexity)}
              detail="portfolio_convexity。"
            />
          </div>

          {krd && krd.warnings.length > 0 && (
            <div
              style={{
                marginTop: 16,
                padding: 12,
                borderRadius: 12,
                border: "1px solid #e8d9a8",
                background: "#fffbeb",
                color: "#7a5c1a",
                fontSize: 13,
              }}
            >
              {krd.warnings.map((w, i) => (
                <div key={i}>{w}</div>
              ))}
            </div>
          )}

          <h2 style={blockTitleStyle}>KRD 分桶</h2>
          <div style={tableShellStyle}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  {["期限", "KRD", "DV01", "市值权重"].map((label) => (
                    <th key={label} style={thStyle}>
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(krd?.krd_buckets ?? []).map((row) => (
                  <tr key={row.tenor}>
                    <td style={tdStyle}>{row.tenor}</td>
                    <td style={tdStyle}>{row.krd}</td>
                    <td style={tdStyle}>{row.dv01}</td>
                    <td style={tdStyle}>{row.market_value_weight}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2 style={blockTitleStyle}>情景分析</h2>
          <div style={tableShellStyle}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  {["情景名称", "情景说明", "经济口径损益", "OCI", "TPL"].map((label) => (
                    <th key={label} style={thStyle}>
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(krd?.scenarios ?? []).map((row) => (
                  <tr key={row.scenario_name}>
                    <td style={tdStyle}>{row.scenario_name}</td>
                    <td style={tdStyle}>{row.scenario_description}</td>
                    <td style={tdStyle}>{row.pnl_economic}</td>
                    <td style={tdStyle}>{row.pnl_oci}</td>
                    <td style={tdStyle}>{row.pnl_tpl}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2 style={blockTitleStyle}>资产类别风险汇总</h2>
          <div style={tableShellStyle}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  {["资产类别", "市值", "久期", "DV01", "权重"].map((label) => (
                    <th key={label} style={thStyle}>
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(krd?.by_asset_class ?? []).map((row) => (
                  <tr key={row.asset_class}>
                    <td style={tdStyle}>{row.asset_class}</td>
                    <td style={tdStyle}>{row.market_value}</td>
                    <td style={tdStyle}>{row.duration}</td>
                    <td style={tdStyle}>{row.dv01}</td>
                    <td style={tdStyle}>{row.weight}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {krd?.computed_at && (
            <p style={{ marginTop: 16, marginBottom: 0, color: "#8090a8", fontSize: 12 }}>
              computed_at: {krd.computed_at}
            </p>
          )}
        </AsyncSection>
      </div>

      <div style={{ marginTop: 24 }}>
        <AsyncSection
          title="信用利差"
          isLoading={creditQuery.isLoading}
          isError={creditQuery.isError}
          isEmpty={false}
          onRetry={() => void creditQuery.refetch()}
        >
          <div style={summaryGridStyle}>
            <PlaceholderCard
              title="信用债数量"
              value={cellText(credit?.credit_bond_count)}
              detail="credit_bond_count。"
            />
            <PlaceholderCard
              title="信用债市值"
              value={cellText(credit?.credit_market_value)}
              detail="credit_market_value。"
            />
            <PlaceholderCard
              title="Spread DV01"
              value={cellText(credit?.spread_dv01)}
              detail="spread_dv01。"
            />
          </div>

          {credit && credit.warnings.length > 0 && (
            <div
              style={{
                marginTop: 16,
                padding: 12,
                borderRadius: 12,
                border: "1px solid #e8d9a8",
                background: "#fffbeb",
                color: "#7a5c1a",
                fontSize: 13,
              }}
            >
              {credit.warnings.map((w, i) => (
                <div key={i}>{w}</div>
              ))}
            </div>
          )}

          <h2 style={blockTitleStyle}>利差情景</h2>
          <div style={tableShellStyle}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  {["情景", "利差变动 (bp)", "损益影响", "OCI", "TPL"].map((label) => (
                    <th key={label} style={thStyle}>
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(credit?.spread_scenarios ?? []).map((row) => (
                  <tr key={row.scenario_name}>
                    <td style={tdStyle}>{row.scenario_name}</td>
                    <td style={tdStyle}>{cellText(row.spread_change_bp)}</td>
                    <td style={tdStyle}>{row.pnl_impact}</td>
                    <td style={tdStyle}>{row.oci_impact}</td>
                    <td style={tdStyle}>{row.tpl_impact}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {credit?.computed_at && (
            <p style={{ marginTop: 16, marginBottom: 0, color: "#8090a8", fontSize: 12 }}>
              computed_at: {credit.computed_at}
            </p>
          )}
        </AsyncSection>
      </div>
    </section>
  );
}
