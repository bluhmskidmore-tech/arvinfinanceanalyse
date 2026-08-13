/**
 * Positions demo/mock client slice.
 * Loaded only from mock composition paths (mockApiClient.ts); keeps the bond
 * trading-desk drill fixtures out of the real-mode bundle that imports
 * positionsClient.ts.
 *
 * 演示数据（编造但自洽，口径依据 D 节审计与 backend/app/repositories/positions_repo.py）：
 * - 金额一律「元」整数字符串；利率为小数字符串（0.0282 → 2.82%）；
 *   percentage / coverage_ratio 为百分数字符串（50.0000 → 50.00%）；
 *   cr10_ratio 与真实契约同形（如 "90.00%"）。
 * - num_days 统一取 30（区间内有快照的天数），日均 = 区间累计 ÷ 30。
 * - 债券书三视图（授信主体 / 评级 / 行业）共享同一册总量：
 *   日均 52 亿元、区间累计 1,560 亿元。
 */
import { buildMockBondTradingDeskPositionsBonds } from "../mocks/bondTradingDeskDrillFixtures";
import type {
  CounterpartyStatItem,
  CustomerBondDetailItem,
  InterbankPositionItem,
  PositionDirection,
  RateCoverage,
} from "./contracts";
import type { PositionsCoreClientMethods } from "./positionsClient";

type Delay = () => Promise<void>;

type PositionsMockBundle = Pick<
  typeof import("../mocks/mockApiEnvelope"),
  "buildMockApiEnvelope"
>;

type EnsurePositionsMockBundle = () => Promise<PositionsMockBundle>;

// ---------------------------------------------------------------------------
// 演示数据种子与派生工具（自洽口径见 D 节审计）
// ---------------------------------------------------------------------------

/** 演示分母天数：区间内有快照的天数，三视图与同业 split 统一取 30。 */
const DEMO_NUM_DAYS = 30;
/** 演示报告日兜底，与 mock getBalanceAnalysisDates 的 2025-12-31 对齐。 */
const DEMO_REPORT_DATE = "2025-12-31";

/** 债券书全书日均（元）：Top10 合计 46.8 亿 + 尾部 4 户合计 5.2 亿。 */
const DEMO_BOND_BOOK_AVG_DAILY_YUAN = 5_200_000_000;
/** 全书授信户数（真实契约 total_customers = 全书户数，可大于展示的 TopN）。 */
const DEMO_BOND_BOOK_TOTAL_CUSTOMERS = 14;

const toAmount = (yuan: number) => String(Math.round(yuan));
const toRate = (rate: number) => rate.toFixed(4);

type DemoRateSeed = { avgDailyYuan: number; rate: number };

/** 金额加权利率（缺失利率剔除分母的演示等价：种子内无缺失）。 */
function weightedAvgRate(seeds: ReadonlyArray<DemoRateSeed>): string {
  const numerator = seeds.reduce((sum, seed) => sum + seed.avgDailyYuan * seed.rate, 0);
  const denominator = seeds.reduce((sum, seed) => sum + seed.avgDailyYuan, 0);
  return (numerator / denominator).toFixed(6);
}

/** 占比 = 档位日均 / 全书日均 × 100（等价于区间累计口径，分母同乘 30）。 */
function percentageOfBook(avgDailyYuan: number): string {
  return ((avgDailyYuan / DEMO_BOND_BOOK_AVG_DAILY_YUAN) * 100).toFixed(4);
}

/** coverage_ratio = covered / (covered + missing)，policy 与真实契约一致。 */
function buildDemoCoverage(seed: {
  coveredYuan: number;
  missingYuan: number;
  missingCount: number;
}): RateCoverage {
  const ratio = (seed.coveredYuan / (seed.coveredYuan + seed.missingYuan)) * 100;
  return {
    policy: "exclude_missing_rate_from_denominator",
    covered_amount: toAmount(seed.coveredYuan),
    missing_amount: toAmount(seed.missingYuan),
    missing_count: seed.missingCount,
    coverage_ratio: ratio.toFixed(6),
  };
}

/** ISO 日期偏移（UTC 计算，避免本地时区回退串日）。 */
function shiftIsoDate(iso: string, deltaDays: number): string {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(Date.UTC(year ?? 2025, (month ?? 1) - 1, (day ?? 1) + deltaDays))
    .toISOString()
    .slice(0, 10);
}

/**
 * 授信主体 Top10（日均元 / YTM / 票面 / 笔数），金额降序；
 * 尾部 4 户合计日均 5.2 亿（每户 ≤ 第 10 名的 1.8 亿）不入列，
 * 故 CR10 = 46.8 / 52 = 90.00%，total_customers = 14。
 */
const DEMO_BOND_COUNTERPARTY_SEEDS = [
  { name: "苏州城市建设投资发展集团有限公司", avgDailyYuan: 840_000_000, rate: 0.0282, coupon: 0.0305, deals: 24 },
  { name: "成都轨道交通集团有限公司", avgDailyYuan: 720_000_000, rate: 0.0295, coupon: 0.0318, deals: 21 },
  { name: "华能国际电力股份有限公司", avgDailyYuan: 600_000_000, rate: 0.0268, coupon: 0.0292, deals: 18 },
  { name: "青岛国信发展(集团)有限责任公司", avgDailyYuan: 540_000_000, rate: 0.0301, coupon: 0.0325, deals: 16 },
  { name: "湖北省交通投资集团有限公司", avgDailyYuan: 480_000_000, rate: 0.0312, coupon: 0.0336, deals: 14 },
  { name: "陕西延长石油(集团)有限责任公司", avgDailyYuan: 420_000_000, rate: 0.0324, coupon: 0.0348, deals: 12 },
  { name: "招商银行股份有限公司", avgDailyYuan: 360_000_000, rate: 0.0245, coupon: 0.0270, deals: 9 },
  { name: "中国长江三峡集团有限公司", avgDailyYuan: 300_000_000, rate: 0.0236, coupon: 0.0260, deals: 8 },
  { name: "万科企业股份有限公司", avgDailyYuan: 240_000_000, rate: 0.0358, coupon: 0.0382, deals: 6 },
  { name: "广州地铁集团有限公司", avgDailyYuan: 180_000_000, rate: 0.0258, coupon: 0.0285, deals: 5 },
] as const;

/** 评级 5 档：日均合计 = 全书 52 亿，占比合计恰为 100；顺序同后端 RATING_ORDER。 */
const DEMO_RATING_SEEDS = [
  { rating: "AAA", avgDailyYuan: 2_600_000_000, rate: 0.0262, bondCount: 28 },
  { rating: "AA+", avgDailyYuan: 1_300_000_000, rate: 0.0291, bondCount: 19 },
  { rating: "AA", avgDailyYuan: 780_000_000, rate: 0.0322, bondCount: 12 },
  { rating: "AA-", avgDailyYuan: 312_000_000, rate: 0.0355, bondCount: 5 },
  { rating: "未评级", avgDailyYuan: 208_000_000, rate: 0.0338, bondCount: 3 },
] as const;

/** 行业 6 档：日均合计同为全书 52 亿，只数合计与评级侧一致（67 只），金额降序。 */
const DEMO_INDUSTRY_SEEDS = [
  { industry: "城投基建", avgDailyYuan: 1_820_000_000, rate: 0.0301, bondCount: 21 },
  { industry: "电力能源", avgDailyYuan: 1_040_000_000, rate: 0.0285, bondCount: 13 },
  { industry: "交通运输", avgDailyYuan: 936_000_000, rate: 0.0296, bondCount: 11 },
  { industry: "金融", avgDailyYuan: 624_000_000, rate: 0.0252, bondCount: 9 },
  { industry: "综合", avgDailyYuan: 468_000_000, rate: 0.0288, bondCount: 8 },
  { industry: "房地产", avgDailyYuan: 312_000_000, rate: 0.0361, bondCount: 5 },
] as const;

/** 覆盖率分母 = 全书区间累计 1,560 亿：YTM 缺 3 笔/60 亿，票面缺 5 笔/90 亿。 */
const DEMO_YTM_COVERAGE = {
  coveredYuan: 150_000_000_000,
  missingYuan: 6_000_000_000,
  missingCount: 3,
};
const DEMO_COUPON_COVERAGE = {
  coveredYuan: 147_000_000_000,
  missingYuan: 9_000_000_000,
  missingCount: 5,
};

/** 同业区间聚合两侧种子：items 加总 = side totals，customer_count = items 数。 */
const DEMO_INTERBANK_ASSET_SEEDS = [
  { name: "兴业银行股份有限公司", avgDailyYuan: 1_500_000_000, rate: 0.0198, deals: 8 },
  { name: "宁波银行股份有限公司", avgDailyYuan: 900_000_000, rate: 0.0212, deals: 6 },
  { name: "上海浦东发展银行股份有限公司", avgDailyYuan: 600_000_000, rate: 0.0205, deals: 4 },
] as const;
const DEMO_INTERBANK_LIABILITY_SEEDS = [
  { name: "中信银行股份有限公司", avgDailyYuan: 1_200_000_000, rate: 0.0182, deals: 7 },
  { name: "中国邮政储蓄银行股份有限公司", avgDailyYuan: 800_000_000, rate: 0.0169, deals: 5 },
  { name: "平安银行股份有限公司", avgDailyYuan: 500_000_000, rate: 0.0175, deals: 3 },
] as const;

/** 同业明细（报告日快照）：对手方与 split 种子对齐，资产 3 行 / 负债 2 行。 */
const DEMO_INTERBANK_LIST_ITEMS: InterbankPositionItem[] = [
  {
    deal_id: "TYW-2025-1201",
    counterparty: "兴业银行股份有限公司",
    product_type: "存放",
    direction: "Asset",
    amount: "1500000000",
    interest_rate: "0.0198",
    maturity_date: "2026-03-15",
  },
  {
    deal_id: "TYW-2025-1188",
    counterparty: "上海浦东发展银行股份有限公司",
    product_type: "拆借",
    direction: "Asset",
    amount: "800000000",
    interest_rate: "0.0205",
    maturity_date: "2026-01-20",
  },
  {
    deal_id: "TYW-2025-1215",
    counterparty: "中信银行股份有限公司",
    product_type: "拆借",
    direction: "Liability",
    amount: "1200000000",
    interest_rate: "0.0182",
    maturity_date: "2026-02-10",
  },
  {
    deal_id: "TYW-2025-1222",
    counterparty: "平安银行股份有限公司",
    product_type: "存放",
    direction: "Liability",
    amount: "600000000",
    interest_rate: "0.0175",
    maturity_date: "2026-04-08",
  },
  {
    deal_id: "TYW-2025-1230",
    counterparty: "宁波银行股份有限公司",
    product_type: "拆借",
    direction: "Asset",
    amount: "500000000",
    interest_rate: "0.0212",
    maturity_date: "2026-05-12",
  },
];

/**
 * 客户债券明细（点击任意授信主体均返回同一演示组合）：
 * 总市值 = 明细加总 = 9.9 亿；首行 149001.SZ 与债券列表夹具对齐，可下钻交易台。
 */
const DEMO_CUSTOMER_BOND_ITEMS: CustomerBondDetailItem[] = [
  {
    bond_code: "149001.SZ",
    sub_type: "公司债",
    asset_class: "credit",
    market_value: "240000000",
    yield_rate: "0.0310",
    maturity_date: "2027-06-15",
    rating: "AA+",
    industry: "城投基建",
  },
  {
    bond_code: "102280045.IB",
    sub_type: "中期票据",
    asset_class: "credit",
    market_value: "300000000",
    yield_rate: "0.0298",
    maturity_date: "2026-11-20",
    rating: "AAA",
    industry: "电力能源",
  },
  {
    bond_code: "042380211.IB",
    sub_type: "短期融资券",
    asset_class: "credit",
    market_value: "150000000",
    yield_rate: "0.0265",
    maturity_date: "2026-05-09",
    rating: "AAA",
    industry: "交通运输",
  },
  {
    bond_code: "175860.SH",
    sub_type: "公司债",
    asset_class: "credit",
    market_value: "180000000",
    yield_rate: "0.0334",
    maturity_date: "2028-03-18",
    rating: "AA",
    industry: "综合",
  },
  {
    bond_code: "232280156.IB",
    sub_type: "中期票据",
    asset_class: "credit",
    market_value: "120000000",
    yield_rate: "0.0351",
    maturity_date: "2027-09-30",
    rating: "AA-",
    industry: "房地产",
  },
];

/** 明细总市值（= 趋势末日余额，两视图锚定同一数）。 */
const DEMO_CUSTOMER_TOTAL_MARKET_VALUE_YUAN = DEMO_CUSTOMER_BOND_ITEMS.reduce(
  (sum, item) => sum + Number(item.market_value),
  0,
);

function buildDemoCounterpartyItems(
  seeds: ReadonlyArray<{
    name: string;
    avgDailyYuan: number;
    rate: number;
    deals: number;
    coupon?: number;
  }>,
): CounterpartyStatItem[] {
  return seeds.map((seed) => ({
    customer_name: seed.name,
    total_amount: toAmount(seed.avgDailyYuan * DEMO_NUM_DAYS),
    avg_daily_balance: toAmount(seed.avgDailyYuan),
    weighted_rate: toRate(seed.rate),
    // 债券侧带票面利率；同业侧与真实契约一致显式 null。
    weighted_coupon_rate: seed.coupon != null ? toRate(seed.coupon) : null,
    transaction_count: seed.deals,
  }));
}

/** 30 天连续余额序列：末日余额锚定明细总市值，波动确定性（无随机）。 */
function buildDemoCustomerTrendItems(endDate: string, days: number) {
  const items: Array<{ date: string; balance: string }> = [];
  for (let i = 0; i < days; i += 1) {
    const offset = days - 1 - i;
    const wiggle = offset === 0 ? 0 : Math.round(Math.sin(i * 0.9) * 6_000_000);
    const balance = DEMO_CUSTOMER_TOTAL_MARKET_VALUE_YUAN - offset * 1_600_000 + wiggle;
    items.push({ date: shiftIsoDate(endDate, -offset), balance: String(balance) });
  }
  return items;
}

export function createDemoPositionsClient(
  delay: Delay,
  ensureMockClientBundle: EnsurePositionsMockBundle,
): PositionsCoreClientMethods {
  return {
    async getPositionsBondSubTypes(_reportDate?: string | null) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.bonds.sub_types",
        { sub_types: ["利率债", "信用债"] },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsBondsList(options: {
      reportDate?: string | null;
      subType?: string | null;
      page: number;
      pageSize: number;
      includeIssued?: boolean;
    }) {
      await delay();
      const items = buildMockBondTradingDeskPositionsBonds();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.bonds.list",
        {
          items,
          total: items.length,
          page: options.page,
          page_size: options.pageSize,
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          quality_flag: "warning",
          requested_report_date: options.reportDate,
          resolved_report_date: options.reportDate,
          as_of_date: options.reportDate,
          date_basis: "positions_snapshot_report_date",
          filters_applied: {
            report_date: options.reportDate,
            sub_type: options.subType,
            page: options.page,
            page_size: options.pageSize,
            include_issued: Boolean(options.includeIssued),
          },
          tables_used: ["zqtz_bond_daily_snapshot"],
          // 与真实契约一致：evidence_rows = 命中明细行数（= total）。
          evidence_rows: items.length,
        },
      );
    },
    async getPositionsCounterpartyBonds(options: {
      startDate: string;
      endDate: string;
      subType?: string | null;
      topN?: number;
      page?: number;
      pageSize?: number;
    }) {
      await delay();
      const items = buildDemoCounterpartyItems(DEMO_BOND_COUNTERPARTY_SEEDS).slice(
        0,
        options.topN && options.topN > 0 ? options.topN : undefined,
      );
      const top10AvgDailyYuan = DEMO_BOND_COUNTERPARTY_SEEDS.reduce(
        (sum, seed) => sum + seed.avgDailyYuan,
        0,
      );
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.counterparty.bonds",
        {
          start_date: options.startDate,
          end_date: options.endDate,
          num_days: DEMO_NUM_DAYS,
          items,
          total_amount: toAmount(DEMO_BOND_BOOK_AVG_DAILY_YUAN * DEMO_NUM_DAYS),
          total_avg_daily: toAmount(DEMO_BOND_BOOK_AVG_DAILY_YUAN),
          // 全书加权收益率取评级视图同册口径（尾部 4 户隐含利率约 2.73%，自洽）。
          total_weighted_rate: weightedAvgRate(DEMO_RATING_SEEDS),
          // 全书加权付息率按 Top10 加权（尾部按同均值补齐的演示假设）。
          total_weighted_coupon_rate: weightedAvgRate(
            DEMO_BOND_COUNTERPARTY_SEEDS.map((seed) => ({
              avgDailyYuan: seed.avgDailyYuan,
              rate: seed.coupon,
            })),
          ),
          total_customers: DEMO_BOND_BOOK_TOTAL_CUSTOMERS,
          ytm_rate_coverage: buildDemoCoverage(DEMO_YTM_COVERAGE),
          coupon_rate_coverage: buildDemoCoverage(DEMO_COUPON_COVERAGE),
          // CR10 = Top10 区间累计 / 全书区间累计 = 46.8 / 52 = 90.00%。
          cr10_ratio: `${((top10AvgDailyYuan / DEMO_BOND_BOOK_AVG_DAILY_YUAN) * 100).toFixed(2)}%`,
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsInterbankProductTypes(_reportDate?: string | null) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.interbank.product_types",
        { product_types: ["拆借", "存放"] },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsInterbankList(options: {
      reportDate?: string | null;
      productType?: string | null;
      direction?: PositionDirection | "ALL" | null;
      page: number;
      pageSize: number;
    }) {
      await delay();
      // 与真实端点同语义：按产品类型 / 方向过滤后分页。
      const filtered = DEMO_INTERBANK_LIST_ITEMS.filter(
        (item) =>
          (!options.productType || item.product_type === options.productType) &&
          (!options.direction ||
            options.direction === "ALL" ||
            item.direction === options.direction),
      );
      const startIndex = (options.page - 1) * options.pageSize;
      const items = filtered.slice(startIndex, startIndex + options.pageSize);
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.interbank.list",
        {
          items,
          total: filtered.length,
          page: options.page,
          page_size: options.pageSize,
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          quality_flag: "warning",
          requested_report_date: options.reportDate,
          resolved_report_date: options.reportDate,
          as_of_date: options.reportDate,
          date_basis: "positions_snapshot_report_date",
          filters_applied: {
            report_date: options.reportDate,
            product_type: options.productType,
            direction: options.direction,
            page: options.page,
            page_size: options.pageSize,
          },
          tables_used: ["tyw_interbank_daily_snapshot"],
          // 与真实契约一致：evidence_rows = 命中明细行数（= total）。
          evidence_rows: filtered.length,
        },
      );
    },
    async getPositionsCounterpartyInterbankSplit(options: {
      startDate: string;
      endDate: string;
      productType?: string | null;
      topN?: number;
    }) {
      await delay();
      // 演示数据不区分产品类型过滤，两侧始终返回全书聚合。
      const assetAvgDailyYuan = DEMO_INTERBANK_ASSET_SEEDS.reduce(
        (sum, seed) => sum + seed.avgDailyYuan,
        0,
      );
      const liabilityAvgDailyYuan = DEMO_INTERBANK_LIABILITY_SEEDS.reduce(
        (sum, seed) => sum + seed.avgDailyYuan,
        0,
      );
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.counterparty.interbank.split",
        {
          start_date: options.startDate,
          end_date: options.endDate,
          num_days: DEMO_NUM_DAYS,
          asset_total_amount: toAmount(assetAvgDailyYuan * DEMO_NUM_DAYS),
          asset_total_avg_daily: toAmount(assetAvgDailyYuan),
          asset_total_weighted_rate: weightedAvgRate(DEMO_INTERBANK_ASSET_SEEDS),
          asset_customer_count: DEMO_INTERBANK_ASSET_SEEDS.length,
          liability_total_amount: toAmount(liabilityAvgDailyYuan * DEMO_NUM_DAYS),
          liability_total_avg_daily: toAmount(liabilityAvgDailyYuan),
          liability_total_weighted_rate: weightedAvgRate(DEMO_INTERBANK_LIABILITY_SEEDS),
          liability_customer_count: DEMO_INTERBANK_LIABILITY_SEEDS.length,
          asset_items: buildDemoCounterpartyItems(DEMO_INTERBANK_ASSET_SEEDS),
          liability_items: buildDemoCounterpartyItems(DEMO_INTERBANK_LIABILITY_SEEDS),
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsStatsRating(options: {
      startDate: string;
      endDate: string;
      subType?: string | null;
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.stats.rating",
        {
          start_date: options.startDate,
          end_date: options.endDate,
          num_days: DEMO_NUM_DAYS,
          items: DEMO_RATING_SEEDS.map((seed) => ({
            rating: seed.rating,
            total_amount: toAmount(seed.avgDailyYuan * DEMO_NUM_DAYS),
            avg_daily_balance: toAmount(seed.avgDailyYuan),
            weighted_rate: toRate(seed.rate),
            bond_count: seed.bondCount,
            percentage: percentageOfBook(seed.avgDailyYuan),
          })),
          total_amount: toAmount(DEMO_BOND_BOOK_AVG_DAILY_YUAN * DEMO_NUM_DAYS),
          total_avg_daily: toAmount(DEMO_BOND_BOOK_AVG_DAILY_YUAN),
          ytm_rate_coverage: buildDemoCoverage(DEMO_YTM_COVERAGE),
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsStatsIndustry(options: {
      startDate: string;
      endDate: string;
      subType?: string | null;
      topN?: number;
    }) {
      await delay();
      const items = DEMO_INDUSTRY_SEEDS.map((seed) => ({
        industry: seed.industry,
        total_amount: toAmount(seed.avgDailyYuan * DEMO_NUM_DAYS),
        avg_daily_balance: toAmount(seed.avgDailyYuan),
        weighted_rate: toRate(seed.rate),
        bond_count: seed.bondCount,
        percentage: percentageOfBook(seed.avgDailyYuan),
      })).slice(0, options.topN && options.topN > 0 ? options.topN : undefined);
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.stats.industry",
        {
          start_date: options.startDate,
          end_date: options.endDate,
          num_days: DEMO_NUM_DAYS,
          items,
          total_amount: toAmount(DEMO_BOND_BOOK_AVG_DAILY_YUAN * DEMO_NUM_DAYS),
          total_avg_daily: toAmount(DEMO_BOND_BOOK_AVG_DAILY_YUAN),
          ytm_rate_coverage: buildDemoCoverage(DEMO_YTM_COVERAGE),
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsCustomerDetails(options: {
      customerName: string;
      reportDate?: string | null;
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.customer.details",
        {
          customer_name: options.customerName,
          report_date: options.reportDate ?? DEMO_REPORT_DATE,
          total_market_value: toAmount(DEMO_CUSTOMER_TOTAL_MARKET_VALUE_YUAN),
          bond_count: DEMO_CUSTOMER_BOND_ITEMS.length,
          items: DEMO_CUSTOMER_BOND_ITEMS,
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsCustomerTrend(options: {
      customerName: string;
      endDate?: string | null;
      days?: number;
    }) {
      await delay();
      const days = Math.max(options.days ?? 30, 1);
      const endDate = options.endDate ?? DEMO_REPORT_DATE;
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.customer.trend",
        {
          customer_name: options.customerName,
          // 与真实契约同语义：窗口起点 = end_date - (days - 1)。
          start_date: shiftIsoDate(endDate, -(days - 1)),
          end_date: endDate,
          days,
          items: buildDemoCustomerTrendItems(endDate, days),
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
  };
}
