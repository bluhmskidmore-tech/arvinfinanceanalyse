import type { Order } from "../../data-structures/OrderModel";
import { EmptyState } from "../common/EmptyState";

export interface OrderHistoryProps {
  orders: Order[];
  onCancelOrder?: (order: Order) => void;
}

export function OrderHistory({ orders, onCancelOrder }: OrderHistoryProps) {
  if (orders.length === 0) {
    return <EmptyState title="暂无订单历史" description="最近订单、成交和撤单记录会在这里沉淀。" />;
  }

  return (
    <section style={{ display: "grid", gap: 12 }}>
      <h3 style={{ margin: 0 }}>订单历史</h3>
      {orders.map((order) => (
        <div
          key={order.orderId}
          style={{ borderRadius: 18, border: "1px solid #d0d5dd", background: "#fff", padding: 16 }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <strong>{order.orderId}</strong>
            <span>{order.status}</span>
          </div>
          <p style={{ color: "#475467" }}>
            {order.side} {order.bondCode} / {order.quantity.toLocaleString()}
          </p>
          {order.status === "PENDING" || order.status === "PARTIALLY_FILLED" ? (
            <button type="button" onClick={() => onCancelOrder?.(order)}>
              取消订单
            </button>
          ) : null}
        </div>
      ))}
    </section>
  );
}
