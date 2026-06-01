import type {
  ApiEnvelope,
  ApiQuality,
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
  ResultMeta,
} from "../../../api/contracts";
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "../../../utils/choiceMacroFormat";

export type MarketDataTerminalStatus = "ready" | "empty" | "source-pending";

export type MarketDataTerminalSource = {
  basis: ResultMeta["basis"];
  qualityFlag: ApiQuality;
  fallbackMode: ResultMeta["fallback_mode"];
  sourceVersion: string;
  vendorVersion: string;
  traceId: string;
};

export type MarketDataTerminalRowBase = {
  key: string;
  seriesId: string;
  seriesName: string;
  rateText: string;
  deltaText: string;
  tradeDate: string;
  sourceVersion: string;
  vendorVersion: string;
  qualityFlag: ApiQuality | "unknown";
  sourceMode: string;
};

export type MarketDataRateQuoteRow = MarketDataTerminalRowBase & {
  variety: string;
  tenor: string;
};

export type MarketDataMoneyMarketRow = MarketDataTerminalRowBase & {
  name: string;
};

export type MarketDataRateQuoteSection = {
  status: MarketDataTerminalStatus;
  rows: MarketDataRateQuoteRow[];
  source: MarketDataTerminalSource | null;
  emptyReason: string;
};

export type MarketDataMoneyMarketSection = {
  status: MarketDataTerminalStatus;
  rows: MarketDataMoneyMarketRow[];
  source: MarketDataTerminalSource | null;
  emptyReason: string;
};

export type MarketDataSourcePendingSection = {
  status: "source-pending";
  rows: [];
  source: null;
  emptyReason: string;
};

export type MarketDataTerminalModel = {
  rateQuotes: MarketDataRateQuoteSection;
  moneyMarket: MarketDataMoneyMarketSection;
  bondFutures: MarketDataSourcePendingSection;
  bondTrades: MarketDataSourcePendingSection;
  creditTrades: MarketDataSourcePendingSection;
};

type BuildMarketDataTerminalModelOptions = {
  ratesEnvelope?: ApiEnvelope<ChoiceMacroLatestPayload>;
  latestEnvelope?: ApiEnvelope<ChoiceMacroLatestPayload>;
};

type SourcePoint = {
  point: ChoiceMacroLatestPoint;
  meta: ResultMeta;
};

type RateSpec = {
  seriesIds: string[];
  variety: string;
  tenor: string;
};

type MoneySpec = {
  seriesIds: string[];
  name: string;
};

const RATE_QUOTE_SPECS: RateSpec[] = [
  { seriesIds: ["EMM00166458"], variety: "国债", tenor: "1Y" },
  { seriesIds: ["EMM00166460"], variety: "国债", tenor: "3Y" },
  { seriesIds: ["EMM00166462"], variety: "国债", tenor: "5Y" },
  { seriesIds: ["EMM00166464"], variety: "国债", tenor: "7Y" },
  { seriesIds: ["CA.CN_GOV_10Y", "E1000180", "EMM00166466"], variety: "国债", tenor: "10Y" },
  { seriesIds: ["EMM00166494"], variety: "国开", tenor: "1Y" },
  { seriesIds: ["EMM00166496"], variety: "国开", tenor: "3Y" },
  { seriesIds: ["EMM00166498"], variety: "国开", tenor: "5Y" },
  { seriesIds: ["EMM00166502"], variety: "国开", tenor: "10Y" },
];

const MONEY_MARKET_SPECS: MoneySpec[] = [
  { seriesIds: ["M001"], name: "公开市场7天逆回购利率" },
  { seriesIds: ["CA.DR007", "M002", "EMM00167613"], name: "DR007" },
];

function terminalSource(meta: ResultMeta): MarketDataTerminalSource {
  return {
    basis: meta.basis,
    qualityFlag: meta.quality_flag,
    fallbackMode: meta.fallback_mode,
    sourceVersion: meta.source_version,
    vendorVersion: meta.vendor_version,
    traceId: meta.trace_id,
  };
}

function buildSourcePointMap(
  envelopes: Array<ApiEnvelope<ChoiceMacroLatestPayload> | undefined>,
): Map<string, SourcePoint> {
  const out = new Map<string, SourcePoint>();
  for (const envelope of envelopes) {
    if (!envelope) {
      continue;
    }
    for (const point of envelope.result.series) {
      if (!out.has(point.series_id)) {
        out.set(point.series_id, { point, meta: envelope.result_meta });
      }
    }
  }
  return out;
}

function findSourcePoint(map: Map<string, SourcePoint>, seriesIds: string[]) {
  for (const seriesId of seriesIds) {
    const found = map.get(seriesId);
    if (found) {
      return found;
    }
  }
  return null;
}

function rowBase(sourcePoint: SourcePoint): MarketDataTerminalRowBase {
  const { point, meta } = sourcePoint;
  return {
    key: point.series_id,
    seriesId: point.series_id,
    seriesName: point.series_name,
    rateText: formatChoiceMacroValue(point, { spaceBeforeUnit: false }),
    deltaText: formatChoiceMacroDelta(point, { spaceBeforeUnit: false, emptyDisplay: "无变动" }),
    tradeDate: point.trade_date,
    sourceVersion: meta.source_version,
    vendorVersion: point.vendor_version || meta.vendor_version,
    qualityFlag: point.quality_flag ?? meta.quality_flag ?? "unknown",
    sourceMode: point.fetch_mode ?? "unknown",
  };
}

function sectionStatus(rowCount: number): MarketDataTerminalStatus {
  return rowCount > 0 ? "ready" : "empty";
}

function primarySource(envelope?: ApiEnvelope<ChoiceMacroLatestPayload>) {
  return envelope ? terminalSource(envelope.result_meta) : null;
}

export function buildMarketDataTerminalModel({
  ratesEnvelope,
  latestEnvelope,
}: BuildMarketDataTerminalModelOptions): MarketDataTerminalModel {
  const bySeriesId = buildSourcePointMap([ratesEnvelope, latestEnvelope]);
  const rateRows = RATE_QUOTE_SPECS.flatMap((spec) => {
    const sourcePoint = findSourcePoint(bySeriesId, spec.seriesIds);
    if (!sourcePoint) {
      return [];
    }
    return [
      {
        ...rowBase(sourcePoint),
        variety: spec.variety,
        tenor: spec.tenor,
      },
    ];
  });
  const moneyRows = MONEY_MARKET_SPECS.flatMap((spec) => {
    const sourcePoint = findSourcePoint(bySeriesId, spec.seriesIds);
    if (!sourcePoint) {
      return [];
    }
    return [
      {
        ...rowBase(sourcePoint),
        name: spec.name,
      },
    ];
  });

  return {
    rateQuotes: {
      status: sectionStatus(rateRows.length),
      rows: rateRows,
      source: primarySource(ratesEnvelope) ?? primarySource(latestEnvelope),
      emptyReason: "未找到已确认的国债/国开收益率序列，前端不补示例行情。",
    },
    moneyMarket: {
      status: sectionStatus(moneyRows.length),
      rows: moneyRows,
      source: primarySource(ratesEnvelope) ?? primarySource(latestEnvelope),
      emptyReason: "未找到已确认的资金利率序列，前端不补示例成交量或区间。",
    },
    bondFutures: {
      status: "source-pending",
      rows: [],
      source: null,
      emptyReason: "国债期货实时行情源尚未纳入市场工作台合同，前端不展示静态示例合约。",
    },
    bondTrades: {
      status: "source-pending",
      rows: [],
      source: null,
      emptyReason: "现券成交明细源尚未纳入市场工作台合同，前端不展示静态成交流水。",
    },
    creditTrades: {
      status: "source-pending",
      rows: [],
      source: null,
      emptyReason: "信用债成交明细源尚未纳入市场工作台合同，前端不展示静态成交流水。",
    },
  };
}
