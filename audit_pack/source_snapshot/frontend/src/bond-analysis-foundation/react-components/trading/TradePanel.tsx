import type { Bond } from "../../data-structures/BondModel";
import type { Order, OrderCreateRequest } from "../../data-structures/OrderModel";
import { ExecutionStatus } from "./ExecutionStatus";
import { OrderForm } from "./OrderForm";
import { OrderHistory } from "./OrderHistory";

export interface TradePanelProps {
  selectedBond?: Bond;
  lastOrder?: Order | null;
  orders?: Order[];
  onSubmitOrder?: (payload: OrderCreateRequest) => void | Promise<void>;
  onCancelOrder?: (order: Order) => void;
}

export function TradePanel({
  selectedBond,
  lastOrder,
  orders = [],
  onSubmitOrder,
  onCancelOrder,
}: TradePanelProps) {
  return (
    <section style={{ display: "grid", gap: 24 }}>
      <div>
        <h2 style={{ margin: 0 }}>交易面板</h2>
        <p style={{ margin: "6px 0 0", color: "#475467" }}>
          {selectedBond ? `当前标的 ${selectedBond.shortName}` : "先从债券表格中选择一只债券。"}
        </p>
      </div>

      <div style={{ display: "grid", gap: 24, gridTemplateColumns: "1fr 1fr" }}>
        <OrderForm initialBondCode={selectedBond?.bondCode} onSubmit={onSubmitOrder} />
        <ExecutionStatus order={lastOrder} />
      </div>

      <OrderHistory orders={orders} onCancelOrder={onCancelOrder} />
    </section>
  );
}
