import { useState, type FormEvent } from "react";

import type { OrderCreateRequest, TradeSide } from "../../data-structures/OrderModel";

export interface OrderFormProps {
  initialBondCode?: string;
  initialSide?: TradeSide;
  submitting?: boolean;
  onSubmit?: (payload: OrderCreateRequest) => void | Promise<void>;
}

export function OrderForm({
  initialBondCode = "",
  initialSide = "BUY",
  submitting = false,
  onSubmit,
}: OrderFormProps) {
  const [bondCode, setBondCode] = useState(initialBondCode);
  const [side, setSide] = useState<TradeSide>(initialSide);
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [feeAmount, setFeeAmount] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const payload: OrderCreateRequest = {
      bondCode,
      side,
      quantity: Number(quantity),
      price: price ? Number(price) : undefined,
      feeAmount: feeAmount ? Number(feeAmount) : undefined,
      orderType: "LIMIT",
    };

    void onSubmit?.(payload);
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12 }}>
      <label>
        债券代码
        <input value={bondCode} onChange={(event) => setBondCode(event.target.value)} />
      </label>
      <label>
        交易方向
        <select value={side} onChange={(event) => setSide(event.target.value as TradeSide)}>
          <option value="BUY">买入</option>
          <option value="SELL">卖出</option>
        </select>
      </label>
      <label>
        数量
        <input value={quantity} onChange={(event) => setQuantity(event.target.value)} />
      </label>
      <label>
        价格
        <input value={price} onChange={(event) => setPrice(event.target.value)} />
      </label>
      <label>
        手续费
        <input value={feeAmount} onChange={(event) => setFeeAmount(event.target.value)} />
      </label>
      <button type="submit" disabled={submitting}>
        提交订单
      </button>
    </form>
  );
}
