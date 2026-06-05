import type { IsoDateTimeString, PaginationQuery } from "./BondModel";

export type TradeSide = "BUY" | "SELL";
export type OrderType = "LIMIT" | "MARKET" | "RFQ";
export type OrderStatus =
  | "PENDING"
  | "PARTIALLY_FILLED"
  | "FILLED"
  | "CANCELLED"
  | "REJECTED";

export interface OrderExecution {
  executionId: string;
  executedQuantity: number;
  executedPrice: number;
  executedAt: IsoDateTimeString;
}

export interface Order {
  orderId: string;
  bondCode: string;
  side: TradeSide;
  quantity: number;
  price?: number;
  feeAmount?: number;
  orderType?: OrderType;
  status: OrderStatus;
  createdAt: IsoDateTimeString;
  executedAt?: IsoDateTimeString;
  averageExecutionPrice?: number;
  traderId?: string;
  executions?: OrderExecution[];
}

export interface OrderCreateRequest {
  bondCode: string;
  side: TradeSide;
  quantity: number;
  price?: number;
  feeAmount?: number;
  orderType: OrderType;
  traderId?: string;
}

export interface OrderQuery extends PaginationQuery {
  bondCode?: string;
  status?: OrderStatus[];
  side?: TradeSide;
}
