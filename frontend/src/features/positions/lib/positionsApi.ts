// TODO: 接入真实后端 API，当前全部为 mock 数据
import type {
  PageResponse,
  BondPositionItem,
  InterbankPositionItem,
  CounterpartyStatsResponse,
  InterbankCounterpartySplitResponse,
  SubTypesResponse,
  ProductTypesResponse,
  RatingStatsResponse,
  IndustryStatsResponse,
  CustomerBondDetailsResponse,
  CustomerBalanceTrendResponse,
  PositionDirection,
} from "../../../api/contracts";

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

const MOCK_BOND_ITEMS: BondPositionItem[] = [
  { bond_code: "220210.IB", credit_name: "国开行", sub_type: "政策性金融债", asset_class: "TPL", market_value: "500000000.0000", face_value: "500000000.0000", valuation_net_price: "100.2350", yield_rate: "0.025500" },
  { bond_code: "230205.IB", credit_name: "农发行", sub_type: "政策性金融债", asset_class: "TPL", market_value: "300000000.0000", face_value: "300000000.0000", valuation_net_price: "99.8700", yield_rate: "0.027800" },
  { bond_code: "2380123.IB", credit_name: "中国银行", sub_type: "商业银行债", asset_class: "OCI", market_value: "200000000.0000", face_value: "200000000.0000", valuation_net_price: "101.1200", yield_rate: "0.032500" },
  { bond_code: "112345.SZ", credit_name: "万科企业", sub_type: "企业债", asset_class: "AC", market_value: "150000000.0000", face_value: "150000000.0000", valuation_net_price: "98.5600", yield_rate: "0.045200" },
  { bond_code: "019672.SH", credit_name: "财政部", sub_type: "国债", asset_class: "TPL", market_value: "800000000.0000", face_value: "800000000.0000", valuation_net_price: "100.0100", yield_rate: "0.021300" },
];

const MOCK_INTERBANK_ITEMS: InterbankPositionItem[] = [
  { deal_id: "IB20260401001", counterparty: "工商银行", product_type: "同业拆借", direction: "Asset", amount: "500000000.0000", interest_rate: "0.019500", maturity_date: "2026-07-01" },
  { deal_id: "IB20260401002", counterparty: "建设银行", product_type: "同业存放", direction: "Liability", amount: "300000000.0000", interest_rate: "0.018000", maturity_date: "2026-06-15" },
  { deal_id: "IB20260402001", counterparty: "招商银行", product_type: "买入返售", direction: "Asset", amount: "200000000.0000", interest_rate: "0.020500", maturity_date: "2026-05-02" },
];

export const positionsApi = {
  bonds: {
    list: async (params: {
      report_date?: string | null;
      sub_type?: string | null;
      page: number;
      page_size: number;
    }): Promise<PageResponse<BondPositionItem>> => {
      await delay(300);
      const filtered = params.sub_type
        ? MOCK_BOND_ITEMS.filter((i) => i.sub_type === params.sub_type)
        : MOCK_BOND_ITEMS;
      const start = (params.page - 1) * params.page_size;
      return {
        items: filtered.slice(start, start + params.page_size),
        total: filtered.length,
        page: params.page,
        page_size: params.page_size,
      };
    },
    subTypes: async (): Promise<SubTypesResponse> => {
      await delay(200);
      return { sub_types: ["国债", "政策性金融债", "商业银行债", "企业债", "中期票据", "短期融资券"] };
    },
    counterpartyStats: async (params: {
      start_date: string;
      end_date: string;
      sub_type?: string | null;
      top_n?: number;
    }): Promise<CounterpartyStatsResponse> => {
      await delay(400);
      return {
        start_date: params.start_date,
        end_date: params.end_date,
        num_days: 90,
        items: [
          { customer_name: "国开行", total_amount: "5000000000.0000", avg_daily_balance: "4500000000.0000", weighted_rate: "0.025500", weighted_coupon_rate: "0.030000", transaction_count: 12 },
          { customer_name: "农发行", total_amount: "3000000000.0000", avg_daily_balance: "2800000000.0000", weighted_rate: "0.027800", weighted_coupon_rate: "0.032000", transaction_count: 8 },
          { customer_name: "财政部", total_amount: "8000000000.0000", avg_daily_balance: "7500000000.0000", weighted_rate: "0.021300", weighted_coupon_rate: "0.022000", transaction_count: 5 },
        ],
        total_amount: "16000000000.0000",
        total_avg_daily: "14800000000.0000",
        total_weighted_rate: "0.024200",
        total_weighted_coupon_rate: "0.027300",
        total_customers: 3,
      };
    },
  },
  interbank: {
    list: async (params: {
      report_date?: string | null;
      product_type?: string | null;
      direction?: PositionDirection | "ALL" | null;
      page: number;
      page_size: number;
    }): Promise<PageResponse<InterbankPositionItem>> => {
      await delay(300);
      let filtered = params.product_type
        ? MOCK_INTERBANK_ITEMS.filter((i) => i.product_type === params.product_type)
        : MOCK_INTERBANK_ITEMS;
      if (params.direction && params.direction !== "ALL") {
        filtered = filtered.filter((i) => i.direction === params.direction);
      }
      const start = (params.page - 1) * params.page_size;
      return {
        items: filtered.slice(start, start + params.page_size),
        total: filtered.length,
        page: params.page,
        page_size: params.page_size,
      };
    },
    productTypes: async (): Promise<ProductTypesResponse> => {
      await delay(200);
      return { product_types: ["同业拆借", "同业存放", "买入返售", "卖出回购"] };
    },
    counterpartyStatsSplit: async (params: {
      start_date: string;
      end_date: string;
      product_type?: string | null;
      top_n?: number;
    }): Promise<InterbankCounterpartySplitResponse> => {
      await delay(400);
      return {
        start_date: params.start_date,
        end_date: params.end_date,
        num_days: 90,
        asset_total_amount: "7000000000.0000",
        asset_total_avg_daily: "6500000000.0000",
        asset_total_weighted_rate: "0.020000",
        asset_customer_count: 2,
        liability_total_amount: "3000000000.0000",
        liability_total_avg_daily: "2800000000.0000",
        liability_total_weighted_rate: "0.018000",
        liability_customer_count: 1,
        asset_items: [
          { customer_name: "工商银行", total_amount: "5000000000.0000", avg_daily_balance: "4500000000.0000", weighted_rate: "0.019500", transaction_count: 5 },
          { customer_name: "招商银行", total_amount: "2000000000.0000", avg_daily_balance: "2000000000.0000", weighted_rate: "0.020500", transaction_count: 3 },
        ],
        liability_items: [
          { customer_name: "建设银行", total_amount: "3000000000.0000", avg_daily_balance: "2800000000.0000", weighted_rate: "0.018000", transaction_count: 4 },
        ],
      };
    },
  },
  stats: {
    rating: async (params: {
      start_date: string;
      end_date: string;
      sub_type?: string | null;
    }): Promise<RatingStatsResponse> => {
      await delay(350);
      return {
        start_date: params.start_date,
        end_date: params.end_date,
        num_days: 90,
        items: [
          { rating: "AAA", total_amount: "12000000000.0000", avg_daily_balance: "11000000000.0000", weighted_rate: "0.025000", bond_count: 15, percentage: "55.00" },
          { rating: "AA+", total_amount: "5000000000.0000", avg_daily_balance: "4500000000.0000", weighted_rate: "0.032000", bond_count: 8, percentage: "22.50" },
          { rating: "AA", total_amount: "3000000000.0000", avg_daily_balance: "2800000000.0000", weighted_rate: "0.038000", bond_count: 5, percentage: "14.00" },
          { rating: "未评级", total_amount: "1700000000.0000", avg_daily_balance: "1700000000.0000", weighted_rate: "0.021000", bond_count: 3, percentage: "8.50" },
        ],
        total_amount: "21700000000.0000",
        total_avg_daily: "20000000000.0000",
      };
    },
    industry: async (params: {
      start_date: string;
      end_date: string;
      sub_type?: string | null;
      top_n?: number;
    }): Promise<IndustryStatsResponse> => {
      await delay(350);
      return {
        start_date: params.start_date,
        end_date: params.end_date,
        num_days: 90,
        items: [
          { industry: "金融业", total_amount: "8000000000.0000", avg_daily_balance: "7500000000.0000", weighted_rate: "0.026000", bond_count: 10, percentage: "37.50" },
          { industry: "房地产业", total_amount: "3000000000.0000", avg_daily_balance: "2800000000.0000", weighted_rate: "0.045000", bond_count: 5, percentage: "14.00" },
          { industry: "制造业", total_amount: "2500000000.0000", avg_daily_balance: "2300000000.0000", weighted_rate: "0.035000", bond_count: 4, percentage: "11.50" },
          { industry: "交通运输", total_amount: "2000000000.0000", avg_daily_balance: "1900000000.0000", weighted_rate: "0.028000", bond_count: 3, percentage: "9.50" },
          { industry: "公用事业", total_amount: "1500000000.0000", avg_daily_balance: "1400000000.0000", weighted_rate: "0.030000", bond_count: 3, percentage: "7.00" },
        ],
        total_amount: "17000000000.0000",
        total_avg_daily: "15900000000.0000",
      };
    },
  },
  customer: {
    details: async (params: {
      customer_name: string;
      report_date?: string | null;
    }): Promise<CustomerBondDetailsResponse> => {
      await delay(300);
      return {
        customer_name: params.customer_name,
        report_date: params.report_date || "2026-04-11",
        total_market_value: "5000000000.0000",
        bond_count: 3,
        items: [
          { bond_code: "220210.IB", sub_type: "政策性金融债", asset_class: "TPL", market_value: "2000000000.0000", yield_rate: "0.025500", maturity_date: "2027-03-15", rating: "AAA", industry: "金融业" },
          { bond_code: "230205.IB", sub_type: "政策性金融债", asset_class: "TPL", market_value: "1500000000.0000", yield_rate: "0.027800", maturity_date: "2028-06-20", rating: "AAA", industry: "金融业" },
          { bond_code: "240101.IB", sub_type: "政策性金融债", asset_class: "OCI", market_value: "1500000000.0000", yield_rate: "0.023000", maturity_date: "2029-01-10", rating: "AAA", industry: "金融业" },
        ],
      };
    },
    trend: async (params: {
      customer_name: string;
      end_date?: string | null;
      days?: number;
    }): Promise<CustomerBalanceTrendResponse> => {
      await delay(300);
      const days = params.days || 30;
      const items = Array.from({ length: days }, (_, i) => {
        const d = new Date(2026, 3, 11);
        d.setDate(d.getDate() - (days - 1 - i));
        const base = 5000000000 + Math.sin(i * 0.3) * 200000000;
        return {
          date: d.toISOString().slice(0, 10),
          balance: base.toFixed(4),
        };
      });
      return {
        customer_name: params.customer_name,
        start_date: items[0].date,
        end_date: items[items.length - 1].date,
        days,
        items,
      };
    },
  },
};
