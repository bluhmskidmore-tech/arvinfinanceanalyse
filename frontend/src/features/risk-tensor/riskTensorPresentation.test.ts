import { describe, expect, it } from "vitest";
import { describeRiskTensorWarning } from "./riskTensorPresentation";

describe("risk tensor warning presentation", () => {
  it("keeps unknown warnings intact instead of hiding a new risk", () => {
    const warning = "New risk input is invalid: field_xyz";
    expect(describeRiskTensorWarning(warning)).toBe(warning);
  });

  it("preserves affected counts and the DV01 boundary in a duration warning", () => {
    const warning = "142 rows carry market_value=47729865025.41000000 and are excluded from portfolio duration denominator: 139 without maturity_date (market_value=45822902447.63000000); 3 matured on or before report_date with outstanding market_value (market_value=1906962577.78000000); 0 future-dated with non-positive modified_duration (market_value=0). DV01 totals remain sourced from row dv01; duration metrics ignore these rows until inputs are remediated.";
    expect(describeRiskTensorWarning(warning)).toBe("142 条持仓未计入组合久期：139 条未列到期日（旧版未拆分基金与待核实期限）、3 条已到期仍有余额、0 条未来到期但久期非正；DV01 沿既有口径汇总。");
  });

  it("separates classified funds from unknown maturity in the current warning", () => {
    const warning = "142 rows carry market_value=47729865025.41000000 and are excluded from portfolio duration denominator: 139 without maturity_date (market_value=45822902447.63000000); within that scope 139 fund_no_maturity (market_value=45822902447.63000000, underlying rate risk not modelled) and 0 unknown_maturity (market_value=0); 3 matured on or before report_date with outstanding market_value (market_value=1906962577.78000000); 0 future-dated with non-positive modified_duration (market_value=0). DV01 totals remain sourced from row dv01; duration is limited to the covered subset. Fund underlying rate risk remains unmodelled; unknown dates and other input-quality rows require review.";
    expect(describeRiskTensorWarning(warning)).toBe("142 条持仓未计入组合久期：139 条基金未列固定到期日（底层利率风险未穿透）、0 条期限待核实、3 条已到期仍有余额、0 条未来到期但久期非正；DV01 沿既有口径汇总。");
  });

  it("translates the short duration-denominator exclusion warning and keeps the market value verbatim", () => {
    const warning = "2 rows carry market_value=100000000.00000000 and are excluded from portfolio duration denominator.";
    expect(describeRiskTensorWarning(warning)).toBe("2 条记录市值 100000000.00000000 已从组合久期分母剔除。");
  });

  it("reuses the cashflow frequency warning without calling the assumption observed", () => {
    expect(describeRiskTensorWarning("1653 rows with market_value=303093854704.01931600 lack an explicit payment frequency; annual coupon frequency is used as a proxy.")).toMatch(/1653 行缺付息频率，按年付代理/);
  });

  it("distinguishes excluded liabilities from assets", () => {
    expect(describeRiskTensorWarning("Excluded 1748 liability rows without maturity_date from liquidity gap calculation.")).toBe("1748 条负债未列到期日，未计入合同流动性缺口；该提示未拆分产品属性。");
    expect(describeRiskTensorWarning("Excluded 139 rows without maturity_date from liquidity gap calculation.")).toBe("139 条资产未列到期日，未计入合同流动性缺口；该提示未拆分产品属性。");
  });
});
