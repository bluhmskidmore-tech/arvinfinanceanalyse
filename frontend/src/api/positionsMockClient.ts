/**
 * Positions demo/mock client slice.
 * Loaded only from mock composition paths (mockApiClient.ts); keeps the bond
 * trading-desk drill fixtures out of the real-mode bundle that imports
 * positionsClient.ts.
 */
import { buildMockBondTradingDeskPositionsBonds } from "../mocks/bondTradingDeskDrillFixtures";
import type { PositionDirection } from "./contracts";
import type { PositionsCoreClientMethods } from "./positionsClient";

type Delay = () => Promise<void>;

type PositionsMockBundle = Pick<
  typeof import("../mocks/mockApiEnvelope"),
  "buildMockApiEnvelope"
>;

type EnsurePositionsMockBundle = () => Promise<PositionsMockBundle>;

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
          evidence_rows: 0,
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
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.counterparty.bonds",
        {
          start_date: options.startDate,
          end_date: options.endDate,
          num_days: 0,
          items: [],
          total_amount: "0",
          total_avg_daily: "0",
          total_weighted_rate: null,
          total_weighted_coupon_rate: null,
          total_customers: 0,
          cr10_ratio: "62.34%",
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
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.interbank.list",
        {
          items: [],
          total: 0,
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
          evidence_rows: 0,
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
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.counterparty.interbank.split",
        {
          start_date: options.startDate,
          end_date: options.endDate,
          num_days: 0,
          asset_total_amount: "0",
          asset_total_avg_daily: "0",
          asset_total_weighted_rate: null,
          asset_customer_count: 0,
          liability_total_amount: "0",
          liability_total_avg_daily: "0",
          liability_total_weighted_rate: null,
          liability_customer_count: 0,
          asset_items: [],
          liability_items: [],
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
          num_days: 0,
          items: [],
          total_amount: "0",
          total_avg_daily: "0",
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
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.stats.industry",
        {
          start_date: options.startDate,
          end_date: options.endDate,
          num_days: 0,
          items: [],
          total_amount: "0",
          total_avg_daily: "0",
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
          report_date: options.reportDate ?? "",
          total_market_value: "0",
          bond_count: 0,
          items: [],
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
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.customer.trend",
        {
          customer_name: options.customerName,
          start_date: options.endDate ?? "",
          end_date: options.endDate ?? "",
          days: options.days ?? 30,
          items: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
  };
}
