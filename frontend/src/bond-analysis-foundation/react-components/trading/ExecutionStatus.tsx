import type { Order } from "../../data-structures/OrderModel";
import { EmptyState } from "../common/EmptyState";

export interface ExecutionStatusProps {
  order?: Order | null;
}

export function ExecutionStatus({ order }: ExecutionStatusProps) {
  if (!order) {
    return <EmptyState title="暂无成交状态" description="提交订单后在这里查看执行进度与成交均价。" />;
  }

  return (
    <section style={{ display: "grid", gap: 12 }}>
      <h3 style={{ margin: 0 }}>成交状态</h3>
      <div style={{ borderRadius: 18, border: "1px solid #d0d5dd", background: "#fff", padding: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
          <strong>{order.orderId}</strong>
          <span>{order.status}</span>
        </div>
        <p style={{ color: "#475467" }}>
          {order.side} {order.bondCode} / 数量 {order.quantity.toLocaleString()}
        </p>
        <div style={{ display: "grid", gap: 8 }}>
          {(order.executions ?? []).map((execution) => (
            <div key={execution.executionId} style={{ borderTop: "1px solid #eaecf0", paddingTop: 8 }}>
              <div>{execution.executedAt}</div>
              <div>
                {execution.executedQuantity.toLocaleString()} @ {execution.executedPrice.toFixed(2)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
