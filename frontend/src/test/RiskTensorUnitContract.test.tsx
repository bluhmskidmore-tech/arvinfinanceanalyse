/**
 * risk-tensor unit_consistency / precision_and_rounding 契约探针
 * （agent 评测 harness `risk_tensor_contract_001` 的 gate 探针）。
 *
 * Gate 语义：
 * - unit_consistency：后端 `/api/risk/tensor` 返回的元（yuan）口径数值，页面按
 *   万元（/1e4，DV01/KRD/CS01 敏感性族）与亿元（/1e8，市值/现金流/流动性缺口族）
 *   缩放展示，单位标签与缩放因子必须配对；数值缺失时单位标签必须一并抑制。
 * - precision_and_rounding：金额缩放后按 zh-CN 两位小数（千分组）显示，四舍五入
 *   进位边界正确；比率族 ×100 保留 1 位小数带 %；后端已给出的展示字符串
 *   （久期/凸性/Numeric.display）原样透传，不得在前端再次舍入。
 *
 * 契约依据：
 * - docs/metric_dictionary.md `MTR-RSK-*` 行：portfolio_dv01/regulatory_dv01/cs01/
 *   rate_risk_dv01 为 DV01 敏感性（页面单位 万元）；total_market_value/
 *   rate_risk_market_value/duration_excluded_market_value/liquidity_gap_30d/90d
 *   为金额（页面单位 亿元）；issuer_top5_weight/liquidity_gap_30d_ratio 为比率型。
 * - docs/page_contracts.md §9 PAGE-RISK-001：禁止前端重算 KRD/DV01/CS01/凸性，
 *   页面只做展示缩放；F 指标映射列出各展示项来源字段。
 * - 展示层 RiskTensorPage.tsx（页面私有，本文件经整页渲染锁定其行为）：
 *   `formatYuanAmount`：raw 元 / YUAN_PER_WAN(1e4) 或 YUAN_PER_YI(1e8)，
 *   `toLocaleString("zh-CN", {min/maximumFractionDigits: 2})`，负号前置；
 *   `amountUnit`：raw 不可解析（null/""）时单位标签返回 undefined（不渲染）；
 *   `regulatoryDv01Display`：null/undefined → 「待接入」，有值 → 万元缩放；
 *   `ratioPercentDisplay`：比率字符串 |raw|<=1 → (raw*100).toFixed(1)+"%"；
 *   `displayStr`（bondNumericDisplay）：字符串/Numeric.display 原样透传，
 *   ""/null → EM_DASH「—」。
 * - 换算必须消费 Numeric.raw（governed 数值真值），不得解析 display 字符串。
 */
import { type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="risk-tensor-unit-contract-echarts-stub" />,
}));

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { Numeric, ResultMeta, RiskTensorPayload } from "../api/contracts";
import RiskTensorPage from "../features/risk-tensor/RiskTensorPage";
import { EM_DASH } from "../utils/format";

const REPORT_DATE = "2026-02-28";
const WAN_YUAN_UNIT = "\u4e07\u5143";
const YI_YUAN_UNIT = "\u4ebf\u5143";

function buildMeta(resultKind: string): ResultMeta {
  return {
    trace_id: `tr_${resultKind}`,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv_risk_unit_contract",
    vendor_version: "vv_none",
    rule_version: "rv_risk_unit_contract",
    cache_version: "cv_risk_unit_contract",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-03-01T08:00:00Z",
  };
}

/** governed Numeric（元口径）；display 故意与 raw 的缩放结果不同形，锁定「换算走 raw」。 */
function yuanNumeric(raw: number, display: string): Numeric {
  return { raw, unit: "yuan", display, precision: 2, sign_aware: false };
}

/** 基准载荷：全部字段可解析，各测试按契约切面覆写。 */
function tensorPayload(overrides: Partial<RiskTensorPayload>): RiskTensorPayload {
  return {
    report_date: REPORT_DATE,
    portfolio_dv01: "123456",
    krd_1y: "10000",
    krd_3y: "20000",
    krd_5y: "30000",
    krd_7y: "25000",
    krd_10y: "15000",
    krd_30y: "5000",
    cs01: "123412",
    portfolio_convexity: "120.5",
    portfolio_modified_duration: "4.2",
    issuer_concentration_hhi: "0.18",
    issuer_top5_weight: "0.406",
    asset_cashflow_30d: "300000000",
    asset_cashflow_90d: "500000000",
    liability_cashflow_30d: "200000000",
    liability_cashflow_90d: "250000000",
    liquidity_gap_30d: "-350000000",
    liquidity_gap_90d: "0",
    liquidity_gap_30d_ratio: "0.053",
    total_market_value: "100000000",
    rate_risk_market_value: "460000000",
    rate_risk_dv01: "123456789",
    rate_risk_modified_duration: "4.2",
    duration_excluded_market_value: "99990000",
    duration_excluded_count: 2,
    missing_maturity_market_value: "0",
    missing_maturity_count: 0,
    floating_rate_proxy_market_value: "0",
    floating_rate_proxy_count: 0,
    payment_frequency_fallback_market_value: "0",
    payment_frequency_fallback_count: 0,
    bullet_value_date_fallback_market_value: "0",
    bullet_value_date_fallback_count: 0,
    projection_quality_status: "available",
    bond_count: 12,
    quality_flag: "ok",
    warnings: [],
    ...overrides,
  };
}

function buildClient(payload: RiskTensorPayload): ApiClient {
  const base = createApiClient({ mode: "mock" });
  return {
    ...base,
    getRiskTensorDates: vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates"),
      result: { report_dates: [REPORT_DATE] },
    })),
    getRiskTensor: vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor"),
      result: payload,
    })),
  };
}

function renderRiskTensorPage(client: ApiClient) {
  function Wrapper({ children }: { children: ReactNode }) {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
      },
    });
    return (
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter initialEntries={["/risk-tensor"]}>{children}</MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>
    );
  }
  return render(
    <Wrapper>
      <RiskTensorPage />
    </Wrapper>,
  );
}

/** 在容器内按 KPI 卡标题精确读出 value 与 unit 文本（unit 未渲染时为 null）。 */
function readKpiCard(root: HTMLElement, title: string): { value: string; unit: string | null } {
  const card = Array.from(root.querySelectorAll(".kpi-card")).find(
    (el) => el.querySelector(".kpi-card__title-text")?.textContent?.trim() === title,
  );
  if (!card) {
    throw new Error(`未找到标题为「${title}」的 KPI 卡`);
  }
  return {
    value: card.querySelector(".kpi-card__value")?.textContent?.trim() ?? "",
    unit: card.querySelector(".kpi-card__unit")?.textContent?.trim() ?? null,
  };
}

describe("risk-tensor 单位一致性：元→万元/亿元缩放因子与单位标签配对", () => {
  it("DV01/CS01 族按 1e4 缩放配万元，市值/缺口族按 1e8 缩放配亿元，缺失值抑制单位", async () => {
    renderRiskTensorPage(
      buildClient(
        tensorPayload({
          // 换算必须消费 Numeric.raw：display 给出元口径干扰字符串，
          // 若前端解析 display 或漏除 1e4，断言必红。
          portfolio_dv01: yuanNumeric(123456, "123,456.00"),
          // 监管口径 DV01 有值时不得显示「待接入」，负号保留（signed tone 契约）。
          regulatory_dv01: "-8800",
          cs01: "123412",
          // 缩放阈值边界：恰好 1 亿元 → 1.00 亿元。若误用 1e4 则显示 10,000.00。
          total_market_value: "100000000",
          rate_risk_market_value: "460000000",
          // 万元缩放 + zh-CN 千分组：123,456,789 元 → 12,345.68 万元。
          rate_risk_dv01: "123456789",
          rate_risk_modified_duration: "4.2",
          // 缺失（空字符串）→ EM_DASH 且亿元单位标签必须一并抑制（amountUnit 契约）。
          duration_excluded_market_value: "",
          // 负缺口保留符号：-350,000,000 元 → -3.50 亿元。
          liquidity_gap_30d: "-350000000",
          // 真零：0.00 亿元，与缺失（—）必须不同形。
          liquidity_gap_90d: "0",
        }),
      ),
    );

    const kpiGrid = await screen.findByTestId("risk-tensor-kpi-grid");
    // MTR-RSK-001 面值口径 DV01：123,456 元 / 1e4 = 12.3456 → 12.35 万元。
    expect(readKpiCard(kpiGrid, "面值口径 DV01")).toEqual({ value: "12.35", unit: WAN_YUAN_UNIT });
    // MTR-RSK-001R 监管口径 DV01：-8,800 元 → -0.88 万元（非「待接入」，符号保留）。
    expect(readKpiCard(kpiGrid, "监管口径 DV01")).toEqual({ value: "-0.88", unit: WAN_YUAN_UNIT });
    // MTR-RSK-008 CS01：123,412 元 → 12.34 万元。
    expect(readKpiCard(kpiGrid, "CS01")).toEqual({ value: "12.34", unit: WAN_YUAN_UNIT });
    // MTR-RSK-020 总市值：1e8 元边界 → 1.00 亿元。
    expect(readKpiCard(kpiGrid, "总市值")).toEqual({ value: "1.00", unit: YI_YUAN_UNIT });

    const durationScope = screen.getByTestId("risk-tensor-duration-scope");
    // MTR-RSK-021 利率风险市值：460,000,000 元 → 4.60 亿元。
    expect(readKpiCard(durationScope, "利率风险市值")).toEqual({ value: "4.60", unit: YI_YUAN_UNIT });
    // MTR-RSK-022 利率风险 DV01：万元缩放 + 千分组 → 12,345.68 万元。
    expect(readKpiCard(durationScope, "利率风险 DV01")).toEqual({
      value: "12,345.68",
      unit: WAN_YUAN_UNIT,
    });
    // MTR-RSK-023 利率风险久期：后端字符串透传 + 年单位（不做金额缩放）。
    expect(readKpiCard(durationScope, "利率风险久期")).toEqual({ value: "4.2", unit: "年" });
    // MTR-RSK-104 久期排除市值缺失：EM_DASH 占位且亿元单位标签不得渲染。
    expect(readKpiCard(durationScope, "久期排除市值")).toEqual({ value: EM_DASH, unit: null });

    const liquidityDetail = screen.getByTestId("risk-tensor-liquidity-gap-detail");
    // MTR-RSK-017 30 天流动性缺口：负值保留符号 → -3.50 亿元。
    expect(readKpiCard(liquidityDetail, "30 日资产现金流 - 负债现金流")).toEqual({
      value: "-3.50",
      unit: YI_YUAN_UNIT,
    });
    // MTR-RSK-018 90 天流动性缺口：真零 → 0.00 亿元（与缺失不同形）。
    expect(readKpiCard(liquidityDetail, "90 日资产现金流 - 负债现金流")).toEqual({
      value: "0.00",
      unit: YI_YUAN_UNIT,
    });

    // MTR-RSK-004 KRD 期限桶（默认选中峰值 5Y）：30,000 元 → 3.00 万元。
    expect(screen.getByTestId("risk-tensor-tenor-drill")).toHaveTextContent(`3.00 ${WAN_YUAN_UNIT}`);
  });
});

describe("risk-tensor 精度与舍入：两位小数边界、比率 1 位小数、后端展示透传", () => {
  it("金额缩放两位小数进/不进位与整数进位边界正确，比率 ×100 保留 1 位，透传值不再舍入", async () => {
    renderRiskTensorPage(
      buildClient(
        tensorPayload({
          // 进位：12.3456 → 12.35。
          portfolio_dv01: "123456",
          // 不进位：12.3412 → 12.34。
          cs01: "123412",
          // 跨整数进位：99.9999 万元 → 100.00 万元。
          regulatory_dv01: "999999",
          // 亿元不进位：1.2345 → 1.23。
          total_market_value: "123450000",
          // 负值按绝对值舍入后补符号：-1.23456789 亿 → -1.23。
          liquidity_gap_30d: "-123456789",
          // 单位边界进位：0.9999 亿 → 1.00 亿元。
          duration_excluded_market_value: "99990000",
          // 比率族 ×100 保留 1 位小数：0.053 → 5.3%；0.406 → 40.6%。
          liquidity_gap_30d_ratio: "0.053",
          issuer_top5_weight: "0.406",
          // 后端展示透传：久期/凸性字符串与 Numeric.display 不得再舍入或补零。
          portfolio_modified_duration: "4.2",
          portfolio_convexity: "120.5",
          issuer_concentration_hhi: {
            raw: 0.1834,
            unit: "ratio",
            display: "0.1834",
            precision: 4,
            sign_aware: false,
          },
        }),
      ),
    );

    const kpiGrid = await screen.findByTestId("risk-tensor-kpi-grid");
    expect(readKpiCard(kpiGrid, "面值口径 DV01").value).toBe("12.35");
    expect(readKpiCard(kpiGrid, "CS01").value).toBe("12.34");
    expect(readKpiCard(kpiGrid, "监管口径 DV01").value).toBe("100.00");
    expect(readKpiCard(kpiGrid, "总市值").value).toBe("1.23");
    // MTR-RSK-010 修正久期：后端字符串 "4.2" 透传，不得补零为 "4.20"。
    expect(readKpiCard(kpiGrid, "修正久期")).toEqual({ value: "4.2", unit: "年" });
    // MTR-RSK-009 组合凸性：透传且无单位标签。
    expect(readKpiCard(kpiGrid, "组合凸性")).toEqual({ value: "120.5", unit: null });

    const durationScope = screen.getByTestId("risk-tensor-duration-scope");
    expect(readKpiCard(durationScope, "久期排除市值")).toEqual({ value: "1.00", unit: YI_YUAN_UNIT });

    const liquidityDetail = screen.getByTestId("risk-tensor-liquidity-gap-detail");
    expect(readKpiCard(liquidityDetail, "30 日资产现金流 - 负债现金流").value).toBe("-1.23");
    // MTR-RSK-019 流动性缺口比例：0.053 → 5.3%（1 位小数）。
    expect(readKpiCard(liquidityDetail, "30 日流动性缺口比例")).toEqual({ value: "5.3%", unit: null });

    const issuerDetail = screen.getByTestId("risk-tensor-issuer-concentration-detail");
    // MTR-RSK-012 前五发行人占比：0.406 → 40.6%。
    expect(readKpiCard(issuerDetail, "前五大权重")).toEqual({ value: "40.6%", unit: null });
    // MTR-RSK-011 发行人 HHI：Numeric.display "0.1834" 原样透传（不截断为两位）。
    expect(readKpiCard(issuerDetail, "发行人 HHI")).toEqual({ value: "0.1834", unit: null });
  });
});
