import type {
  ApiEnvelope,
  BalanceMovementDatesPayload,
  BalanceMovementPayload,
  BalanceMovementRefreshPayload,
} from "./contracts";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";

type FetchLike = typeof fetch;

export type BalanceMovementClientMethods = {
  getBalanceMovementDates: (
    currencyBasis?: string,
  ) => Promise<ApiEnvelope<BalanceMovementDatesPayload>>;
  getBalanceMovementAnalysis: (options: {
    reportDate: string;
    currencyBasis?: string;
  }) => Promise<ApiEnvelope<BalanceMovementPayload>>;
  refreshBalanceMovementAnalysis: (options: {
    reportDate: string;
    currencyBasis?: string;
  }) => Promise<BalanceMovementRefreshPayload>;
};

export function createMockBalanceMovementClient(): BalanceMovementClientMethods {
  return {
    async getBalanceMovementDates(currencyBasis = "CNX") {
      return buildMockApiEnvelope("balance-analysis.movement.dates", {
        report_dates: ["2026-02-28"],
        currency_basis: currencyBasis,
      });
    },
    async getBalanceMovementAnalysis({ reportDate, currencyBasis = "CNX" }) {
      const reportMonth = reportDate.slice(0, 7);
      const currentRows: BalanceMovementPayload["rows"] = [
        {
          report_date: reportDate,
          report_month: reportMonth,
          currency_basis: currencyBasis,
          sort_order: 1,
          basis_bucket: "AC",
          previous_balance: "139214376198.90",
          current_balance: "142543803312.70",
          previous_balance_pct: "43.114646",
          current_balance_pct: "42.439753",
          balance_change: "3329427113.80",
          change_pct: "2.391581",
          contribution_pct: "25.6509",
          zqtz_amount: "142543803312.70",
          gl_amount: "142543803312.70",
          reconciliation_diff: "0",
          reconciliation_status: "matched",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
        {
          report_date: reportDate,
          report_month: reportMonth,
          currency_basis: currencyBasis,
          sort_order: 2,
          basis_bucket: "OCI",
          previous_balance: "101294750662.96",
          current_balance: "105781745231.25",
          previous_balance_pct: "31.370951",
          current_balance_pct: "31.494537",
          balance_change: "4486994568.29",
          change_pct: "4.429644",
          contribution_pct: "34.5682",
          zqtz_amount: "105781745231.25",
          gl_amount: "105781745231.25",
          reconciliation_diff: "0",
          reconciliation_status: "matched",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
        {
          report_date: reportDate,
          report_month: reportMonth,
          currency_basis: currencyBasis,
          sort_order: 3,
          basis_bucket: "TPL",
          previous_balance: "82384340890.05",
          current_balance: "87547760746.55",
          previous_balance_pct: "25.514403",
          current_balance_pct: "26.065709",
          balance_change: "5163419856.50",
          change_pct: "6.267476",
          contribution_pct: "39.7809",
          zqtz_amount: "87547760746.55",
          gl_amount: "87547760746.55",
          reconciliation_diff: "0",
          reconciliation_status: "matched",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
      ];
      const previousRows: BalanceMovementPayload["rows"] = [
        {
          report_date: "2026-01-31",
          report_month: "2026-01",
          currency_basis: currencyBasis,
          sort_order: 1,
          basis_bucket: "AC",
          previous_balance: "133290012435.54",
          current_balance: "139214376198.90",
          previous_balance_pct: "43.18",
          current_balance_pct: "43.11",
          balance_change: "5924363763.36",
          change_pct: "4.44",
          contribution_pct: "40.98",
          zqtz_amount: "139214376198.90",
          gl_amount: "139214376198.90",
          reconciliation_diff: "0",
          reconciliation_status: "matched",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
        {
          report_date: "2026-01-31",
          report_month: "2026-01",
          currency_basis: currencyBasis,
          sort_order: 2,
          basis_bucket: "OCI",
          previous_balance: "98220500620.00",
          current_balance: "101294750662.96",
          previous_balance_pct: "31.84",
          current_balance_pct: "31.37",
          balance_change: "3074250042.96",
          change_pct: "3.13",
          contribution_pct: "21.27",
          zqtz_amount: "101294750662.96",
          gl_amount: "101294750662.96",
          reconciliation_diff: "0",
          reconciliation_status: "matched",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
        {
          report_date: "2026-01-31",
          report_month: "2026-01",
          currency_basis: currencyBasis,
          sort_order: 3,
          basis_bucket: "TPL",
          previous_balance: "76928560422.80",
          current_balance: "82384340890.18",
          previous_balance_pct: "24.98",
          current_balance_pct: "25.51",
          balance_change: "5455780467.38",
          change_pct: "7.09",
          contribution_pct: "37.75",
          zqtz_amount: "82384340890.05",
          gl_amount: "82384340890.05",
          reconciliation_diff: "0",
          reconciliation_status: "matched",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
      ];
      const currentBusinessRows: BalanceMovementPayload["business_trend_months"][number]["rows"] = [
        {
          report_date: reportDate,
          report_month: reportMonth,
          currency_basis: currencyBasis,
          side: "asset",
          sort_order: 10,
          row_key: "asset_interbank_lending",
          row_label: "资产端-拆放同业",
          current_balance: "8000000000",
          source_kind: "ledger",
          source_note: "总账对账科目余额：120% + 121%",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
        {
          report_date: reportDate,
          report_month: reportMonth,
          currency_basis: currencyBasis,
          side: "asset",
          sort_order: 20,
          row_key: "asset_reverse_repo",
          row_label: "资产端-买入返售",
          current_balance: "9000000000",
          source_kind: "ledger",
          source_note: "总账对账科目余额：140%，排除 14004% / 14005%",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
        {
          report_date: reportDate,
          report_month: reportMonth,
          currency_basis: currencyBasis,
          side: "asset",
          sort_order: 30,
          row_key: "asset_interbank_current_deposit",
          row_label: "资产端-同业存放-活期",
          current_balance: "3500000000",
          source_kind: "ledger",
          source_note: "总账对账科目余额：114%",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
        {
          report_date: reportDate,
          report_month: reportMonth,
          currency_basis: currencyBasis,
          side: "asset",
          sort_order: 40,
          row_key: "asset_domestic_interbank_term_deposit",
          row_label: "资产端-存放同业境内-定期",
          current_balance: "4500000000",
          source_kind: "ledger",
          source_note: "总账对账科目余额：115%",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
        {
          report_date: reportDate,
          report_month: reportMonth,
          currency_basis: currencyBasis,
          side: "asset",
          sort_order: 50,
          row_key: "asset_overseas_interbank_term_deposit",
          row_label: "资产端-存放同业境外-定期",
          current_balance: "2500000000",
          source_kind: "ledger",
          source_note: "总账对账科目余额：116%",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
        {
          report_date: reportDate,
          report_month: reportMonth,
          currency_basis: currencyBasis,
          side: "asset",
          sort_order: 60,
          row_key: "asset_zqtz_interbank_cd",
          row_label: "资产端-同业存单",
          current_balance: "1800000000",
          source_kind: "zqtz",
          source_note: "ZQTZSHOW 业务种类1=同业存单",
          source_version: "sv_mock_zqtz",
          rule_version: "rv_accounting_asset_movement_v2",
        },
        {
          report_date: reportDate,
          report_month: reportMonth,
          currency_basis: currencyBasis,
          side: "liability",
          sort_order: 110,
          row_key: "liability_interbank_deposits",
          row_label: "负债端-同业存放",
          current_balance: "-9000000000",
          source_kind: "ledger",
          source_note: "总账对账科目余额：234% + 235%",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
        {
          report_date: reportDate,
          report_month: reportMonth,
          currency_basis: currencyBasis,
          side: "liability",
          sort_order: 120,
          row_key: "liability_interbank_borrowings",
          row_label: "负债端-同业拆入",
          current_balance: "-3500000000",
          source_kind: "ledger",
          source_note: "总账对账科目余额：241% + 242%",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
        {
          report_date: reportDate,
          report_month: reportMonth,
          currency_basis: currencyBasis,
          side: "liability",
          sort_order: 130,
          row_key: "liability_repo",
          row_label: "负债端-卖出回购",
          current_balance: "-9500000000",
          source_kind: "ledger",
          source_note: "总账对账科目余额：255%",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
        {
          report_date: reportDate,
          report_month: reportMonth,
          currency_basis: currencyBasis,
          side: "liability",
          sort_order: 140,
          row_key: "liability_interbank_cd",
          row_label: "负债端-同业存单",
          current_balance: "-4000000000",
          source_kind: "ledger",
          source_note: "总账对账科目余额：27205000001 + 27206000001",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
      ];
      currentBusinessRows.splice(
        5,
        1,
        ...[
          ["asset_zqtz_central_bank_bill", "央行票据", "0", 60],
          ["asset_zqtz_treasury_bond", "国债（含凭证式国债）", "1200000000", 62],
          ["asset_zqtz_local_government_bond", "地方政府债", "2200000000", 64],
          ["asset_zqtz_policy_financial_bond", "政策性金融债", "3200000000", 66],
          ["asset_zqtz_railway_bond", "铁道债", "0", 68],
          ["asset_zqtz_commercial_financial_bond", "商业性金融债", "1600000000", 70],
          ["asset_zqtz_interbank_cd", "同业存单", "1800000000", 72],
          ["asset_zqtz_nonfinancial_enterprise_bond", "非金融企业债券", "2600000000", 74],
          ["asset_zqtz_abs", "资产支持证券", "900000000", 76],
          ["asset_zqtz_foreign_bond", "外国债券", "300000000", 78],
          ["asset_zqtz_public_fund", "公募基金", "800000000", 80],
          ["asset_zqtz_non_bottom_investment", "非底层投资资产", "700000000", 82],
          ["asset_zqtz_detail_trust_plan", "信托计划", "0", 83],
          ["asset_zqtz_detail_securities_asset_management_plan", "证券业资管计划", "400000000", 84],
          ["asset_zqtz_detail_structured_finance_broker", "其中：结构化融资（券商）", "200000000", 85],
          ["asset_zqtz_detail_foreign_currency_delegated", "其中：外币委外", "100000000", 86],
          ["asset_zqtz_detail_local_currency_delegated_market_value", "其中：本币委外（市值法）", "400000000", 87],
          ["asset_zqtz_detail_local_currency_special_account_cost", "其中：本币专户（成本法）", "200000000", 88],
          ["asset_zqtz_other_debt_financing", "其他债权融资类产品", "400000000", 90],
          ["asset_long_term_equity_investment", "长期股权投资（亿元）", "600000000", 94],
        ].map(([rowKey, rowLabel, currentBalance, sortOrder]) => ({
          report_date: reportDate,
          report_month: reportMonth,
          currency_basis: currencyBasis,
          side: "asset" as const,
          sort_order: Number(sortOrder),
          row_key: String(rowKey),
          row_label: String(rowLabel),
          current_balance: String(currentBalance),
          source_kind: rowKey === "asset_long_term_equity_investment" ? "ledger" as const : "zqtz" as const,
          source_note: "ZQTZSHOW 资产产品分类",
          source_version: rowKey === "asset_long_term_equity_investment" ? "sv_mock" : "sv_mock_zqtz",
          rule_version: "rv_accounting_asset_movement_v2",
        })),
      );
      const previousBusinessRows = currentBusinessRows.map((row) => ({
        ...row,
        report_date: "2026-01-31",
        report_month: "2026-01",
        current_balance:
          row.row_key === "asset_interbank_lending"
            ? "5000000000"
            : row.row_key === "asset_reverse_repo"
              ? "7000000000"
              : row.row_key === "asset_interbank_current_deposit"
                ? "3000000000"
                : row.row_key === "asset_domestic_interbank_term_deposit"
                  ? "4000000000"
                  : row.row_key === "asset_overseas_interbank_term_deposit"
                    ? "2000000000"
                    : row.row_key === "asset_zqtz_interbank_cd"
                      ? "1200000000"
                      : row.row_key === "liability_interbank_deposits"
                        ? "-6000000000"
                        : row.row_key === "liability_interbank_borrowings"
                          ? "-2500000000"
                          : row.row_key === "liability_repo"
                            ? "-7000000000"
                            : row.row_key === "liability_interbank_cd"
                              ? "-2000000000"
                              : row.row_key.startsWith("asset_zqtz_detail_")
                                ? "0"
                                : String(Math.round(Number(row.current_balance) * 0.75)),
      }));

      return buildMockApiEnvelope(
        "balance-analysis.movement.detail",
        {
          report_date: reportDate,
          currency_basis: currencyBasis,
          accounting_controls: ["141%", "142%", "143%", "1440101%"],
          excluded_controls: ["144020%"],
          summary: {
            previous_balance_total: "322893467751.91",
            current_balance_total: "335873309290.50",
            balance_change_total: "12979841538.59",
            zqtz_amount_total: "335873309290.50",
            reconciliation_diff_total: "0",
            matched_bucket_count: 3,
            bucket_count: 3,
          },
          trend_months: [
            {
              report_date: reportDate,
              report_month: reportMonth,
              current_balance_total: "335873309290.50",
              balance_change_total: "12979841538.59",
              rows: currentRows,
            },
            {
              report_date: "2026-01-31",
              report_month: "2026-01",
              current_balance_total: "322893467752.04",
              balance_change_total: "14454898913.70",
              rows: previousRows,
            },
          ],
          business_trend_months: [
            {
              report_date: reportDate,
              report_month: reportMonth,
              asset_balance_total: "43800000000",
              liability_balance_total: "-26000000000",
              net_balance_total: "17800000000",
              rows: currentBusinessRows,
            },
            {
              report_date: "2026-01-31",
              report_month: "2026-01",
              asset_balance_total: "34425000000",
              liability_balance_total: "-17700000000",
              net_balance_total: "16725000000",
              rows: previousBusinessRows,
            },
          ],
          zqtz_calibration_analysis: {
            source_file: "ZQTZSHOW-20260228.xls / ZQTZ228",
            conclusion:
              "政策性金融债的大额差异已定位并修复：不是外债折算，也不是政策债口径包含凭证式国债/地方债，而是 ZQTZ 标准化粒度覆盖了同券多笔持仓。",
            root_cause:
              "旧 canonical grain 只按日期、债券代码、组合、成本中心、币种聚合；同券多分类持仓被后到行覆盖，导致政策性金融债少约 58.12 亿元。",
            remediation:
              "现已把 ZQTZ grain 扩到会计分类、业务种类、到期日、来源批次等维度，并在同一会计桶内加总金额。",
            items: [
              {
                row_key: "asset_zqtz_policy_financial_bond",
                row_label: "政策性金融债",
                system_amount: "65228031802.46",
                reference_amount: "65228031802.46",
                diff_amount: "0",
                status: "matched",
                note: "ZQTZ228 原表按会计分类保留多笔同券持仓后，与展示表一致。",
              },
              {
                row_key: "asset_zqtz_local_government_bond",
                row_label: "地方政府债",
                system_amount: "42264356556.22",
                reference_amount: "42264356556.22",
                diff_amount: "0",
                status: "matched",
                note: "同一口径下，地方政府债与展示表一致。",
              },
              {
                row_key: "asset_zqtz_foreign_bond",
                row_label: "外国债券",
                system_amount: "483804358.75",
                reference_amount: "496000000",
                diff_amount: "-12195641.25",
                status: "matched",
                note: "外国债券按 US* + HK0001155867 清单和 CNY formal 金额折算，保留小额观察。",
              },
            ],
            residual_risks: [
              "外国债券仍依赖披露外债清单；如后续 ZQTZ 提供明确 sub_type=外国债券，应替换清单规则。",
              "2026-03 展示表需要 2026-03 ZQTZ/总账入库后才能做同样核对。",
            ],
          },
          structure_migration_analysis: {
            summary: "2026-02 较 2026-01：占比正向抬升最明显的是 TPL。",
            caveat:
              "这是汇总会计分类桶的结构信号，不等同于单只资产已经在 AC/OCI/FVTPL 之间完成会计分类迁移。",
            pairs: [
              {
                previous_report_date: "2026-01-31",
                current_report_date: reportDate,
                previous_report_month: "2026-01",
                current_report_month: reportMonth,
                total_balance_delta: "12979841538.46",
                dominant_share_increase_bucket: "TPL",
                fvtpl_volatility_signal:
                  "FVTPL 余额或占比上升，说明损益波动暴露在抬升；这不是已实现损益结论。",
                oci_valuation_signal:
                  "OCI 公允价值变动科目的变化解释不足一半 OCI 余额变动；估值不是本月对的主导代理信号。",
                buckets: [
                  {
                    basis_bucket: "AC",
                    previous_balance: "139214376198.90",
                    current_balance: "142543803312.70",
                    balance_delta: "3329427113.80",
                    previous_share_pct: "43.114646",
                    current_share_pct: "42.439753",
                    share_delta_pp: "-0.674893",
                  },
                  {
                    basis_bucket: "OCI",
                    previous_balance: "101294750662.96",
                    current_balance: "105781745231.25",
                    balance_delta: "4486994568.29",
                    previous_share_pct: "31.370951",
                    current_share_pct: "31.494537",
                    share_delta_pp: "0.123586",
                  },
                  {
                    basis_bucket: "TPL",
                    previous_balance: "82384340890.05",
                    current_balance: "87547760746.55",
                    balance_delta: "5163419856.50",
                    previous_share_pct: "25.514403",
                    current_share_pct: "26.065709",
                    share_delta_pp: "0.551306",
                  },
                ],
              },
            ],
          },
          difference_attribution_waterfall: {
            reference_label: "ZQTZ 明细汇总",
            reference_total: "337854709540.00",
            target_label: "AC/OCI/FVTPL 合计",
            target_total: "335873309290.50",
            net_difference: "-1981400249.50",
            components: [
              {
                component_key: "long_term_equity_investment",
                component_label: "长期股权投资",
                amount: "-2008360000.00",
                source_kind: "ledger",
                evidence_note:
                  "ZQTZ 明细页汇总包含总账长期股权投资行；AC/OCI/FVTPL 控制合计剔除 145*。",
                is_residual: false,
                is_supported: true,
              },
              {
                component_key: "voucher_treasury_1430101_cost",
                component_label: "凭证式国债 / 1430101 成本",
                amount: "52205400.00",
                source_kind: "derived",
                evidence_note:
                  "总账 14301010001 期末余额与 formal ZQTZ 凭证式国债摊余成本的差额。",
                is_residual: false,
                is_supported: true,
              },
              {
                component_key: "voucher_treasury_1430101_accrued_interest",
                component_label: "凭证式国债 / 1430101 应计利息",
                amount: "0",
                source_kind: "derived",
                evidence_note:
                  "总账 14301010002 期末余额与 formal ZQTZ 凭证式国债应计利息的差额。",
                is_residual: false,
                is_supported: true,
              },
              {
                component_key: "valuation_gap",
                component_label: "估值差",
                amount: "0",
                source_kind: "derived",
                evidence_note: "当前 payload 没有可独立闭合的估值拆分；未支持金额保留在残差中。",
                is_residual: false,
                is_supported: false,
              },
              {
                component_key: "fx_translation_gap",
                component_label: "外币折算差",
                amount: "0",
                source_kind: "derived",
                evidence_note: "当前 payload 没有可独立闭合的外币折算拆分；未支持金额保留在残差中。",
                is_residual: false,
                is_supported: false,
              },
              {
                component_key: "residual_unclassified",
                component_label: "未分类 / 残差",
                amount: "-252594649.50",
                source_kind: "residual",
                evidence_note: "直接支持项拆分后，为闭合瀑布图所需的剩余差额。",
                is_residual: true,
                is_supported: true,
              },
            ],
            closing_check: "0",
            caveat:
              "瀑布金额表示从 ZQTZ 明细汇总调整到 AC/OCI/FVTPL 合计的方向。估值差和外币折算差目前只展示可确认部分，不反推未闭合金额。",
          },
          rows: currentRows,
        },
        { quality_flag: "ok" },
      );
    },
    async refreshBalanceMovementAnalysis({ reportDate, currencyBasis = "CNX" }) {
      return {
        status: "completed",
        cache_key: "accounting_asset_movement.monthly",
        report_date: reportDate,
        currency_basis: currencyBasis,
        row_count: 3,
        source_version: "sv_mock",
        rule_version: "rv_accounting_asset_movement_v2",
      };
    },
  };
}

export function createRealBalanceMovementClient(options: {
  fetchImpl: FetchLike;
  baseUrl: string;
}): BalanceMovementClientMethods {
  const { fetchImpl, baseUrl } = options;
  return {
    getBalanceMovementDates: (currencyBasis = "CNX") =>
      requestJson<BalanceMovementDatesPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-movement-analysis/dates?currency_basis=${encodeURIComponent(currencyBasis)}`,
      ),
    getBalanceMovementAnalysis: ({ reportDate, currencyBasis = "CNX" }) =>
      requestJson<BalanceMovementPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-movement-analysis?report_date=${encodeURIComponent(reportDate)}&currency_basis=${encodeURIComponent(currencyBasis)}`,
      ),
    refreshBalanceMovementAnalysis: ({ reportDate, currencyBasis = "CNX" }) =>
      requestActionJson<BalanceMovementRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-movement-analysis/refresh?report_date=${encodeURIComponent(reportDate)}&currency_basis=${encodeURIComponent(currencyBasis)}`,
      ),
  };
}

async function requestJson<T>(fetchImpl: FetchLike, baseUrl: string, path: string) {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as ApiEnvelope<T>;
}

async function requestActionJson<T>(fetchImpl: FetchLike, baseUrl: string, path: string) {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as T;
}
